import React, { useState, useEffect } from 'react';
import './index.css';
import './App.css';
import Dashboard from './pages/Dashboard';
import AuditHistory from './pages/AuditHistory';
import Correlations from './pages/Correlations';
import SWOT from './pages/SWOT';
import ActionPlan from './pages/ActionPlan';
import Alerts from './pages/Alerts';

function App() {
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [serverHealth, setServerHealth] = useState(null);

  useEffect(() => {
    fetch('/api/health')
      .then(r => r.json())
      .then(data => setServerHealth(data))
      .catch(console.error);
  }, []);

  return (
    <div className="app">
      <header className="header">
        <div className="header-content">
          <h1>🏛️ LOGHOUSE</h1>
          <p>Claude Code Audit & Operations Dashboard</p>
        </div>
        <nav className="nav">
          <button className={currentPage === 'dashboard' ? 'active' : ''} onClick={() => setCurrentPage('dashboard')}>
            Dashboard
          </button>
          <button className={currentPage === 'audits' ? 'active' : ''} onClick={() => setCurrentPage('audits')}>
            Audits
          </button>
          <button className={currentPage === 'correlations' ? 'active' : ''} onClick={() => setCurrentPage('correlations')}>
            Correlations
          </button>
          <button className={currentPage === 'swot' ? 'active' : ''} onClick={() => setCurrentPage('swot')}>
            SWOT
          </button>
          <button className={currentPage === 'actions' ? 'active' : ''} onClick={() => setCurrentPage('actions')}>
            Action Plan
          </button>
          <button className={currentPage === 'alerts' ? 'active' : ''} onClick={() => setCurrentPage('alerts')}>
            Alerts
          </button>
        </nav>
      </header>

      <main className="main-content">
        {currentPage === 'dashboard' && <Dashboard />}
        {currentPage === 'audits' && <AuditHistory />}
        {currentPage === 'correlations' && <Correlations />}
        {currentPage === 'swot' && <SWOT />}
        {currentPage === 'actions' && <ActionPlan />}
        {currentPage === 'alerts' && <Alerts />}
      </main>

      <footer className="footer">
        <p>LOGHOUSE Server • Port 3333 • {serverHealth?.timestamp ? new Date(serverHealth.timestamp).toLocaleString() : 'Loading...'}</p>
      </footer>
    </div>
  );
}

export default App;
