import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import api from '../utils/api';

const CampaignList = () => {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetchCampaigns();
  }, []);

  const fetchCampaigns = async () => {
    try {
      const response = await api.get('/campaigns');
      setCampaigns(response.data);
    } catch (error) {
      console.error('Error fetching campaigns:', error);
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
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">Campaigns</h1>
            <p className="text-slate-400">Manage your voice sales campaigns</p>
          </div>
          <button
            onClick={() => navigate('/campaigns/create')}
            className="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700"
            data-testid="create-campaign-btn"
          >
            Create Campaign
          </button>
        </div>

        {campaigns.length === 0 ? (
          <div className="bg-slate-800 rounded-lg p-12 border border-slate-700 text-center">
            <p className="text-slate-400 mb-4">No campaigns yet</p>
            <button
              onClick={() => navigate('/campaigns/create')}
              className="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700"
              data-testid="create-first-campaign-btn"
            >
              Create Your First Campaign
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {campaigns.map((campaign) => (
              <div
                key={campaign.id}
                onClick={() => navigate(`/campaign/${campaign.id}`)}
                className="bg-slate-800 rounded-lg p-6 border border-slate-700 hover:border-slate-600 transition-colors cursor-pointer"
                data-testid="campaign-card"
              >
                <h3 className="text-xl font-bold text-white mb-2">{campaign.name}</h3>
                <p className="text-slate-400 text-sm mb-4 line-clamp-2">{campaign.goal}</p>
                <div className="flex justify-between items-center mb-4">
                  <span className="text-slate-500 text-sm capitalize">
                    {campaign.language.replace('_', ' ')}
                  </span>
                  <span className="text-green-400 text-sm">{campaign.status}</span>
                </div>
                <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                  <button
                    onClick={() => navigate(`/campaigns/${campaign.id}/leads`)}
                    className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 text-sm"
                  >
                    Manage Leads
                  </button>
                  <button
                    onClick={() => navigate(`/campaigns/${campaign.id}/analytics`)}
                    className="flex-1 bg-slate-700 text-white px-4 py-2 rounded-md hover:bg-slate-600 text-sm"
                  >
                    Analytics
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default CampaignList;