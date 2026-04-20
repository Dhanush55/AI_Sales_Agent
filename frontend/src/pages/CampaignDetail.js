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
    } catch {
      setSession(null);
    }
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
      } catch {
        /* no session yet */
      }
    }, 10000);
    return () => clearInterval(pollRef.current);
  }, [id]);

  const stats = {
    total: leads.length,
    pending: leads.filter((l) => l.status === 'pending').length,
    contacted: leads.filter((l) => l.status === 'contacted').length,
    interested: leads.filter((l) => l.status === 'interested').length,
  };

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
    } finally {
      setLaunching(false);
    }
  };

  const pauseDialer = async () => {
    await api.post(`/dialer/${session.id}/pause`);
    await loadAll();
  };

  const resumeDialer = async () => {
    await api.post(`/dialer/${session.id}/resume`);
    await loadAll();
  };

  const callNow = async (leadId) => {
    setCallingLeadId(leadId);
    try {
      await api.post(`/phone/call?campaign_id=${id}&lead_id=${leadId}`);
      await loadAll();
    } catch (e) {
      alert(e.response?.data?.detail || 'Call failed');
    } finally {
      setCallingLeadId(null);
    }
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

  return (
    <div className="min-h-screen bg-slate-900">
      <Navbar />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <button
          onClick={() => navigate('/campaigns')}
          className="text-slate-400 hover:text-white mb-4 text-sm"
          data-testid="back-to-campaigns-btn"
        >
          ← Back to Campaigns
        </button>

        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-3xl font-bold text-white" data-testid="campaign-name">
              {campaign.name}
            </h1>
            <span className="px-3 py-1 text-xs rounded-full bg-slate-700 text-slate-200 capitalize">
              {campaign.language.replace('_', ' ')}
            </span>
          </div>
          <p className="text-slate-400" data-testid="campaign-goal">{campaign.goal}</p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <StatCard label="Total Leads" value={stats.total} testId="stat-total" />
          <StatCard label="Pending" value={stats.pending} testId="stat-pending" />
          <StatCard label="Contacted" value={stats.contacted} testId="stat-contacted" />
          <StatCard label="Interested" value={stats.interested} testId="stat-interested" />
        </div>

        <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 mb-6">
          <h2 className="text-xl font-bold text-white mb-4">Dialer Control</h2>
          {!telConfigured ? (
            <div className="bg-blue-900/30 border border-blue-800 rounded-md p-4 text-blue-200 text-sm" data-testid="telephony-not-configured">
              Real calling requires Twilio setup. Use Test Mode to simulate calls.
            </div>
          ) : (
            <div className="flex flex-wrap items-end gap-4">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Seconds between calls</label>
                <input
                  type="number"
                  min={10}
                  value={delay}
                  onChange={(e) => setDelay(e.target.value)}
                  className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-md text-white w-40"
                  data-testid="dialer-delay-input"
                />
              </div>
              <button
                onClick={launchDialer}
                disabled={launching || stats.pending === 0}
                className="bg-green-600 text-white px-6 py-2 rounded-md hover:bg-green-700 disabled:bg-slate-700 disabled:text-slate-500"
                data-testid="launch-dialer-btn"
              >
                {launching ? 'Launching...' : 'Launch Auto-Dialer'}
              </button>
            </div>
          )}
        </div>

        {session && (
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 mb-6" data-testid="dialer-session-card">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-white">Dialer Session</h2>
              <SessionBadge status={session.status} />
            </div>
            <div className="mb-4">
              <div className="flex justify-between text-sm text-slate-400 mb-1">
                <span>Progress</span>
                <span data-testid="dialer-progress">{session.calls_made} / {session.lead_ids.length}</span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-2">
                <div
                  className="bg-blue-500 h-2 rounded-full"
                  style={{ width: `${(session.calls_made / Math.max(1, session.lead_ids.length)) * 100}%` }}
                />
              </div>
            </div>
            <div className="flex gap-2">
              {session.status === 'running' && (
                <button onClick={pauseDialer} className="bg-yellow-600 text-white px-4 py-2 rounded-md hover:bg-yellow-700 text-sm" data-testid="pause-dialer-btn">
                  Pause
                </button>
              )}
              {session.status === 'paused' && (
                <button onClick={resumeDialer} className="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 text-sm" data-testid="resume-dialer-btn">
                  Resume
                </button>
              )}
            </div>
          </div>
        )}

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
                  <tr>
                    <Th>Name</Th><Th>Phone</Th><Th>Status</Th><Th>Action</Th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700">
                  {pagedLeads.map((lead) => (
                    <tr key={lead.id} className="hover:bg-slate-700/50" data-testid="lead-row">
                      <td className="px-6 py-4 text-sm text-white">{lead.name}</td>
                      <td className="px-6 py-4 text-sm text-slate-300 font-mono">{lead.phone}</td>
                      <td className="px-6 py-4">
                        <span className={`px-2 py-1 text-xs rounded-full ${statusColors[lead.status] || statusColors.pending}`}>
                          {lead.status}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        {lead.status === 'pending' && telConfigured && (
                          <button
                            onClick={() => callNow(lead.id)}
                            disabled={callingLeadId === lead.id}
                            className="text-sm text-blue-400 hover:text-blue-300 disabled:text-slate-500"
                            data-testid="call-now-btn"
                          >
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
                    <button
                      key={i}
                      onClick={() => setPage(i + 1)}
                      className={`px-3 py-1 rounded text-sm ${page === i + 1 ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-300'}`}
                    >
                      {i + 1}
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

const StatCard = ({ label, value, testId }) => (
  <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
    <div className="text-xs text-slate-400">{label}</div>
    <div className="text-2xl font-bold text-white mt-1" data-testid={testId}>{value}</div>
  </div>
);

const Th = ({ children }) => (
  <th className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">
    {children}
  </th>
);

const SessionBadge = ({ status }) => {
  const map = {
    running: 'bg-green-900/40 text-green-300',
    paused: 'bg-yellow-900/40 text-yellow-300',
    completed: 'bg-blue-900/40 text-blue-300',
    failed: 'bg-red-900/40 text-red-300',
  };
  return (
    <span className={`px-3 py-1 text-xs rounded-full capitalize ${map[status] || 'bg-slate-700 text-slate-300'}`} data-testid="dialer-status-badge">
      {status}
    </span>
  );
};

export default CampaignDetail;
