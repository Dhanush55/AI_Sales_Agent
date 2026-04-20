import React, { useEffect, useState } from 'react';
import Navbar from '../components/Navbar';
import api from '../utils/api';

const Dot = ({ ok }) => (
  <span className={`inline-block w-2.5 h-2.5 rounded-full ${ok ? 'bg-green-500' : 'bg-red-500'}`} />
);

const Settings = () => {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/phone/status')
      .then((r) => setStatus(r.data))
      .catch(() => setStatus(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-900">
        <Navbar />
        <div className="flex items-center justify-center h-96 text-white">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900">
      <Navbar />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h1 className="text-3xl font-bold text-white mb-2">Settings</h1>
        <p className="text-slate-400 mb-8">System configuration overview (read-only)</p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700" data-testid="voice-card">
            <h3 className="text-lg font-bold text-white mb-4">Voice Services</h3>
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-slate-300">STT: <span className="font-mono text-slate-100">{status?.stt_provider}</span></span>
                <Dot ok={status?.voice_enabled} />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-300">TTS: <span className="font-mono text-slate-100">{status?.tts_provider}</span></span>
                <Dot ok={status?.voice_enabled} />
              </div>
            </div>
            <p className="text-xs text-slate-500 mt-4">faster_whisper and edge_tts run locally — no API key needed</p>
          </div>

          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700" data-testid="telephony-card">
            <h3 className="text-lg font-bold text-white mb-4">Telephony</h3>
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-slate-300">Provider: <span className="font-mono text-slate-100">{status?.telephony_provider}</span></span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-300">Status:</span>
                <span className={status?.telephony_configured ? 'text-green-400' : 'text-red-400'}>
                  {status?.telephony_configured ? 'Configured' : 'Not configured'}
                </span>
              </div>
            </div>
            {!status?.telephony_configured && (
              <p className="text-xs text-slate-500 mt-4">Contact your administrator to enable real phone calls</p>
            )}
          </div>

          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700" data-testid="ai-card">
            <h3 className="text-lg font-bold text-white mb-4">AI Engine</h3>
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-slate-300">Model: <span className="font-mono text-slate-100">GPT-4o</span></span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-300">Status:</span>
                <span className="text-green-400">Active</span>
              </div>
            </div>
            <p className="text-xs text-slate-500 mt-4">Powered by Emergent LLM</p>
          </div>
        </div>

        <p className="text-xs text-slate-500 mt-8">All configuration is managed server-side via environment variables.</p>
      </div>
    </div>
  );
};

export default Settings;
