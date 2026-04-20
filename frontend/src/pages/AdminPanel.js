import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { useAuth } from '../contexts/AuthContext';
import api from '../utils/api';

const AdminPanel = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user && !user.is_admin) {
      navigate('/dashboard');
      return;
    }
    Promise.all([api.get('/admin/stats'), api.get('/admin/users')])
      .then(([s, u]) => {
        setStats(s.data);
        setUsers(u.data);
      })
      .catch((e) => console.error(e))
      .finally(() => setLoading(false));
  }, [user, navigate]);

  const toggleAdmin = async (targetId) => {
    await api.put(`/admin/users/${targetId}/toggle-admin`);
    const u = await api.get('/admin/users');
    setUsers(u.data);
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
        <h1 className="text-3xl font-bold text-white mb-2">Admin Panel</h1>
        <p className="text-slate-400 mb-8">Platform-wide management</p>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatCard label="Total Clients" value={stats?.total_users} testId="admin-total-users" />
          <StatCard label="Total Campaigns" value={stats?.total_campaigns} testId="admin-total-campaigns" />
          <StatCard label="Total Calls" value={stats?.total_calls} testId="admin-total-calls" />
          <StatCard label="Calls Today" value={stats?.calls_today} testId="admin-calls-today" />
        </div>

        <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
          <div className="p-4 border-b border-slate-700">
            <h2 className="text-xl font-bold text-white">Clients</h2>
          </div>
          <table className="w-full">
            <thead className="bg-slate-700">
              <tr>
                <Th>Company</Th><Th>Email</Th><Th>Campaigns</Th><Th>Leads</Th>
                <Th>Calls</Th><Th>This Month</Th><Th>Joined</Th><Th>Admin</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-slate-700/50" data-testid="admin-user-row">
                  <td className="px-4 py-3 text-sm text-white">{u.company_name || '—'}</td>
                  <td className="px-4 py-3 text-sm text-slate-300">{u.email}</td>
                  <td className="px-4 py-3 text-sm text-slate-300">{u.campaign_count}</td>
                  <td className="px-4 py-3 text-sm text-slate-300">{u.lead_count}</td>
                  <td className="px-4 py-3 text-sm text-slate-300">{u.call_count}</td>
                  <td className="px-4 py-3 text-sm text-slate-300">{u.calls_this_month}</td>
                  <td className="px-4 py-3 text-sm text-slate-400">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => toggleAdmin(u.id)}
                      className={`text-xs px-3 py-1 rounded ${u.is_admin ? 'bg-purple-900/40 text-purple-300' : 'bg-slate-700 text-slate-300'}`}
                      data-testid="toggle-admin-btn"
                    >
                      {u.is_admin ? 'Admin ✓' : 'Make Admin'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

const StatCard = ({ label, value, testId }) => (
  <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
    <div className="text-xs text-slate-400">{label}</div>
    <div className="text-2xl font-bold text-white mt-1" data-testid={testId}>{value ?? 0}</div>
  </div>
);

const Th = ({ children }) => (
  <th className="px-4 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">
    {children}
  </th>
);

export default AdminPanel;
