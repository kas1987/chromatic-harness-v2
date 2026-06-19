import React, { useState, useEffect } from 'react';
import axios from 'axios';

function AuditHistory() {
  const [audits, setAudits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    const fetchAudits = async () => {
      try {
        const res = await axios.get('/api/audits/reports');
        setAudits(res.data.reports);
        setLoading(false);
      } catch (err) {
        setError(err.message);
        setLoading(false);
      }
    };

    fetchAudits();
  }, []);

  const handleSearch = async (term) => {
    setSearchTerm(term);
    if (term.length < 2) {
      const res = await axios.get('/api/audits/reports');
      setAudits(res.data.reports);
      return;
    }

    try {
      const res = await axios.get(`/api/audits/search?q=${term}`);
      setAudits(res.data.results);
    } catch (err) {
      console.error(err);
    }
  };

  const handleExport = async (format) => {
    try {
      window.location.href = `/api/audits/export/${format}`;
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) return <div className="loading">Loading audit reports...</div>;
  if (error) return <div className="error">Error: {error}</div>;

  return (
    <div className="container">
      <div className="section">
        <h2 className="section-title">📋 Audit History</h2>

        <div style={{ display: 'flex', gap: '12px', marginBottom: '20px', flexWrap: 'wrap' }}>
          <input
            type="text"
            placeholder="Search audits..."
            value={searchTerm}
            onChange={(e) => handleSearch(e.target.value)}
            style={{ flex: 1, minWidth: '200px' }}
          />
          <button onClick={() => handleExport('json')}>Export JSON</button>
          <button onClick={() => handleExport('csv')}>Export CSV</button>
        </div>

        <div>
          <p style={{ marginBottom: '20px', color: '#cbd5e1' }}>
            Found {audits.length} audit report{audits.length !== 1 ? 's' : ''}
          </p>

          <ul className="list">
            {audits.map((audit, i) => (
              <li key={i} className="list-item">
                <div className="list-item-title">{audit.title}</div>
                <div className="list-item-date">Date: {audit.date}</div>
                {audit.metrics && (
                  <div style={{ fontSize: '12px', color: '#cbd5e1', marginTop: '8px' }}>
                    Tools: {audit.metrics.tools || '—'} | Turns: {audit.metrics.turns || '—'} | Peak: {audit.metrics.peak || '—'}
                  </div>
                )}
                <div style={{ fontSize: '12px', marginTop: '8px', color: '#94a3b8' }}>
                  {audit.preview}
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

export default AuditHistory;
