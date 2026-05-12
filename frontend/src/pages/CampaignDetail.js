import React, { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import api from '../utils/api';

const statusColors = {
  pending: 'bg-slate-600 text-slate-200',
  contacted: 'bg-blue-900/40 text-blue-300',
  interested: 'bg-green-900/40 text-green-300',
  not_interested: 'bg-red-900/40 text-red-300',
  callback: 'bg-yellow-900/40 text-yellow-300',
};

const LANGUAGES = [
  { value: 'indian_english', label: 'Indian English' },
  { value: 'hindi',          label: 'Hindi' },
  { value: 'kannada',        label: 'Kannada' },
  { value: 'tamil',          label: 'Tamil' },
  { value: 'telugu',         label: 'Telugu' },
];

const PAGE = 20;

const CampaignDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [campaign, setCampaign] = useState(null);
  const [leads, setLeads] = useState([]);
  const [phoneStatus, setPhoneStatus] = useState(null);
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [delay, setDelay] = useState(60);
  const [launching, setLaunching] = useState(false);
  const [callingLeadId, setCallingLeadId] = useState(null);
  const [page, setPage] = useState(1);

  /* edit state */
  const [editOpen, setEditOpen] = useState(false);
  const [editForm, setEditForm] = useState({});
  const [editSaving, setEditSaving] = useState(false);

  /* example conversations */
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadSuccess, setUploadSuccess] = useState('');
  const fileInputRef = useRef(null);

  const pollRef = useRef(null);

  const loadAll = async () => {
    const [campRes, leadsRes, psRes] = await Promise.all([
      api.get(`/campaigns/${id}`),
      api.get(`/leads?campaign_id=${id}`),
      api.get('/phone/status'),
    ]);
    setCampaign(campRes.data);
    setLeads(leadsRes.data);
    setPhoneStatus(psRes.data);
    try {
      const sRes = await api.get(`/dialer/campaign/${id}`);
      setSession(sRes.data);
    } catch { setSession(null); }
  };

  useEffect(() => {
    loadAll().finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    pollRef.current = setInterval(async () => {
      try {
        const sRes = await api.get(`/dialer/campaign/${id}`);
        setSession(sRes.data);
        const leadsRes = await api.get(`/leads?campaign_id=${id}`);
        setLeads(leadsRes.data);
      } catch {}
    }, 10000);
    return () => clearInterval(pollRef.current);
  }, [id]);

  const stats = {
    total: leads.length,
    pending: leads.filter(l => l.status === 'pending').length,
    contacted: leads.filter(l => l.status === 'contacted').length,
    interested: leads.filter(l => l.status === 'interested').length,
  };

  /* ── Edit campaign ── */
  const openEdit = () => {
    setEditForm({
      name: campaign.name,
      goal: campaign.goal,
      language: campaign.language,
      product_name: campaign.product_name || '',
      product_description: campaign.product_description || '',
      key_features: (campaign.key_features || []).join('\n'),
      pricing: campaign.pricing || '',
      target_customer: campaign.target_customer || '',
      objection_handling: campaign.objection_handling || '',
    });
    setEditOpen(true);
  };

  const saveEdit = async () => {
    setEditSaving(true);
    try {
      const payload = {
        ...editForm,
        key_features: editForm.key_features
          ? editForm.key_features.split('\n').map(f => f.trim()).filter(Boolean)
          : [],
      };
      await api.patch(`/campaigns/${id}`, payload);
      await loadAll();
      setEditOpen(false);
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed to save');
    } finally {
      setEditSaving(false);
    }
  };

  /* ── Upload example conversation ── */
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    setUploadError('');
    setUploadSuccess('');
    try {
      const fd = new FormData();
      fd.append('file', file);
      await api.post(`/campaigns/${id}/example-conversations`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setUploadSuccess(`✅ "${file.name}" transcribed and saved!`);
      await loadAll();
    } catch (err) {
      setUploadError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const deleteExample = async (exampleId) => {
    if (!window.confirm('Remove this example conversation?')) return;
    await api.delete(`/campaigns/${id}/example-conversations/${exampleId}`);
    await loadAll();
  };

  /* ── Dialer ── */
  const launchDialer = async () => {
    setLaunching(true);
    try {
      await api.post('/dialer/launch', {
        campaign_id: id,
        delay_between_calls_seconds: Math.max(10, Number(delay) || 60),
      });
      await loadAll();
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed to launch dialer');
    } finally { setLaunching(false); }
  };

  const pauseDialer  = async () => { await api.post(`/dialer/${session.id}/pause`);  await loadAll(); };
  const resumeDialer = async () => { await api.post(`/dialer/${session.id}/resume`); await loadAll(); };

  const callNow = async (leadId) => {
    setCallingLeadId(leadId);
    try {
      await api.post(`/phone/call?campaign_id=${id}&lead_id=${leadId}`);
      await loadAll();
    } catch (e) {
      alert(e.response?.data?.detail || 'Call failed');
    } finally { setCallingLeadId(null); }
  };

  if (loading || !campaign) {
    return (
      <div className="min-h-screen bg-slate-900">
        <Navbar />
        <div className="flex items-center justify-center h-96 text-white">Loading...</div>
      </div>
    );
  }

  const pageCount = Math.ceil(leads.length / PAGE);
  const pagedLeads = leads.slice((page - 1) * PAGE, page * PAGE);
  const telConfigured = phoneStatus?.telephony_configured;
  const inputClass = "w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-md text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500";

  return (
    <div className="min-h-screen bg-slate-900">
      <Navbar />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

        <button onClick={() => navigate('/campaigns')}
          className="text-slate-400 hover:text-white mb-4 text-sm">
          ← Back to Campaigns
        </button>

        {/* Header */}
        <div className="mb-6 flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-3xl font-bold text-white">{campaign.name}</h1>
              <span className="px-3 py-1 text-xs rounded-full bg-slate-700 text-slate-200 capitalize">
                {campaign.language.replace('_', ' ')}
              </span>
            </div>
            <p className="text-slate-400">{campaign.goal}</p>
          </div>
          <button onClick={openEdit}
            className="bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-md text-sm">
            ✏️ Edit Campaign
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <StatCard label="Total Leads"  value={stats.total} />
          <StatCard label="Pending"      value={stats.pending} />
          <StatCard label="Contacted"    value={stats.contacted} />
          <StatCard label="Interested"   value={stats.interested} />
        </div>

        {/* ── Example Conversations ── */}
        <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 mb-6">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-xl font-bold text-white">🎙️ Example Conversations</h2>
              <p className="text-slate-400 text-sm mt-1">
                Upload recordings of your best sales calls — the AI will study and mimic your style
              </p>
            </div>
            <label className={`cursor-pointer px-4 py-2 rounded-md text-sm font-medium text-white ${uploading ? 'bg-slate-600' : 'bg-blue-600 hover:bg-blue-700'}`}>
              {uploading ? 'Transcribing...' : '+ Upload Recording'}
              <input
                ref={fileInputRef}
                type="file"
                accept="audio/*,video/*,.mp3,.wav,.m4a,.ogg,.webm,.mpeg,.mpg,.mp4,.opus,.aac,.flac"
                className="hidden"
                onChange={handleFileUpload}
                disabled={uploading}
              />
            </label>
          </div>

          {uploadSuccess && <p className="text-green-400 text-sm mb-3">{uploadSuccess}</p>}
          {uploadError   && <p className="text-red-400  text-sm mb-3">❌ {uploadError}</p>}

          {(campaign.example_conversations || []).length === 0 ? (
            <div className="border-2 border-dashed border-slate-600 rounded-lg p-8 text-center text-slate-400">
              <p className="text-lg mb-1">No recordings yet</p>
              <p className="text-sm">Upload MP3, WAV, or M4A files of real sales calls</p>
            </div>
          ) : (
            <div className="space-y-3">
              {campaign.example_conversations.map((ex) => (
                <div key={ex.id} className="bg-slate-700 rounded-lg p-4 flex gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-white">🎵 {ex.filename}</span>
                      <span className="text-xs text-slate-400">
                        {new Date(ex.uploaded_at).toLocaleDateString()}
                      </span>
                    </div>
                    <p className="text-xs text-slate-300 line-clamp-3">{ex.transcript}</p>
                  </div>
                  <button onClick={() => deleteExample(ex.id)}
                    className="text-red-400 hover:text-red-300 text-sm flex-shrink-0">
                    🗑️
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Dialer Control */}
        <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 mb-6">
          <h2 className="text-xl font-bold text-white mb-4">Dialer Control</h2>
          {!telConfigured ? (
            <div className="bg-blue-900/30 border border-blue-800 rounded-md p-4 text-blue-200 text-sm">
              Real calling requires Twilio setup. Use Test Mode to simulate calls.
            </div>
          ) : (
            <div className="flex flex-wrap items-end gap-4">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Seconds between calls</label>
                <input type="number" min={10} value={delay} onChange={e => setDelay(e.target.value)}
                  className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-md text-white w-40" />
              </div>
              <button onClick={launchDialer} disabled={launching || stats.pending === 0}
                className="bg-green-600 text-white px-6 py-2 rounded-md hover:bg-green-700 disabled:bg-slate-700 disabled:text-slate-500">
                {launching ? 'Launching...' : 'Launch Auto-Dialer'}
              </button>
            </div>
          )}
        </div>

        {session && (
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 mb-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-white">Dialer Session</h2>
              <SessionBadge status={session.status} />
            </div>
            <div className="mb-4">
              <div className="flex justify-between text-sm text-slate-400 mb-1">
                <span>Progress</span>
                <span>{session.calls_made} / {session.lead_ids.length}</span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-2">
                <div className="bg-blue-500 h-2 rounded-full"
                  style={{ width: `${(session.calls_made / Math.max(1, session.lead_ids.length)) * 100}%` }} />
              </div>
            </div>
            <div className="flex gap-2">
              {session.status === 'running' && (
                <button onClick={pauseDialer} className="bg-yellow-600 text-white px-4 py-2 rounded-md hover:bg-yellow-700 text-sm">Pause</button>
              )}
              {session.status === 'paused' && (
                <button onClick={resumeDialer} className="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 text-sm">Resume</button>
              )}
            </div>
          </div>
        )}

        {/* Leads table */}
        <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
          <div className="p-4 border-b border-slate-700">
            <h2 className="text-xl font-bold text-white">Leads</h2>
          </div>
          {leads.length === 0 ? (
            <div className="p-8 text-center text-slate-400">No leads yet for this campaign.</div>
          ) : (
            <>
              <table className="w-full">
                <thead className="bg-slate-700">
                  <tr><Th>Name</Th><Th>Phone</Th><Th>Status</Th><Th>Action</Th></tr>
                </thead>
                <tbody className="divide-y divide-slate-700">
                  {pagedLeads.map(lead => (
                    <tr key={lead.id} className="hover:bg-slate-700/50">
                      <td className="px-6 py-4 text-sm text-white">{lead.name}</td>
                      <td className="px-6 py-4 text-sm text-slate-300 font-mono">{lead.phone}</td>
                      <td className="px-6 py-4">
                        <span className={`px-2 py-1 text-xs rounded-full ${statusColors[lead.status] || statusColors.pending}`}>
                          {lead.status}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        {lead.status === 'pending' && telConfigured && (
                          <button onClick={() => callNow(lead.id)} disabled={callingLeadId === lead.id}
                            className="text-sm text-blue-400 hover:text-blue-300 disabled:text-slate-500">
                            {callingLeadId === lead.id ? 'Calling...' : 'Call Now'}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {pageCount > 1 && (
                <div className="flex justify-center gap-2 p-4 border-t border-slate-700">
                  {Array.from({ length: pageCount }).map((_, i) => (
                    <button key={i} onClick={() => setPage(i + 1)}
                      className={`px-3 py-1 rounded text-sm ${page === i + 1 ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-300'}`}>
                      {i + 1}
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* ── Edit Campaign Modal ── */}
      {editOpen && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 rounded-xl border border-slate-700 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-slate-700 flex items-center justify-between">
              <h2 className="text-xl font-bold text-white">Edit Campaign</h2>
              <button onClick={() => setEditOpen(false)} className="text-slate-400 hover:text-white text-2xl">×</button>
            </div>
            <div className="p-6 space-y-4">

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Campaign Name</label>
                <input value={editForm.name} onChange={e => setEditForm({...editForm, name: e.target.value})}
                  className={inputClass} placeholder="Campaign name" />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Goal</label>
                <textarea value={editForm.goal} onChange={e => setEditForm({...editForm, goal: e.target.value})}
                  className={`${inputClass} h-20`} placeholder="Campaign goal" />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Language</label>
                <select value={editForm.language} onChange={e => setEditForm({...editForm, language: e.target.value})}
                  className={inputClass}>
                  {LANGUAGES.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Product Name</label>
                <input value={editForm.product_name} onChange={e => setEditForm({...editForm, product_name: e.target.value})}
                  className={inputClass} placeholder="Product name" />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Product Description</label>
                <textarea value={editForm.product_description} onChange={e => setEditForm({...editForm, product_description: e.target.value})}
                  className={`${inputClass} h-20`} placeholder="Product description" />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Key Features <span className="text-slate-500 font-normal">(one per line)</span></label>
                <textarea value={editForm.key_features} onChange={e => setEditForm({...editForm, key_features: e.target.value})}
                  className={`${inputClass} h-24`} placeholder="One feature per line" />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Pricing</label>
                <input value={editForm.pricing} onChange={e => setEditForm({...editForm, pricing: e.target.value})}
                  className={inputClass} placeholder="Pricing details" />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Target Customer</label>
                <input value={editForm.target_customer} onChange={e => setEditForm({...editForm, target_customer: e.target.value})}
                  className={inputClass} placeholder="Who is the ideal customer?" />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Objection Handling</label>
                <textarea value={editForm.objection_handling} onChange={e => setEditForm({...editForm, objection_handling: e.target.value})}
                  className={`${inputClass} h-20`} placeholder="How to handle common objections" />
              </div>
            </div>

            <div className="p-6 border-t border-slate-700 flex gap-3">
              <button onClick={saveEdit} disabled={editSaving}
                className="flex-1 bg-blue-600 text-white py-2 rounded-md hover:bg-blue-700 disabled:opacity-50 font-medium">
                {editSaving ? 'Saving...' : 'Save Changes'}
              </button>
              <button onClick={() => setEditOpen(false)}
                className="px-6 bg-slate-700 text-white rounded-md hover:bg-slate-600">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const StatCard = ({ label, value }) => (
  <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
    <div className="text-xs text-slate-400">{label}</div>
    <div className="text-2xl font-bold text-white mt-1">{value}</div>
  </div>
);

const Th = ({ children }) => (
  <th className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">{children}</th>
);

const SessionBadge = ({ status }) => {
  const map = {
    running: 'bg-green-900/40 text-green-300',
    paused: 'bg-yellow-900/40 text-yellow-300',
    completed: 'bg-blue-900/40 text-blue-300',
    failed: 'bg-red-900/40 text-red-300',
  };
  return <span className={`px-3 py-1 text-xs rounded-full capitalize ${map[status] || 'bg-slate-700 text-slate-300'}`}>{status}</span>;
};

export default CampaignDetail;
