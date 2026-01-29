import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import api from '../utils/api';

const LeadsList = () => {
  const { campaignId } = useParams();
  const [campaign, setCampaign] = useState(null);
  const [leads, setLeads] = useState([]);
  const [showAddLead, setShowAddLead] = useState(false);
  const [showBulkImport, setShowBulkImport] = useState(false);
  const [formData, setFormData] = useState({ name: '', phone: '' });
  const [csvFile, setCsvFile] = useState(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetchData();
  }, [campaignId]);

  const fetchData = async () => {
    try {
      const [campaignRes, leadsRes] = await Promise.all([
        api.get(`/campaigns/${campaignId}`),
        api.get(`/leads?campaign_id=${campaignId}`)
      ]);
      setCampaign(campaignRes.data);
      setLeads(leadsRes.data);
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddLead = async (e) => {
    e.preventDefault();
    try {
      await api.post('/leads', {
        ...formData,
        campaign_id: campaignId
      });
      setFormData({ name: '', phone: '' });
      setShowAddLead(false);
      fetchData();
    } catch (error) {
      console.error('Error adding lead:', error);
    }
  };

  const handleBulkImport = async (e) => {
    e.preventDefault();
    if (!csvFile) return;

    setImporting(true);
    try {
      const formData = new FormData();
      formData.append('file', csvFile);

      const response = await api.post(`/leads/bulk-import?campaign_id=${campaignId}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      setImportResult(response.data);
      setCsvFile(null);
      fetchData();
    } catch (error) {
      console.error('Error importing leads:', error);
      alert('Failed to import leads. Please check CSV format.');
    } finally {
      setImporting(false);
    }
  };

  const downloadSampleCSV = () => {
    const csvContent = 'name,phone\nJohn Doe,+919876543210\nJane Smith,+919876543211';
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'sample_leads.csv';
    a.click();
    window.URL.revokeObjectURL(url);
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
          <button
            onClick={() => navigate('/campaigns')}
            className="text-blue-400 hover:text-blue-300 mb-4"
            data-testid="back-to-campaigns-btn"
          >
            ← Back to Campaigns
          </button>
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-white mb-2">{campaign?.name}</h1>
              <p className="text-slate-400">Manage leads for this campaign</p>
            </div>
            <button
              onClick={() => setShowAddLead(true)}
              className="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700"
              data-testid="add-lead-btn"
            >
              Add Lead
            </button>
          </div>
        </div>

        {showAddLead && (
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 mb-6">
            <h3 className="text-white font-bold mb-4">Add New Lead</h3>
            <form onSubmit={handleAddLead} className="space-y-4" data-testid="add-lead-form">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Name
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-md text-white"
                    data-testid="lead-name-input"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Phone Number
                  </label>
                  <input
                    type="tel"
                    required
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-md text-white"
                    data-testid="lead-phone-input"
                  />
                </div>
              </div>
              <div className="flex gap-4">
                <button
                  type="submit"
                  className="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700"
                  data-testid="submit-lead-btn"
                >
                  Add Lead
                </button>
                <button
                  type="button"
                  onClick={() => setShowAddLead(false)}
                  className="bg-slate-700 text-white px-6 py-2 rounded-md hover:bg-slate-600"
                  data-testid="cancel-lead-btn"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        {leads.length === 0 ? (
          <div className="bg-slate-800 rounded-lg p-12 border border-slate-700 text-center">
            <p className="text-slate-400">No leads yet. Add your first lead!</p>
          </div>
        ) : (
          <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-700">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">
                    Name
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">
                    Phone
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">
                    Created
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700">
                {leads.map((lead) => (
                  <tr key={lead.id} data-testid="lead-row">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-white">
                      {lead.name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                      {lead.phone}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-slate-700 text-slate-300">
                        {lead.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-400">
                      {new Date(lead.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default LeadsList;