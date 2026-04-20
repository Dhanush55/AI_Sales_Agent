import React from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const linkCls = 'text-slate-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium';

const Navbar = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <nav className="bg-slate-800 border-b border-slate-700">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <Link to="/dashboard" className="text-xl font-bold text-white">
              Voice Sales Agent
            </Link>
            <div className="ml-10 flex items-baseline space-x-4">
              <Link to="/dashboard" className={linkCls} data-testid="nav-dashboard">Dashboard</Link>
              <Link to="/campaigns" className={linkCls} data-testid="nav-campaigns">Campaigns</Link>
              <Link to="/calls" className={linkCls} data-testid="nav-calls">Calls</Link>
              <Link to="/test-mode" className={linkCls} data-testid="nav-test-mode">Test Mode</Link>
              <Link to="/settings" className={linkCls} data-testid="nav-settings">Settings</Link>
              {user?.is_admin && (
                <Link to="/admin" className={`${linkCls} text-purple-300`} data-testid="nav-admin">Admin</Link>
              )}
            </div>
          </div>
          <div className="flex items-center space-x-4">
            {user && (
              <>
                <span className="text-slate-300 text-sm">{user.email}</span>
                <button
                  onClick={handleLogout}
                  className="bg-slate-700 text-white px-4 py-2 rounded-md text-sm hover:bg-slate-600"
                  data-testid="logout-btn"
                >
                  Logout
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
