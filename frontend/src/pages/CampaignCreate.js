import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import api from '../utils/api';

const CampaignCreate = () => {
  const [formData, setFormData] = useState({
    name: '',
    goal: '',
    language: 'indian_english'
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await api.post('/campaigns', formData);
      navigate('/campaigns');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create campaign');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900">
      <Navbar />
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Create Campaign</h1>
          <p className="text-slate-400">Set up a new voice sales campaign</p>
        </div>

        <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
          <form onSubmit={handleSubmit} className="space-y-6" data-testid="campaign-form">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Campaign Name
              </label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-md text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="E.g., Tyre Changer Outreach Q1"
                data-testid="campaign-name-input"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Campaign Goal
              </label>
              <textarea
                required
                value={formData.goal}
                onChange={(e) => setFormData({ ...formData, goal: e.target.value })}
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-md text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 h-32"
                placeholder="E.g., Qualify leads for automotive workshop machinery - tyre changers, air compressors, nitrogen systems, wheel balancing equipment"
                data-testid="campaign-goal-input"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Language
              </label>
              <select
                value={formData.language}
                onChange={(e) => setFormData({ ...formData, language: e.target.value })}
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                data-testid="campaign-language-select"
              >
                <option value="indian_english">Indian English</option>
                <option value="hindi">Hindi</option>
                <option value="kannada">Kannada</option>
                <option value="tamil">Tamil</option>
              </select>
            </div>

            {error && (
              <div className="text-red-400 text-sm bg-red-900/20 p-3 rounded" data-testid="error-message">
                {error}
              </div>
            )}

            <div className="flex gap-4">
              <button
                type="submit"
                disabled={loading}
                className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="submit-campaign-btn"
              >
                {loading ? 'Creating...' : 'Create Campaign'}
              </button>
              <button
                type="button"
                onClick={() => navigate('/campaigns')}
                className="px-6 bg-slate-700 text-white rounded-md hover:bg-slate-600"
                data-testid="cancel-btn"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default CampaignCreate;