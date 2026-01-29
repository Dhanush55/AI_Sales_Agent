import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import api from '../utils/api';

const Dashboard = () => {
  const [campaigns, setCampaigns] = useState([]);
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [campaignsRes, callsRes] = await Promise.all([
        api.get('/campaigns'),
        api.get('/calls')
      ]);
      setCampaigns(campaignsRes.data);
      setCalls(callsRes.data.slice(0, 5));
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
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

  return (
    <div className="min-h-screen bg-slate-900">
      <Navbar />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Dashboard</h1>
          <p className="text-slate-400">Welcome to your Voice Sales Agent dashboard</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h3 className="text-slate-400 text-sm font-medium">Total Campaigns</h3>
            <p className="text-3xl font-bold text-white mt-2" data-testid="total-campaigns">{campaigns.length}</p>
          </div>
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h3 className="text-slate-400 text-sm font-medium">Total Calls</h3>
            <p className="text-3xl font-bold text-white mt-2" data-testid="total-calls">{calls.length}</p>
          </div>
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h3 className="text-slate-400 text-sm font-medium">Active Leads</h3>
            <p className="text-3xl font-bold text-white mt-2">-</p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-white">Campaigns</h2>
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
                  <div key={campaign.id} className="bg-slate-700 p-4 rounded-md" data-testid="campaign-item">
                    <h3 className="text-white font-medium">{campaign.name}</h3>
                    <p className="text-slate-400 text-sm mt-1">{campaign.language.replace('_', ' ')}</p>
                  </div>
                ))}
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
                {calls.map((call) => (
                  <div key={call.id} className="bg-slate-700 p-4 rounded-md" data-testid="call-item">
                    <div className="flex justify-between">
                      <span className="text-white text-sm">{call.status}</span>
                      <span className="text-slate-400 text-sm">{call.duration}s</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;