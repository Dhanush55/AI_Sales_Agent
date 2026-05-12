import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import api from '../utils/api';

const CampaignCreate = () => {
  const [formData, setFormData] = useState({
    name: '',
    goal: '',
    language: 'indian_english',
    product_name: '',
    product_description: '',
    key_features: '',
    pricing: '',
    target_customer: '',
    objection_handling: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // Convert key_features from newline-separated text to array
      const payload = {
        ...formData,
        key_features: formData.key_features
          ? formData.key_features.split('\n').map(f => f.trim()).filter(Boolean)
          : [],
      };
      await api.post('/campaigns', payload);
      navigate('/campaigns');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create campaign');
    } finally {
      setLoading(false);
    }
  };

  const inputClass = "w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-md text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500";
  const labelClass = "block text-sm font-medium text-slate-300 mb-2";

  return (
    <div className="min-h-screen bg-slate-900">
      <Navbar />
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Create Campaign</h1>
          <p className="text-slate-400">Set up a new voice sales campaign with product knowledge</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">

          {/* ── Basic Info ── */}
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 space-y-5">
            <h2 className="text-lg font-semibold text-white">Campaign Info</h2>

            <div>
              <label className={labelClass}>Campaign Name *</label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className={inputClass}
                placeholder="E.g., Solar Panel Outreach Q2"
              />
            </div>

            <div>
              <label className={labelClass}>Campaign Goal *</label>
              <textarea
                required
                value={formData.goal}
                onChange={(e) => setFormData({ ...formData, goal: e.target.value })}
                className={`${inputClass} h-24`}
                placeholder="E.g., Qualify homeowners interested in solar panels and book a site visit"
              />
            </div>

            <div>
              <label className={labelClass}>Language</label>
              <select
                value={formData.language}
                onChange={(e) => setFormData({ ...formData, language: e.target.value })}
                className={inputClass}
              >
                <option value="indian_english">Indian English</option>
                <option value="hindi">Hindi</option>
                <option value="kannada">Kannada</option>
                <option value="tamil">Tamil</option>
                <option value="telugu">Telugu</option>
              </select>
            </div>
          </div>

          {/* ── Product Knowledge ── */}
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 space-y-5">
            <div>
              <h2 className="text-lg font-semibold text-white">Product Knowledge</h2>
              <p className="text-slate-400 text-sm mt-1">The AI agent will use this information when talking to leads</p>
            </div>

            <div>
              <label className={labelClass}>Product Name</label>
              <input
                type="text"
                value={formData.product_name}
                onChange={(e) => setFormData({ ...formData, product_name: e.target.value })}
                className={inputClass}
                placeholder="E.g., SolarMax 5000"
              />
            </div>

            <div>
              <label className={labelClass}>Product Description</label>
              <textarea
                value={formData.product_description}
                onChange={(e) => setFormData({ ...formData, product_description: e.target.value })}
                className={`${inputClass} h-24`}
                placeholder="E.g., Premium rooftop solar panel system for Indian homes. 5kW capacity, 25-year warranty, reduces electricity bill by 90%."
              />
            </div>

            <div>
              <label className={labelClass}>Key Features <span className="text-slate-500 font-normal">(one per line)</span></label>
              <textarea
                value={formData.key_features}
                onChange={(e) => setFormData({ ...formData, key_features: e.target.value })}
                className={`${inputClass} h-28`}
                placeholder={"Zero electricity bill after installation\n5kW capacity\n25-year warranty\nGovernment subsidy available\nInstallation in 2 days"}
              />
            </div>

            <div>
              <label className={labelClass}>Pricing</label>
              <input
                type="text"
                value={formData.pricing}
                onChange={(e) => setFormData({ ...formData, pricing: e.target.value })}
                className={inputClass}
                placeholder="E.g., ₹1.2 lakh installed. EMI from ₹3,500/month. ROI in 3 years."
              />
            </div>

            <div>
              <label className={labelClass}>Target Customer</label>
              <input
                type="text"
                value={formData.target_customer}
                onChange={(e) => setFormData({ ...formData, target_customer: e.target.value })}
                className={inputClass}
                placeholder="E.g., Homeowners with monthly electricity bill above ₹3,000"
              />
            </div>

            <div>
              <label className={labelClass}>Objection Handling</label>
              <textarea
                value={formData.objection_handling}
                onChange={(e) => setFormData({ ...formData, objection_handling: e.target.value })}
                className={`${inputClass} h-24`}
                placeholder="E.g., If they say it's expensive, highlight EMI options and 3-year ROI. If they say they rent, ask if they can speak to the owner."
              />
            </div>
          </div>

          {error && (
            <div className="text-red-400 text-sm bg-red-900/20 p-3 rounded">
              {error}
            </div>
          )}

          <div className="flex gap-4">
            <button
              type="submit"
              disabled={loading}
              className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
            >
              {loading ? 'Creating...' : 'Create Campaign'}
            </button>
            <button
              type="button"
              onClick={() => navigate('/campaigns')}
              className="px-6 bg-slate-700 text-white rounded-md hover:bg-slate-600"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default CampaignCreate;
