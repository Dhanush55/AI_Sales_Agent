import React, { useEffect, useState, useRef } from 'react';
import Navbar from '../components/Navbar';
import api from '../utils/api';

const TestMode = () => {
  const [campaigns, setCampaigns] = useState([]);
  const [selectedCampaign, setSelectedCampaign] = useState(null);
  const [currentCallId, setCurrentCallId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [userInput, setUserInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [callEnded, setCallEnded] = useState(false);
  
  // Voice-related states
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [voiceError, setVoiceError] = useState('');
  const [micPermission, setMicPermission] = useState(null);
  
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const audioRef = useRef(null);

  useEffect(() => {
    fetchCampaigns();
    checkVoiceStatus();
    checkMicPermission();
  }, []);

  const checkVoiceStatus = async () => {
    try {
      const response = await api.get('/voice/status');
      setVoiceEnabled(response.data.voice_enabled);
      if (!response.data.voice_enabled) {
        setVoiceError('Voice services not configured. Using text mode.');
      }
    } catch (error) {
      console.error('Error checking voice status:', error);
      setVoiceError('Voice services unavailable. Using text mode.');
    }
  };

  const checkMicPermission = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach(track => track.stop());
      setMicPermission(true);
    } catch (error) {
      console.log('Microphone permission denied or unavailable');
      setMicPermission(false);
      setVoiceError('Microphone access denied. Using text mode.');
    }
  };

  const fetchCampaigns = async () => {
    try {
      const response = await api.get('/campaigns');
      setCampaigns(response.data);
      if (response.data.length > 0) {
        setSelectedCampaign(response.data[0].id);
      }
    } catch (error) {
      console.error('Error fetching campaigns:', error);
    }
  };

  const startNewConversation = () => {
    setCurrentCallId(null);
    setMessages([]);
    setCallEnded(false);
    setUserInput('');
    setVoiceError('');
  };

  const startRecording = async () => {
    if (!selectedCampaign || callEnded || isSpeaking) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        await processVoiceInput(audioBlob);
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (error) {
      console.error('Error starting recording:', error);
      setVoiceError('Failed to start recording. Using text mode.');
      setMicPermission(false);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const processVoiceInput = async (audioBlob) => {
    setLoading(true);
    try {
      // Send audio to STT
      const formData = new FormData();
      formData.append('audio', audioBlob, 'recording.wav');
      
      const sttResponse = await api.post('/voice/stt', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      const transcribedText = sttResponse.data.text;
      
      // Send transcribed text to chat endpoint
      await sendMessage(null, transcribedText);
      
    } catch (error) {
      console.error('Error processing voice input:', error);
      setVoiceError('Voice processing failed. Please use text input.');
    } finally {
      setLoading(false);
    }
  };

  const playAgentResponse = async (text, language) => {
    if (!voiceEnabled) return;

    try {
      setIsSpeaking(true);
      
      const response = await api.post('/voice/tts', {
        text,
        language: language || 'indian_english'
      }, {
        responseType: 'blob'
      });

      const audioUrl = URL.createObjectURL(response.data);
      const audio = new Audio(audioUrl);
      audioRef.current = audio;

      audio.onended = () => {
        setIsSpeaking(false);
        URL.revokeObjectURL(audioUrl);
      };

      await audio.play();
    } catch (error) {
      console.error('Error playing agent response:', error);
      setIsSpeaking(false);
    }
  };

  const sendMessage = async (simulate = null) => {
    if (!selectedCampaign || (!userInput.trim() && !simulate)) return;

    setLoading(true);
    try {
      const payload = {
        campaign_id: selectedCampaign,
        user_input: userInput || '',
        call_id: currentCallId,
        simulate: simulate
      };

      const response = await api.post('/test-mode/chat', payload);
      const { call_id, agent_response, should_end_call } = response.data;

      setCurrentCallId(call_id);
      
      if (!simulate) {
        setMessages(prev => [
          ...prev,
          { speaker: 'user', text: userInput },
          { speaker: 'agent', text: agent_response }
        ]);
      } else {
        setMessages(prev => [
          ...prev,
          { speaker: 'user', text: `[${simulate}]` },
          { speaker: 'agent', text: agent_response }
        ]);
      }

      setUserInput('');

      if (should_end_call) {
        setCallEnded(true);
      }
    } catch (error) {
      console.error('Error sending message:', error);
      alert('Failed to send message. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="min-h-screen bg-slate-900">
      <Navbar />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Test Mode</h1>
          <p className="text-slate-400">Test your voice agent in a simulated conversation</p>
        </div>

        <div className="bg-slate-800 rounded-lg border border-slate-700 p-6 mb-6">
          <div className="flex items-center gap-4 mb-4">
            <label className="text-sm font-medium text-slate-300">
              Campaign:
            </label>
            <select
              value={selectedCampaign || ''}
              onChange={(e) => setSelectedCampaign(e.target.value)}
              className="flex-1 px-3 py-2 bg-slate-700 border border-slate-600 rounded-md text-white"
              disabled={currentCallId !== null}
              data-testid="campaign-select"
            >
              <option value="">Select a campaign</option>
              {campaigns.map((campaign) => (
                <option key={campaign.id} value={campaign.id}>
                  {campaign.name} ({campaign.language.replace('_', ' ')})
                </option>
              ))}
            </select>
            {currentCallId && (
              <button
                onClick={startNewConversation}
                className="bg-slate-700 text-white px-4 py-2 rounded-md hover:bg-slate-600"
                data-testid="new-conversation-btn"
              >
                New Conversation
              </button>
            )}
          </div>

          {campaigns.length === 0 && (
            <div className="text-center py-8">
              <p className="text-slate-400 mb-4">No campaigns available</p>
              <button
                onClick={() => window.location.href = '/campaigns/create'}
                className="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700"
                data-testid="create-campaign-link"
              >
                Create a Campaign
              </button>
            </div>
          )}
        </div>

        {selectedCampaign && (
          <div className="bg-slate-800 rounded-lg border border-slate-700">
            <div className="h-96 overflow-y-auto p-6 space-y-4" data-testid="chat-container">
              {messages.length === 0 ? (
                <div className="text-center text-slate-400 py-12">
                  <p>Start a conversation by typing a message below</p>
                  <p className="text-sm mt-2">The AI agent will respond based on your campaign settings</p>
                </div>
              ) : (
                messages.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`flex ${msg.speaker === 'user' ? 'justify-end' : 'justify-start'}`}
                    data-testid={`message-${msg.speaker}`}
                  >
                    <div
                      className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                        msg.speaker === 'user'
                          ? 'bg-blue-600 text-white'
                          : 'bg-slate-700 text-slate-100'
                      }`}
                    >
                      <p className="text-sm">{msg.text}</p>
                    </div>
                  </div>
                ))
              )}
              {callEnded && (
                <div className="text-center py-4">
                  <div className="inline-block bg-green-900/20 text-green-400 px-6 py-3 rounded-lg" data-testid="call-ended-message">
                    Call Ended
                  </div>
                </div>
              )}
            </div>

            <div className="border-t border-slate-700 p-4">
              <div className="flex gap-2 mb-3">
                <button
                  onClick={() => sendMessage('silence')}
                  disabled={loading || callEnded || !currentCallId}
                  className="text-xs bg-slate-700 text-slate-300 px-3 py-1 rounded hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed"
                  data-testid="simulate-silence-btn"
                >
                  Simulate Silence
                </button>
                <button
                  onClick={() => sendMessage('interruption')}
                  disabled={loading || callEnded || !currentCallId}
                  className="text-xs bg-slate-700 text-slate-300 px-3 py-1 rounded hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed"
                  data-testid="simulate-interruption-btn"
                >
                  Simulate Interruption
                </button>
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={userInput}
                  onChange={(e) => setUserInput(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Type your message..."
                  disabled={loading || callEnded}
                  className="flex-1 px-4 py-2 bg-slate-700 border border-slate-600 rounded-md text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                  data-testid="user-input"
                />
                <button
                  onClick={() => sendMessage()}
                  disabled={loading || callEnded || !userInput.trim()}
                  className="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  data-testid="send-message-btn"
                >
                  {loading ? 'Sending...' : 'Send'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TestMode;