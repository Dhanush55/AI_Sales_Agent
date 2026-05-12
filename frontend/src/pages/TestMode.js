import React, { useEffect, useState, useRef, useCallback } from 'react';
import Navbar from '../components/Navbar';
import api from '../utils/api';

/* ─── Simple RMS energy VAD (no WASM / no special headers needed) ─── */
const SPEECH_THRESHOLD = 12;   // RMS out of 255 — above this = speech
const SILENCE_MS       = 800;  // ms of quiet before we cut the recording
const MIN_SPEECH_MS    = 300;  // ignore clips shorter than this

const TestMode = () => {
  const [campaigns, setCampaigns] = useState([]);
  const [selectedCampaign, setSelectedCampaign] = useState(null);
  const [currentCallId, setCurrentCallId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [userInput, setUserInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [callEnded, setCallEnded] = useState(false);

  /* voice states */
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [micPermission, setMicPermission] = useState(null);
  const [voiceMode, setVoiceMode] = useState(false);   // ChatGPT-style on/off
  const [status, setStatus] = useState('idle');         // idle | listening | processing | speaking
  const [voiceError, setVoiceError] = useState('');
  const [volume, setVolume] = useState(0);              // 0-100 for animation
  const [lastTranscript, setLastTranscript] = useState('');
  const [debugLog, setDebugLog] = useState([]);

  const addDebug = (msg) => {
    const ts = new Date().toLocaleTimeString();
    console.log(`[DEBUG ${ts}]`, msg);
    setDebugLog(prev => [...prev.slice(-29), `${ts}  ${msg}`]);
  };

  const forceReset = () => {
    addDebug('🔧 FORCE RESET clicked');
    stopVoiceMode();
    setStatus('idle');
    setVoiceError('');
    setLoading(false);
  };

  /* refs */
  const mediaRecorderRef = useRef(null);
  const audioChunksRef   = useRef([]);
  const audioContextRef  = useRef(null);
  const analyserRef      = useRef(null);
  const streamRef        = useRef(null);
  const silenceTimerRef  = useRef(null);
  const speechStartRef   = useRef(null);
  const vadLoopRef       = useRef(null);
  const currentAudioRef  = useRef(null);
  const voiceModeRef     = useRef(false);
  const statusRef        = useRef('idle');
  const messagesEndRef   = useRef(null);
  const audioQueueRef    = useRef([]);    // pending audio blob URLs to play in order
  const isPlayingRef     = useRef(false); // currently draining audio queue
  const callIdRef           = useRef(null);  // mutable copy for streaming callback
  const selectedCampaignRef = useRef(null);  // mutable copy so voice callbacks always see current value

  /* keep refs in sync with state */
  useEffect(() => { voiceModeRef.current = voiceMode; }, [voiceMode]);
  useEffect(() => { statusRef.current = status; }, [status]);
  useEffect(() => { callIdRef.current = currentCallId; }, [currentCallId]);
  useEffect(() => { selectedCampaignRef.current = selectedCampaign; }, [selectedCampaign]);

  /* auto-scroll chat */
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    fetchCampaigns();
    checkVoiceStatus();
    checkMicPermission();
    return () => stopVoiceMode();
  }, []);

  const checkVoiceStatus = async () => {
    try {
      const r = await api.get('/voice/status');
      setVoiceEnabled(r.data.voice_enabled);
    } catch { setVoiceEnabled(false); }
  };

  const checkMicPermission = async () => {
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: true });
      s.getTracks().forEach(t => t.stop());
      setMicPermission(true);
    } catch { setMicPermission(false); }
  };

  const fetchCampaigns = async () => {
    try {
      const r = await api.get('/campaigns');
      setCampaigns(r.data);
      if (r.data.length > 0) setSelectedCampaign(r.data[0].id);
    } catch {}
  };

  /* ─── stop everything ─── */
  const stopVoiceMode = useCallback(() => {
    // Clear VAD polling interval
    if (silenceTimerRef.current) {
      clearInterval(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    // Stop MediaRecorder gracefully
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
    // Release mic stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    // Close AudioContext
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    currentAudioRef.current?.pause();
    setVoiceMode(false);
    setStatus('idle');
    setVolume(0);
  }, []);

  /* ─── start listening with simple RMS energy VAD ─── */
  const startListening = useCallback(async () => {
    if (!voiceModeRef.current || statusRef.current !== 'idle') {
      addDebug(`startListening SKIPPED — voiceMode=${voiceModeRef.current} status=${statusRef.current}`);
      return;
    }
    addDebug('startListening → RMS VAD starting');
    setStatus('listening');

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      streamRef.current = stream;

      // AudioContext + analyser for energy detection
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      audioContextRef.current = audioCtx;
      const source  = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);
      analyserRef.current = analyser;
      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      // MediaRecorder to capture audio
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      audioChunksRef.current   = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        const blob = new Blob(audioChunksRef.current, { type: recorder.mimeType || 'audio/webm' });
        audioChunksRef.current = [];
        stream.getTracks().forEach(t => t.stop());
        audioCtx.close().catch(() => {});
        streamRef.current      = null;
        audioContextRef.current = null;
        await processVoiceBlob(blob);
      };

      // RMS VAD polling loop — no WASM, no special headers
      let isSpeaking   = false;
      let silenceStart = null;
      let speechStart  = null;

      const vadInterval = setInterval(() => {
        if (!voiceModeRef.current) {
          clearInterval(vadInterval);
          if (recorder.state === 'recording') recorder.stop();
          else { stream.getTracks().forEach(t => t.stop()); audioCtx.close().catch(() => {}); }
          return;
        }

        analyser.getByteTimeDomainData(dataArray);
        // time-domain values are centred at 128; RMS gives energy
        const rms = Math.sqrt(
          dataArray.reduce((sum, v) => sum + (v - 128) ** 2, 0) / dataArray.length
        );
        const speaking = rms > SPEECH_THRESHOLD;
        setVolume(Math.min(100, rms * 4));

        if (speaking) {
          silenceStart = null;
          if (!isSpeaking) {
            isSpeaking  = true;
            speechStart = Date.now();
            recorder.start(100);   // collect in 100 ms slices
            addDebug(`RMS speech detected (rms=${rms.toFixed(1)})`);
          }
        } else if (isSpeaking) {
          if (!silenceStart) silenceStart = Date.now();
          const silenceDuration = Date.now() - silenceStart;

          if (silenceDuration >= SILENCE_MS) {
            clearInterval(vadInterval);
            silenceTimerRef.current = null;
            const speechDuration = Date.now() - (speechStart || 0);

            if (speechDuration >= MIN_SPEECH_MS && recorder.state === 'recording') {
              addDebug(`speech ended (${speechDuration}ms) → processing`);
              setStatus('processing');
              setVolume(0);
              recorder.stop();   // → onstop → processVoiceBlob
            } else {
              addDebug('too short — re-listening');
              if (recorder.state === 'recording') recorder.stop();
              else { stream.getTracks().forEach(t => t.stop()); audioCtx.close().catch(() => {}); }
              setStatus('idle');
              if (voiceModeRef.current) setTimeout(startListening, 300);
            }
          }
        }
      }, 100);

      silenceTimerRef.current = vadInterval;

    } catch (e) {
      setVoiceError('Microphone error: ' + e.message);
      addDebug('VAD error: ' + e.message);
      setVoiceMode(false);
      setStatus('idle');
    }
  }, []);

  const handleRecordingStop = async () => {
    // Legacy — kept for safety but Silero VAD handles this now
    addDebug('handleRecordingStop called (legacy path)');
    setVolume(0);

    const duration = Date.now() - (speechStartRef.current || 0);
    addDebug(`recording stopped — ${duration}ms, ${audioChunksRef.current.length} chunks`);
    if (duration < MIN_SPEECH_MS || audioChunksRef.current.length === 0) {
      /* too short — re-listen */
      addDebug('too short, re-listening');
      setStatus('idle');
      if (voiceModeRef.current) setTimeout(startListening, 300);
      return;
    }

    const blob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
    await processVoiceBlob(blob);
  };

  /* ─── audio queue: play chunks in order, re-listen after last ─── */
  const drainAudioQueue = async () => {
    if (isPlayingRef.current) return;
    isPlayingRef.current = true;
    setStatus('speaking');
    while (audioQueueRef.current.length > 0) {
      const url = audioQueueRef.current.shift();
      const audio = new Audio(url);
      currentAudioRef.current = audio;
      await new Promise((resolve) => {
        audio.onended = () => { URL.revokeObjectURL(url); resolve(); };
        audio.onerror = () => { URL.revokeObjectURL(url); resolve(); };
        audio.play().catch(() => resolve());
      });
    }
    isPlayingRef.current = false;
    addDebug('audio queue drained → re-listen');
    setStatus('idle');
    if (voiceModeRef.current) setTimeout(startListening, 200);
  };

  /* ─── SSE-based single-roundtrip voice turn ─── */
  const processVoiceBlob = async (blob) => {
    setStatus('processing');
    const activeCampaign = selectedCampaignRef.current;
    addDebug(`blob ${blob.size}B → /test-mode/voice-turn (SSE) — campaign=${activeCampaign?.slice(0,8) || 'NONE'} callId=${callIdRef.current?.slice(0,8) || 'null'}`);
    audioQueueRef.current = [];

    if (!activeCampaign) {
      addDebug('ABORT: no campaign selected');
      setVoiceError('Please select a campaign first');
      setStatus('idle');
      return;
    }

    try {
      const fd = new FormData();
      fd.append('audio', blob, 'recording.wav');
      fd.append('campaign_id', activeCampaign);
      if (callIdRef.current) fd.append('call_id', callIdRef.current);

      const token = localStorage.getItem('token');
      const url = `${process.env.REACT_APP_BACKEND_URL}/api/test-mode/voice-turn`;
      addDebug(`POST ${url}`);
      const res = await fetch(url, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      addDebug(`HTTP ${res.status} ${res.headers.get('content-type') || ''}`);

      if (!res.ok) {
        // Clone defensively — the body may already be locked by browser
        let detail = `HTTP ${res.status}`;
        try {
          detail = await res.clone().text();
        } catch (_) { /* body unreadable, keep status */ }
        addDebug(`error body: ${detail.slice(0, 120)}`);
        setVoiceError(`Server ${res.status}: ${detail.slice(0, 80)}`);
        setStatus('idle');
        if (voiceModeRef.current) setTimeout(() => { setVoiceError(''); startListening(); }, 1200);
        return;
      }

      if (!res.body) {
        addDebug('no response body — server returned empty');
        setVoiceError('Empty server response');
        setStatus('idle');
        if (voiceModeRef.current) setTimeout(() => { setVoiceError(''); startListening(); }, 1200);
        return;
      }

      // Parse SSE stream incrementally
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let sseBuffer = '';
      let userMsgPushed = false;
      let agentText = '';
      let agentMsgIndex = -1;
      const t0 = performance.now();
      let firstAudioMs = null;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        sseBuffer += decoder.decode(value, { stream: true });

        // Extract complete events (separated by \n\n)
        let sep;
        while ((sep = sseBuffer.indexOf('\n\n')) !== -1) {
          const raw = sseBuffer.slice(0, sep);
          sseBuffer = sseBuffer.slice(sep + 2);
          if (!raw.trim()) continue;

          let eventName = 'message';
          let dataLine = '';
          for (const line of raw.split('\n')) {
            if (line.startsWith('event:')) eventName = line.slice(6).trim();
            else if (line.startsWith('data:')) dataLine += line.slice(5).trim();
          }
          if (!dataLine) continue;
          let data;
          try { data = JSON.parse(dataLine); } catch { continue; }

          if (eventName === 'transcript') {
            setLastTranscript(data.text);
            addDebug(`transcript (${Math.round(performance.now() - t0)}ms): "${data.text.slice(0, 50)}"`);
            if (!userMsgPushed) {
              setMessages(prev => [...prev, { speaker: 'user', text: data.text }]);
              userMsgPushed = true;
            }
          } else if (eventName === 'delta') {
            agentText += data.text;
            setMessages(prev => {
              const next = [...prev];
              if (agentMsgIndex === -1) {
                agentMsgIndex = next.length;
                next.push({ speaker: 'agent', text: agentText });
              } else {
                next[agentMsgIndex] = { speaker: 'agent', text: agentText };
              }
              return next;
            });
          } else if (eventName === 'audio') {
            if (firstAudioMs === null) {
              firstAudioMs = Math.round(performance.now() - t0);
              addDebug(`first audio chunk @ ${firstAudioMs}ms 🚀`);
            }
            // base64 → Blob → URL → enqueue
            const bin = atob(data.b64);
            const bytes = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
            const audioBlob = new Blob([bytes], { type: 'audio/mpeg' });
            const audioUrl = URL.createObjectURL(audioBlob);
            audioQueueRef.current.push(audioUrl);
            // kick playback if not already running
            drainAudioQueue();
          } else if (eventName === 'done') {
            const m = data.metrics || {};
            addDebug(`✅ done @ ${Math.round(performance.now() - t0)}ms | STT:${m.stt_ms}ms LLM:${m.llm_ms}ms TTS1:${m.tts_first_ms}ms`);
            if (data.call_id) {
              setCurrentCallId(data.call_id);
              callIdRef.current = data.call_id;
            }
            if (data.should_end_call) {
              setCallEnded(true);
              stopVoiceMode();
              return;
            }
          } else if (eventName === 'error') {
            addDebug(`server error: ${data.detail}`);
            setVoiceError(data.detail || 'Server error');
            setStatus('idle');
            if (voiceModeRef.current) setTimeout(() => { setVoiceError(''); startListening(); }, 1200);
            return;
          }
        }
      }

      // Stream ended — if no audio got queued, re-listen now
      if (audioQueueRef.current.length === 0 && !isPlayingRef.current) {
        setStatus('idle');
        if (voiceModeRef.current) setTimeout(startListening, 200);
      }
    } catch (e) {
      addDebug(`stream error: ${e.message}`);
      setVoiceError('Voice processing error: ' + e.message);
      setStatus('idle');
      if (voiceModeRef.current) setTimeout(() => { setVoiceError(''); startListening(); }, 1500);
    }
  };

  /* ─── play TTS, then re-listen ─── */
  const playAndRelisten = async (text, language) => {
    if (!voiceEnabled) {
      setStatus('idle');
      if (voiceModeRef.current) setTimeout(startListening, 300);
      return;
    }
    try {
      setStatus('speaking');
      addDebug(`TTS request → ${language}`);
      const res = await api.post('/voice/tts', { text, language: language || 'indian_english' }, { responseType: 'blob' });
      addDebug(`TTS got ${res.data.size}B audio`);
      const url = URL.createObjectURL(res.data);
      const audio = new Audio(url);
      currentAudioRef.current = audio;
      audio.onended = () => {
        URL.revokeObjectURL(url);
        addDebug('audio ended → re-listen');
        setStatus('idle');
        if (voiceModeRef.current) setTimeout(startListening, 400);
      };
      audio.onerror = (err) => {
        addDebug(`audio play error: ${err}`);
        setStatus('idle');
        if (voiceModeRef.current) setTimeout(startListening, 400);
      };
      await audio.play();
      addDebug('audio playing…');
    } catch (e) {
      addDebug(`TTS ERROR: ${e.response?.data?.detail || e.message}`);
      setStatus('idle');
      if (voiceModeRef.current) setTimeout(startListening, 400);
    }
  };

  /* ─── main chat send ─── */
  const sendMessage = async (simulate = null, voiceTranscript = null) => {
    const text = voiceTranscript || userInput;
    if (!selectedCampaign || (!text.trim() && !simulate)) return;

    setLoading(true);
    try {
      const payload = {
        campaign_id: selectedCampaign,
        user_input: text || '',
        call_id: currentCallId,
        simulate,
      };
      addDebug(`chat API → "${text.slice(0, 40)}"`);
      const res = await api.post('/test-mode/chat', payload);
      const { call_id, agent_response, should_end_call, conversation_state } = res.data;
      addDebug(`chat API ← "${(agent_response || '').slice(0, 40)}"`);

      setCurrentCallId(call_id);
      setMessages(prev => [
        ...prev,
        { speaker: 'user', text: simulate ? `[${simulate}]` : text },
        { speaker: 'agent', text: agent_response },
      ]);
      setUserInput('');

      if (should_end_call) {
        setCallEnded(true);
        stopVoiceMode();
        return;
      }

      const lang = conversation_state?.language_detected ||
        campaigns.find(c => c.id === selectedCampaign)?.language ||
        'indian_english';

      if (voiceModeRef.current && agent_response) {
        await playAndRelisten(agent_response, lang);
      }

    } catch (e) {
      const errMsg = e.response?.data?.detail || e.message;
      addDebug(`chat API ERROR: ${errMsg}`);
      setVoiceError('Chat error: ' + errMsg);
      setStatus('idle');
      if (voiceModeRef.current) setTimeout(startListening, 500);
    } finally {
      setLoading(false);
    }
  };

  /* ─── toggle voice mode ─── */
  const toggleVoiceMode = async () => {
    if (voiceMode) {
      stopVoiceMode();
    } else {
      setVoiceMode(true);
      voiceModeRef.current = true;
      setVoiceError('');
      await startListening();
    }
  };

  const startNewConversation = () => {
    stopVoiceMode();
    setCurrentCallId(null);
    setMessages([]);
    setCallEnded(false);
    setUserInput('');
    setVoiceError('');
  };

  /* ─── UI helpers ─── */
  const statusLabel = {
    idle: voiceMode ? 'Ready — speak anytime' : 'Ready',
    listening: 'Listening...',
    processing: 'Processing...',
    speaking: 'Agent speaking...',
  }[status];

  const statusColor = {
    idle: voiceMode ? 'text-blue-400' : 'text-slate-400',
    listening: 'text-green-400',
    processing: 'text-yellow-400',
    speaking: 'text-purple-400',
  }[status];

  const dotColor = {
    idle: voiceMode ? 'bg-blue-400' : 'bg-slate-600',
    listening: 'bg-green-400 animate-pulse',
    processing: 'bg-yellow-400 animate-pulse',
    speaking: 'bg-purple-400 animate-pulse',
  }[status];

  const micBtnClass = voiceMode
    ? 'bg-red-600 hover:bg-red-700 text-white shadow-lg shadow-red-900/40'
    : 'bg-blue-600 hover:bg-blue-700 text-white';

  return (
    <div className="min-h-screen bg-slate-900">
      <Navbar />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-white mb-1">Test Mode</h1>
          <p className="text-slate-400">Simulate a real sales call with your AI agent</p>
        </div>

        {/* ── Top bar ── */}
        <div className="bg-slate-800 rounded-lg border border-slate-700 p-5 mb-4">
          <div className="flex items-center gap-4 mb-4">
            <label className="text-sm font-medium text-slate-300 whitespace-nowrap">Campaign:</label>
            <select
              value={selectedCampaign || ''}
              onChange={e => setSelectedCampaign(e.target.value)}
              className="flex-1 px-3 py-2 bg-slate-700 border border-slate-600 rounded-md text-white"
              disabled={!!currentCallId}
            >
              <option value="">Select a campaign</option>
              {campaigns.map(c => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.language.replace('_', ' ')})
                </option>
              ))}
            </select>
            {currentCallId && (
              <button onClick={startNewConversation}
                className="bg-slate-700 text-white px-4 py-2 rounded-md hover:bg-slate-600 whitespace-nowrap">
                New Conversation
              </button>
            )}
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${dotColor}`} />
              <span className={`text-sm font-medium ${statusColor}`}>{statusLabel}</span>
            </div>
            {voiceEnabled && micPermission && (
              <span className="text-xs text-green-400">🎤 Voice ready</span>
            )}
            {voiceError && <span className="text-xs text-yellow-400">{voiceError}</span>}
          </div>

          {/* Live voice debug panel — helps diagnose voice mode without DevTools */}
          {(voiceMode || debugLog.length > 0) && (
            <div className="mt-3 p-3 bg-slate-900/60 border border-slate-700 rounded text-xs font-mono space-y-1">
              <div className="flex items-center justify-between">
                <div className="text-slate-400">
                  state: <span className="text-cyan-300">status={status}</span>{' '}
                  <span className="text-cyan-300">voiceMode={String(voiceMode)}</span>{' '}
                  <span className="text-cyan-300">loading={String(loading)}</span>{' '}
                  <span className="text-cyan-300">msgs={messages.length}</span>{' '}
                  <span className="text-cyan-300">callId={currentCallId ? currentCallId.slice(0, 8) : 'null'}</span>
                </div>
                <button
                  onClick={forceReset}
                  className="text-xs bg-red-700 hover:bg-red-600 text-white px-2 py-0.5 rounded ml-2"
                >
                  Force Reset
                </button>
              </div>
              <div className="text-slate-400">
                Last heard: <span className="text-cyan-300">{lastTranscript || '(nothing yet)'}</span>
              </div>
              <div className="text-slate-500 max-h-64 overflow-y-auto border-t border-slate-700 pt-1">
                {debugLog.length === 0
                  ? <div className="italic">waiting for events…</div>
                  : debugLog.map((line, i) => <div key={i}>{line}</div>)
                }
              </div>
            </div>
          )}
        </div>

        {/* ── Chat window ── */}
        {selectedCampaign && (
          <div className="bg-slate-800 rounded-lg border border-slate-700 flex flex-col" style={{ height: '520px' }}>

            {/* messages */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {messages.length === 0 ? (
                <div className="text-center text-slate-400 py-16">
                  {voiceEnabled && micPermission
                    ? <><p className="text-lg mb-2">🎤 Click the microphone to start</p>
                        <p className="text-sm">The AI will listen, respond, then listen again automatically</p></>
                    : <><p>Type a message to start the conversation</p>
                        <p className="text-sm mt-1">The AI agent will respond based on your campaign</p></>
                  }
                </div>
              ) : (
                messages.map((msg, i) => (
                  <div key={i} className={`flex ${msg.speaker === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-xs lg:max-w-md px-4 py-3 rounded-2xl text-sm ${
                      msg.speaker === 'user'
                        ? 'bg-blue-600 text-white rounded-br-sm'
                        : 'bg-slate-700 text-slate-100 rounded-bl-sm'
                    }`}>
                      {msg.text}
                    </div>
                  </div>
                ))
              )}
              {callEnded && (
                <div className="text-center py-4">
                  <span className="bg-green-900/30 text-green-400 px-6 py-2 rounded-full text-sm">
                    ✓ Call Ended
                  </span>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* ── Voice visualizer ── */}
            {voiceMode && status === 'listening' && (
              <div className="px-6 py-2 flex items-center justify-center gap-1">
                {[...Array(12)].map((_, i) => (
                  <div key={i}
                    className="bg-green-400 rounded-full w-1 transition-all duration-75"
                    style={{ height: `${8 + (volume * (0.5 + Math.sin(i) * 0.5))}px`, opacity: 0.7 + i * 0.02 }}
                  />
                ))}
              </div>
            )}

            {/* ── Input bar ── */}
            <div className="border-t border-slate-700 p-4 space-y-3">

              {/* simulate buttons */}
              <div className="flex gap-2">
                <button onClick={() => sendMessage('silence')}
                  disabled={loading || callEnded || !currentCallId}
                  className="text-xs bg-slate-700 text-slate-300 px-3 py-1 rounded hover:bg-slate-600 disabled:opacity-40">
                  Simulate Silence
                </button>
                <button onClick={() => sendMessage('interruption')}
                  disabled={loading || callEnded || !currentCallId}
                  className="text-xs bg-slate-700 text-slate-300 px-3 py-1 rounded hover:bg-slate-600 disabled:opacity-40">
                  Simulate Interruption
                </button>
              </div>

              <div className="flex gap-3 items-center">

                {/* Mic toggle button */}
                {voiceEnabled && micPermission && (
                  <button
                    onClick={toggleVoiceMode}
                    disabled={callEnded}
                    className={`w-12 h-12 rounded-full flex items-center justify-center text-xl transition-all ${micBtnClass} disabled:opacity-40`}
                    title={voiceMode ? 'Stop voice mode' : 'Start voice conversation'}
                  >
                    {voiceMode ? '⏹' : '🎤'}
                  </button>
                )}

                {/* Text input */}
                <input
                  type="text"
                  value={userInput}
                  onChange={e => setUserInput(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
                  }}
                  placeholder={voiceEnabled && micPermission ? 'Or type here...' : 'Type your message...'}
                  disabled={loading || callEnded || status === 'speaking'}
                  className="flex-1 px-4 py-2.5 bg-slate-700 border border-slate-600 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                />

                <button
                  onClick={() => sendMessage()}
                  disabled={loading || callEnded || !userInput.trim() || status === 'speaking'}
                  className="bg-blue-600 text-white px-5 py-2.5 rounded-xl hover:bg-blue-700 disabled:opacity-40 font-medium"
                >
                  Send
                </button>
              </div>

              {voiceEnabled && micPermission && (
                <p className="text-xs text-slate-500 text-center">
                  {voiceMode
                    ? '🟢 Voice mode ON — speak naturally, AI will respond and listen again automatically'
                    : 'Click 🎤 to start a hands-free voice conversation'}
                </p>
              )}
            </div>
          </div>
        )}

        {campaigns.length === 0 && (
          <div className="text-center py-12 bg-slate-800 rounded-lg border border-slate-700">
            <p className="text-slate-400 mb-4">No campaigns yet</p>
            <button onClick={() => window.location.href = '/campaigns/create'}
              className="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700">
              Create a Campaign
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default TestMode;
