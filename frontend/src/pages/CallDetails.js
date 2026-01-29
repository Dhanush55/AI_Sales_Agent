import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import api from '../utils/api';

const CallDetails = () => {
  const { callId } = useParams();
  const [call, setCall] = useState(null);
  const [conversationState, setConversationState] = useState(null);
  const [outcome, setOutcome] = useState(null);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetchCallDetails();
  }, [callId]);

  const fetchCallDetails = async () => {
    try {
      const callRes = await api.get(`/calls/${callId}`);
      setCall(callRes.data);

      // Fetch conversation state
      try {
        const stateRes = await api.get(`/conversation-states?call_id=${callId}`);
        if (stateRes.data && stateRes.data.length > 0) {
          setConversationState(stateRes.data[0]);
        }
      } catch (err) {
        console.log('No conversation state found');
      }

      // Fetch outcome
      try {
        const outcomeRes = await api.get(`/calls/${callId}/outcome`);
        setOutcome(outcomeRes.data);
      } catch (err) {
        console.log('No outcome found');
      }

      // Fetch summary
      try {
        const summaryRes = await api.get(`/calls/${callId}/summary`);
        setSummary(summaryRes.data);
      } catch (err) {
        console.log('No summary found');
      }
    } catch (error) {
      console.error('Error fetching call details:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatDuration = (seconds) => {
    if (!seconds) return 'N/A';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  };

  const getOutcomeColor = (outcome) => {
    switch (outcome) {
      case 'interested':
        return 'text-green-400';
      case 'not_interested':
        return 'text-red-400';
      case 'callback_scheduled':
        return 'text-blue-400';
      case 'busy':
        return 'text-yellow-400';
      default:
        return 'text-slate-400';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-900">
        <Navbar />
        <div className="flex items-center justify-center h-96">
          <div className="text-white">Loading...</div>
        </div>
      </div>
    );
  }

  if (!call) {
    return (
      <div className="min-h-screen bg-slate-900">
        <Navbar />
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center text-slate-400">Call not found</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900">
      <Navbar />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <button
            onClick={() => navigate('/calls')}
            className="text-blue-400 hover:text-blue-300 mb-4"
            data-testid="back-to-calls-btn"
          >
            ← Back to Calls
          </button>
          <h1 className="text-3xl font-bold text-white mb-2">Call Details</h1>
          <p className="text-slate-400">Call ID: {call.id}</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h3 className="text-slate-400 text-sm font-medium mb-2">Status</h3>
            <p className="text-2xl font-bold text-white capitalize">{call.status}</p>
          </div>
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h3 className="text-slate-400 text-sm font-medium mb-2">Duration</h3>
            <p className="text-2xl font-bold text-white">{formatDuration(call.duration)}</p>
          </div>
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h3 className="text-slate-400 text-sm font-medium mb-2">Started</h3>
            <p className="text-sm text-white">{new Date(call.started_at).toLocaleString()}</p>
          </div>
        </div>

        {outcome && (
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 mb-6">
            <h2 className="text-xl font-bold text-white mb-4">Call Outcome</h2>
            <div className="space-y-3">
              <div>
                <span className="text-slate-400 text-sm">Outcome: </span>
                <span className={`font-semibold ${getOutcomeColor(outcome.outcome)}`}>
                  {outcome.outcome.replace('_', ' ').toUpperCase()}
                </span>
              </div>
              <div>
                <span className="text-slate-400 text-sm">Qualified: </span>
                <span className="text-white">{outcome.is_qualified ? 'Yes' : 'No'}</span>
              </div>
              {outcome.notes && (
                <div>
                  <span className="text-slate-400 text-sm">Notes: </span>
                  <span className="text-white">{outcome.notes}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {summary && (
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 mb-6">
            <h2 className="text-xl font-bold text-white mb-4">Call Summary</h2>
            <p className="text-slate-300">{summary.summary_text}</p>
          </div>
        )}

        {conversationState && conversationState.turns && conversationState.turns.length > 0 && (
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h2 className="text-xl font-bold text-white mb-4">Conversation Transcript</h2>
            <div className="space-y-4">
              {conversationState.turns.map((turn, idx) => (
                <div
                  key={idx}
                  className={`flex ${turn.speaker === 'user' ? 'justify-end' : 'justify-start'}`}
                  data-testid={`transcript-${turn.speaker}`}
                >
                  <div
                    className={`max-w-2xl px-4 py-3 rounded-lg ${
                      turn.speaker === 'user'
                        ? 'bg-blue-600 text-white'
                        : 'bg-slate-700 text-slate-100'
                    }`}
                  >
                    <div className="text-xs opacity-75 mb-1">
                      {turn.speaker === 'user' ? 'Customer' : 'Agent'}
                    </div>
                    <p className="text-sm">{turn.text}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default CallDetails;