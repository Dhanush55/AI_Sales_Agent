import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import AuthGuard from './components/AuthGuard';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import CampaignCreate from './pages/CampaignCreate';
import CampaignList from './pages/CampaignList';
import CampaignAnalytics from './pages/CampaignAnalytics';
import LeadsList from './pages/LeadsList';
import CallsList from './pages/CallsList';
import CallDetails from './pages/CallDetails';
import TestMode from './pages/TestMode';
import './App.css';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/dashboard"
            element={
              <AuthGuard>
                <Dashboard />
              </AuthGuard>
            }
          />
          <Route
            path="/campaigns"
            element={
              <AuthGuard>
                <CampaignList />
              </AuthGuard>
            }
          />
          <Route
            path="/campaigns/create"
            element={
              <AuthGuard>
                <CampaignCreate />
              </AuthGuard>
            }
          />
          <Route
            path="/campaigns/:campaignId/leads"
            element={
              <AuthGuard>
                <LeadsList />
              </AuthGuard>
            }
          />
          <Route
            path="/calls"
            element={
              <AuthGuard>
                <CallsList />
              </AuthGuard>
            }
          />
          <Route
            path="/calls/:callId"
            element={
              <AuthGuard>
                <CallDetails />
              </AuthGuard>
            }
          />
          <Route
            path="/test-mode"
            element={
              <AuthGuard>
                <TestMode />
              </AuthGuard>
            }
          />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;