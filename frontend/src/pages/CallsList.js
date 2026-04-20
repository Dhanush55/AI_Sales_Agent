import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import api from '../utils/api';

const sourceStyles = {
  test: 'bg-slate-700 text-slate-300',
  manual: 'bg-blue-900/40 text-blue-300',
  dialer: 'bg-purple-900/40 text-purple-300',
};

const CallsList = () => {
  const [calls, setCalls] = useState([]);
  const [campaigns, setCampaigns] = useState([]);
  const [selectedCampaign, setSelectedCampaign] = useState('all');
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const refreshRef = useRef(null);

  const fetchCalls = async (campaignId = selectedCampaign) => {
    try {
      const url = campaignId === 'all' ? '/calls' : `/calls?campaign_id=${campaignId}`;
      const response = await api.get(url);
      setCalls(response.data);
    } catch (err) {
      console.error('Error fetching calls:', err);
    }
  };

  useEffect(() => {
    (async () => {
      try {
        const [c, _] = await Promise.all([api.get('/campaigns'), fetchCalls('all')]);
        setCampaigns(c.data);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    fetchCalls(selectedCampaign);
  }, [selectedCampaign]);

  useEffect(() => {
    refreshRef.current = setInterval(() => fetchCalls(), 15000);
    return () => clearInterval(refreshRef.current);
  }, [selectedCampaign]);

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return 'bg-green-900/30 text-green-400';
      case 'in_progress': return 'bg-blue-900/30 text-blue-400';
      case 'failed': return 'bg-red-900/30 text-red-400';
      default: return 'bg-slate-700 text-slate-300';
    }
  };

  const formatDuration = (seconds) => {
    if (!seconds) return 'N/A';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  };

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
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Calls</h1>
          <p className="text-slate-400">View all calls and their details (auto-refreshes every 15s)</p>
        </div>

        <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 mb-6">
          <div className="flex items-center gap-4">
            <label className="text-sm font-medium text-slate-300">Filter by Campaign:</label>
            <select
              value={selectedCampaign}
              onChange={(e) => setSelectedCampaign(e.target.value)}
              className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-md text-white"
              data-testid="campaign-filter"
            >
              <option value="all">All Campaigns</option>
              {campaigns.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
        </div>

        {calls.length === 0 ? (
          <div className="bg-slate-800 rounded-lg p-12 border border-slate-700 text-center">
            <p className="text-slate-400 mb-4">No calls yet</p>
            <button
              onClick={() => navigate('/test-mode')}
              className="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700"
              data-testid="go-to-test-mode-btn"
            >
              Try Test Mode
            </button>
          </div>
        ) : (
          <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-700">
                <tr>
                  <Th>Call ID</Th><Th>Source</Th><Th>Status</Th><Th>Duration</Th><Th>Started</Th><Th>Action</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700">
                {calls.map((call) => {
                  const src = call.call_source || 'test';
                  return (
                    <tr key={call.id} data-testid="call-row" className="hover:bg-slate-700/50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-white font-mono">
                        {call.id.substring(0, 8)}...
                      </td>
                      <td className="px-6 py-4">
                        <span className={`px-2 py-1 text-xs rounded-full capitalize ${sourceStyles[src]}`} data-testid="call-source-badge">
                          {src === 'dialer' ? 'Auto-Dialer' : src}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          {call.status === 'in_progress' && (
                            <span className="flex items-center gap-1" data-testid="live-indicator">
                              <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                              <span className="text-xs text-green-400">Live</span>
                            </span>
                          )}
                          <span className={`px-2 py-1 text-xs rounded-full ${getStatusColor(call.status)}`}>
                            {call.status}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-300">{formatDuration(call.duration)}</td>
                      <td className="px-6 py-4 text-sm text-slate-400">
                        {new Date(call.started_at).toLocaleString()}
                      </td>
                      <td className="px-6 py-4 text-sm">
                        <button
                          onClick={() => navigate(`/calls/${call.id}`)}
                          className="text-blue-400 hover:text-blue-300"
                          data-testid="view-call-btn"
                        >
                          View Details
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

const Th = ({ children }) => (
  <th className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">
    {children}
  </th>
);

export default CallsList;
