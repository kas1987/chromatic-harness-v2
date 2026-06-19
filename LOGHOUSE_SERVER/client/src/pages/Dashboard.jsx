import React, { useState, useEffect } from 'react';
import axios from 'axios';

function Dashboard() {
  const [latestAudit, setLatestAudit] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const auditRes = await axios.get('/api/audits/latest');
        setLatestAudit(auditRes.data.report);

        // Mock alerts based on thresholds
        const mockAlerts = [];
        const metrics = auditRes.data.report?.metrics || {};

        if (parseInt(metrics.tools) > 4000) {
          mockAlerts.push({
            level: 'warning',
            message: `High activity detected: ${metrics.tools} tools invoked`
          });
        }

        setAlerts(mockAlerts);
        setLoading(false);
      } catch (err) {
        setError(err.message);
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div className="loading">Loading dashboard...</div>;
  if (error) return <div className="error">Error: {error}</div>;

  const metrics = latestAudit?.metrics || {};

  return (
    <div className="container">
      <div className="section">
        <h2 className="section-title">📊 Dashboard Overview</h2>

        <div className="grid">
          <div className="card">
            <div className="metric-label">Total Tools Invoked</div>
            <div className="metric">{metrics.tools || '—'}</div>
            <p style={{ fontSize: '12px', color: '#cbd5e1' }}>5-day analysis period</p>
          </div>

          <div className="card">
            <div className="metric-label">Estimated Turns</div>
            <div className="metric">{metrics.turns || '—'}</div>
            <p style={{ fontSize: '12px', color: '#cbd5e1' }}>~652 turns/day average</p>
          </div>

          <div className="card">
            <div className="metric-label">Peak Hour Activity</div>
            <div className="metric">{metrics.peak || '—'}</div>
            <p style={{ fontSize: '12px', color: '#cbd5e1' }}>16:00 UTC (12.7% daily)</p>
          </div>

          <div className="card">
            <div className="metric-label">Latest Report</div>
            <div className="metric" style={{ fontSize: '16px' }}>
              {latestAudit?.date || 'N/A'}
            </div>
            <p style={{ fontSize: '12px', color: '#cbd5e1' }}>{latestAudit?.title}</p>
          </div>
        </div>
      </div>

      {alerts.length > 0 && (
        <div className="section">
          <h2 className="section-title">🚨 Active Alerts</h2>
          {alerts.map((alert, i) => (
            <div key={i} className="error" style={{ marginBottom: '12px' }}>
              {alert.message}
            </div>
          ))}
        </div>
      )}

      <div className="section">
        <h2 className="section-title">📈 Quick Stats</h2>
        <div className="grid">
          <div className="card">
            <h3>Workflow Pattern</h3>
            <p>61% Shell • 30% File Ops • 9% Other</p>
            <div className="progress-bar" style={{ marginTop: '12px' }}>
              <div className="progress-fill" style={{ width: '61%' }}></div>
            </div>
          </div>

          <div className="card">
            <h3>Business Hours Discipline</h3>
            <p>98.9% activity during 08:00-23:59 UTC</p>
            <div className="progress-bar" style={{ marginTop: '12px' }}>
              <div className="progress-fill" style={{ width: '98.9%' }}></div>
            </div>
          </div>

          <div className="card">
            <h3>Read:Write Ratio</h3>
            <p>1.2:1 (debugging-heavy workflow)</p>
            <div className="progress-bar" style={{ marginTop: '12px' }}>
              <div className="progress-fill" style={{ width: '55%' }}></div>
            </div>
          </div>

          <div className="card">
            <h3>Agent Utilization</h3>
            <p>0.7% subagent usage (opportunity for +25% throughput)</p>
            <div className="progress-bar" style={{ marginTop: '12px' }}>
              <div className="progress-fill" style={{ width: '7%' }}></div>
            </div>
          </div>
        </div>
      </div>

      <div className="section">
        <h2 className="section-title">💡 Key Insights</h2>
        <div className="card">
          <ul style={{ paddingLeft: '20px', lineHeight: '1.8' }}>
            <li>Tuesday peak: 31.4% of weekly activity in single day</li>
            <li>Peak window (16:00-19:59 UTC): 33.4% of daily activity</li>
            <li>Sustained high intensity: 51 turns/hour on peak day</li>
            <li>Multi-agent coordination: 8 parallel branches merged successfully</li>
            <li>No nocturnal work detected: strong work-life discipline</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
