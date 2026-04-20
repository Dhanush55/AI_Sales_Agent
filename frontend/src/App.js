import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import AuthGuard from './components/AuthGuard';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import CampaignCreate from './pages/CampaignCreate';
import CampaignList from './pages/CampaignList';
import CampaignDetail from './pages/CampaignDetail';
import CampaignAnalytics from './pages/CampaignAnalytics';
import LeadsList from './pages/LeadsList';
import CallsList from './pages/CallsList';
import CallDetails from './pages/CallDetails';
import TestMode from './pages/TestMode';
import Settings from './pages/Settings';
import AdminPanel from './pages/AdminPanel';
import './App.css';

const guarded = (el) => <AuthGuard>{el}</AuthGuard>;

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/dashboard" element={guarded(<Dashboard />)} />
          <Route path="/campaigns" element={guarded(<CampaignList />)} />
          <Route path="/campaigns/create" element={guarded(<CampaignCreate />)} />
          <Route path="/campaign/:id" element={guarded(<CampaignDetail />)} />
          <Route path="/campaigns/:campaignId/analytics" element={guarded(<CampaignAnalytics />)} />
          <Route path="/campaigns/:campaignId/leads" element={guarded(<LeadsList />)} />
          <Route path="/calls" element={guarded(<CallsList />)} />
          <Route path="/calls/:callId" element={guarded(<CallDetails />)} />
          <Route path="/test-mode" element={guarded(<TestMode />)} />
          <Route path="/settings" element={guarded(<Settings />)} />
          <Route path="/admin" element={guarded(<AdminPanel />)} />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
