import React, { useState, useEffect } from 'react';
import axios from 'axios';

function SWOT() {
  const [swots, setSWOTs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchSWOTs = async () => {
      try {
        const res = await axios.get('/api/audits/swot');
        setSWOTs(res.data.reports);
        setLoading(false);
      } catch (err) {
        setError(err.message);
        setLoading(false);
      }
    };

    fetchSWOTs();
  }, []);

  if (loading) return <div className="loading">Loading SWOT analysis...</div>;
  if (error) return <div className="error">Error: {error}</div>;

  return (
    <div className="container">
      <div className="section">
        <h2 className="section-title">💼 SWOT Analysis</h2>
        <p style={{ color: '#cbd5e1', marginBottom: '20px' }}>
          Strategic analysis of strengths, weaknesses, opportunities, and threats from usage patterns.
        </p>

        <div className="grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
          <div className="card" style={{ borderLeft: '4px solid var(--success)' }}>
            <h3>✅ Strengths</h3>
            <ul style={{ paddingLeft: '20px', lineHeight: '1.8', fontSize: '14px' }}>
              <li>Exceptional focus & discipline (98.9% business hours)</li>
              <li>Sustained high-intensity sessions (20+ hour blocks)</li>
              <li>Automation-first workflow (61% shell)</li>
              <li>Successful multi-agent coordination</li>
              <li>Read-driven debugging culture</li>
              <li>Clear sprint structure</li>
            </ul>
          </div>

          <div className="card" style={{ borderLeft: '4px solid var(--danger)' }}>
            <h3>⚠️ Weaknesses</h3>
            <ul style={{ paddingLeft: '20px', lineHeight: '1.8', fontSize: '14px' }}>
              <li>Extreme peak-hour concentration (33.4% in 4h)</li>
              <li>Low subagent utilization (0.7%)</li>
              <li>Minimal task tracking (0.8%)</li>
              <li>Stale cache (9 months old)</li>
              <li>Limited web integration (0.7%)</li>
              <li>No adaptive throttling</li>
            </ul>
          </div>

          <div className="card" style={{ borderLeft: '4px solid var(--primary)' }}>
            <h3>💡 Opportunities</h3>
            <ul style={{ paddingLeft: '20px', lineHeight: '1.8', fontSize: '14px' }}>
              <li>Load balancing (redistribute peak 25%)</li>
              <li>Agent parallelization (+25% throughput)</li>
              <li>Task tracking integration (0.8% → 5%)</li>
              <li>Peak-hour awareness system</li>
              <li>Cache automation (40% savings)</li>
              <li>Web integration enhancement</li>
              <li>Audit automation (weekly reports)</li>
            </ul>
          </div>

          <div className="card" style={{ borderLeft: '4px solid var(--warning)' }}>
            <h3>🚨 Threats</h3>
            <ul style={{ paddingLeft: '20px', lineHeight: '1.8', fontSize: '14px' }}>
              <li>Token budget exhaustion</li>
              <li>Context degradation in long sessions</li>
              <li>Undetected regressions</li>
              <li>Cache collision during parallelization</li>
              <li>Burnout from sustained intensity</li>
              <li>Dependency drift</li>
              <li>Scaling limits</li>
            </ul>
          </div>
        </div>

        {swots.length > 0 && (
          <div className="section" style={{ marginTop: '40px' }}>
            <h3 style={{ marginBottom: '12px' }}>Historical SWOT Reports</h3>
            <ul className="list">
              {swots.map((swot, i) => (
                <li key={i} className="list-item">
                  <div className="list-item-title">{swot.title}</div>
                  <div className="list-item-date">Date: {swot.date}</div>
                  <div style={{ fontSize: '12px', marginTop: '8px', color: '#94a3b8' }}>
                    {swot.preview}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

export default SWOT;
