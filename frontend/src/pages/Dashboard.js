import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import api from '../utils/api';

const Dashboard = () => {
  const [campaigns, setCampaigns] = useState([]);
  const [calls, setCalls] = useState([]);
  const [leads, setLeads] = useState([]);
  const [stats, setStats] = useState({
    totalCampaigns: 0,
    totalCalls: 0,
    totalLeads: 0,
    completedCalls: 0,
    interestedLeads: 0
  });
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [campaignsRes, callsRes, leadsRes] = await Promise.all([
        api.get('/campaigns'),
        api.get('/calls'),
        api.get('/leads')
      ]);
      
      setCampaigns(campaignsRes.data);
      setCalls(callsRes.data);
      setLeads(leadsRes.data);
      
      // Calculate stats
      const completedCalls = callsRes.data.filter(c => c.status === 'completed').length;
      const interestedLeads = leadsRes.data.filter(l => l.status === 'interested').length;
      
      setStats({
        totalCampaigns: campaignsRes.data.length,
        totalCalls: callsRes.data.length,
        totalLeads: leadsRes.data.length,
        completedCalls,
        interestedLeads
      });
    } catch (error) {
      console.error('Error fetching data:', error);
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

  return (
    <div className="min-h-screen bg-slate-900">
      <Navbar />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Dashboard</h1>
          <p className="text-slate-400">Welcome to your Voice Sales Agent dashboard</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h3 className="text-slate-400 text-sm font-medium">Total Campaigns</h3>
            <p className="text-3xl font-bold text-white mt-2" data-testid="total-campaigns">{stats.totalCampaigns}</p>
            <p className="text-slate-500 text-xs mt-2">Active campaigns</p>
          </div>
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h3 className="text-slate-400 text-sm font-medium">Total Calls</h3>
            <p className="text-3xl font-bold text-white mt-2" data-testid="total-calls">{stats.totalCalls}</p>
            <p className="text-slate-500 text-xs mt-2">{stats.completedCalls} completed</p>
          </div>
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h3 className="text-slate-400 text-sm font-medium">Total Leads</h3>
            <p className="text-3xl font-bold text-white mt-2" data-testid="total-leads">{stats.totalLeads}</p>
            <p className="text-slate-500 text-xs mt-2">{stats.interestedLeads} interested</p>
          </div>
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h3 className="text-slate-400 text-sm font-medium">Completion Rate</h3>
            <p className="text-3xl font-bold text-white mt-2">
              {stats.totalCalls > 0 ? Math.round((stats.completedCalls / stats.totalCalls) * 100) : 0}%
            </p>
            <p className="text-slate-500 text-xs mt-2">Call success rate</p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-white">Recent Campaigns</h2>
              <button
                onClick={() => navigate('/campaigns/create')}
                className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm hover:bg-blue-700"
                data-testid="create-campaign-btn"
              >
                Create Campaign
              </button>
            </div>
            {campaigns.length === 0 ? (
              <p className="text-slate-400 text-sm">No campaigns yet. Create your first campaign!</p>
            ) : (
              <div className="space-y-3">
                {campaigns.slice(0, 5).map((campaign) => (
                  <div 
                    key={campaign.id} 
                    className="bg-slate-700 p-4 rounded-md hover:bg-slate-600 cursor-pointer transition-colors" 
                    onClick={() => navigate(`/campaign/${campaign.id}`)}
                    data-testid="campaign-item"
                  >
                    <h3 className="text-white font-medium">{campaign.name}</h3>
                    <p className="text-slate-400 text-sm mt-1 capitalize">{campaign.language.replace('_', ' ')}</p>
                  </div>
                ))}
                {campaigns.length > 5 && (
                  <button
                    onClick={() => navigate('/campaigns')}
                    className="text-blue-400 hover:text-blue-300 text-sm"
                  >
                    View all {campaigns.length} campaigns →
                  </button>
                )}
              </div>
            )}
          </div>

          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-white">Recent Calls</h2>
              <button
                onClick={() => navigate('/test-mode')}
                className="bg-green-600 text-white px-4 py-2 rounded-md text-sm hover:bg-green-700"
                data-testid="test-mode-btn"
              >
                Test Mode
              </button>
            </div>
            {calls.length === 0 ? (
              <p className="text-slate-400 text-sm">No calls yet. Try Test Mode!</p>
            ) : (
              <div className="space-y-3">
                {calls.slice(0, 5).map((call) => (
                  <div 
                    key={call.id} 
                    className="bg-slate-700 p-4 rounded-md hover:bg-slate-600 cursor-pointer transition-colors" 
                    onClick={() => navigate(`/calls/${call.id}`)}
                    data-testid="call-item"
                  >
                    <div className="flex justify-between items-center">
                      <div>
                        <span className="text-white text-sm capitalize">{call.status}</span>
                        <p className="text-slate-400 text-xs mt-1">
                          {new Date(call.started_at).toLocaleString()}
                        </p>
                      </div>
                      <span className="text-slate-400 text-sm">{formatDuration(call.duration)}</span>
                    </div>
                  </div>
                ))}
                {calls.length > 5 && (
                  <button
                    onClick={() => navigate('/calls')}
                    className="text-blue-400 hover:text-blue-300 text-sm"
                  >
                    View all {calls.length} calls →
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {campaigns.length === 0 && (
          <div className="bg-blue-900/20 border border-blue-800 rounded-lg p-8 mt-8">
            <h3 className="text-xl font-bold text-white mb-4">Get Started</h3>
            <p className="text-slate-300 mb-6">
              Welcome to Voice Sales Agent! Start by creating your first campaign to begin qualifying leads 
              with our AI-powered voice agent.
            </p>
            <div className="flex gap-4">
              <button
                onClick={() => navigate('/campaigns/create')}
                className="bg-blue-600 text-white px-6 py-3 rounded-md hover:bg-blue-700 font-medium"
              >
                Create First Campaign
              </button>
              <button
                onClick={() => navigate('/test-mode')}
                className="bg-slate-700 text-white px-6 py-3 rounded-md hover:bg-slate-600 font-medium"
              >
                Try Test Mode
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;