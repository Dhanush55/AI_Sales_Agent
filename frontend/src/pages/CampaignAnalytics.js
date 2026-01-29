import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import api from '../utils/api';

const CampaignAnalytics = () => {
  const { campaignId } = useParams();
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetchAnalytics();
  }, [campaignId]);

  const fetchAnalytics = async () => {
    try {
      const response = await api.get(`/analytics/campaign/${campaignId}`);
      setAnalytics(response.data);
    } catch (error) {
      console.error('Error fetching analytics:', error);
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

  if (!analytics) {
    return (
      <div className="min-h-screen bg-slate-900">
        <Navbar />
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center text-slate-400">Analytics not available</div>
        </div>
      </div>
    );
  }

  const { campaign, metrics, lead_status_breakdown, outcome_breakdown } = analytics;

  return (
    <div className="min-h-screen bg-slate-900">
      <Navbar />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <button
            onClick={() => navigate('/campaigns')}
            className="text-blue-400 hover:text-blue-300 mb-4"
            data-testid="back-to-campaigns-btn"
          >
            ← Back to Campaigns
          </button>
          <h1 className="text-3xl font-bold text-white mb-2">{campaign.name} - Analytics</h1>
          <p className="text-slate-400">Campaign performance metrics and insights</p>
        </div>

        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h3 className="text-slate-400 text-sm font-medium">Total Leads</h3>
            <p className="text-3xl font-bold text-white mt-2">{metrics.total_leads}</p>
          </div>
          
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h3 className="text-slate-400 text-sm font-medium">Completed Calls</h3>
            <p className="text-3xl font-bold text-white mt-2">{metrics.completed_calls}</p>
            <p className="text-slate-500 text-xs mt-2">of {metrics.total_calls} total</p>
          </div>
          
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h3 className="text-slate-400 text-sm font-medium">Contact Rate</h3>
            <p className="text-3xl font-bold text-green-400 mt-2">{metrics.contact_rate}%</p>
            <p className="text-slate-500 text-xs mt-2">calls completed</p>
          </div>
          
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h3 className="text-slate-400 text-sm font-medium">Qualification Rate</h3>
            <p className="text-3xl font-bold text-blue-400 mt-2">{metrics.qualification_rate}%</p>
            <p className="text-slate-500 text-xs mt-2">{metrics.qualified_leads} qualified</p>
          </div>
        </div>

        {/* Additional Metrics */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h2 className="text-xl font-bold text-white mb-4">Call Performance</h2>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-slate-300">Average Call Duration</span>
                <span className="text-white font-medium">{Math.floor(metrics.avg_call_duration / 60)}m {Math.floor(metrics.avg_call_duration % 60)}s</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-300">Total Calls Made</span>
                <span className="text-white font-medium">{metrics.total_calls}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-300">Successful Completions</span>
                <span className="text-white font-medium">{metrics.completed_calls}</span>
              </div>
            </div>
          </div>

          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h2 className="text-xl font-bold text-white mb-4">Lead Status Breakdown</h2>
            <div className="space-y-3">
              {Object.entries(lead_status_breakdown).map(([status, count]) => (
                <div key={status} className="flex justify-between items-center">
                  <span className="text-slate-300 capitalize">{status.replace('_', ' ')}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-32 bg-slate-700 rounded-full h-2">
                      <div
                        className="bg-blue-500 h-2 rounded-full"
                        style={{ width: `${(count / metrics.total_leads) * 100}%` }}
                      />
                    </div>
                    <span className="text-white font-medium w-12 text-right">{count}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Call Outcomes */}
        {Object.keys(outcome_breakdown).length > 0 && (
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h2 className="text-xl font-bold text-white mb-4">Call Outcomes</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {Object.entries(outcome_breakdown).map(([outcome, count]) => (
                <div key={outcome} className="bg-slate-700 rounded-lg p-4">
                  <h3 className="text-slate-300 text-sm capitalize mb-2">{outcome.replace('_', ' ')}</h3>
                  <p className="text-2xl font-bold text-white">{count}</p>
                  <p className="text-slate-400 text-xs mt-1">
                    {metrics.completed_calls > 0
                      ? `${Math.round((count / metrics.completed_calls) * 100)}%`
                      : '0%'}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default CampaignAnalytics;
