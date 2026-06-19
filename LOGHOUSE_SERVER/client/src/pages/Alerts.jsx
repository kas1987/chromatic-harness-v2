import React, { useState } from 'react';

function Alerts() {
  const [thresholds, setThresholds] = useState({
    daily_tools: 4000,
    peak_hour: 1500,
    sustained_rate: 350,
    task_tracking_min: 0.5,
    agent_usage_min: 10
  });

  const [alerts, setAlerts] = useState([
    {
      id: 1,
      level: 'warning',
      title: 'Peak Hour Concentration',
      message: '33.4% of daily activity in 4-hour window (16:00-19:59 UTC)',
      timestamp: '2026-06-19T16:00:00Z',
      resolved: false
    },
    {
      id: 2,
      level: 'warning',
      title: 'Low Task Tracking',
      message: 'Task operations at 0.8% (threshold: 0.5% minimum). Target: 5%',
      timestamp: '2026-06-19T14:30:00Z',
      resolved: false
    },
    {
      id: 3,
      level: 'info',
      title: 'Tuesday Spike Detected',
      message: 'June 2: 31.4% weekly activity in single day. Investigation: See correlation report.',
      timestamp: '2026-06-19T04:00:00Z',
      resolved: true
    }
  ]);

  const handleThresholdChange = (key, value) => {
    setThresholds({
      ...thresholds,
      [key]: parseFloat(value) || 0
    });
  };

  const handleResolveAlert = (id) => {
    setAlerts(alerts.map(a => a.id === id ? { ...a, resolved: !a.resolved } : a));
  };

  const getLevelColor = (level) => {
    switch (level) {
      case 'danger':
        return 'var(--danger)';
      case 'warning':
        return 'var(--warning)';
      case 'info':
        return 'var(--primary)';
      default:
        return 'var(--text-secondary)';
    }
  };

  const activeAlerts = alerts.filter(a => !a.resolved);
  const resolvedAlerts = alerts.filter(a => a.resolved);

  return (
    <div className="container">
      <div className="section">
        <h2 className="section-title">🚨 Alerts & Thresholds</h2>

        <div className="section" style={{ marginBottom: '40px' }}>
          <h3 style={{ marginBottom: '16px' }}>⚙️ Alert Thresholds</h3>
          <div className="grid">
            <div className="card">
              <label style={{ display: 'block', marginBottom: '8px' }}>
                <div style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>Daily Tools Alert</div>
                <input
                  type="number"
                  value={thresholds.daily_tools}
                  onChange={(e) => handleThresholdChange('daily_tools', e.target.value)}
                  style={{ width: '100%' }}
                />
              </label>
              <div style={{ fontSize: '11px', color: '#cbd5e1' }}>Trigger if &gt; value</div>
            </div>

            <div className="card">
              <label style={{ display: 'block', marginBottom: '8px' }}>
                <div style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>Peak Hour Alert</div>
                <input
                  type="number"
                  value={thresholds.peak_hour}
                  onChange={(e) => handleThresholdChange('peak_hour', e.target.value)}
                  style={{ width: '100%' }}
                />
              </label>
              <div style={{ fontSize: '11px', color: '#cbd5e1' }}>Tools/hour in peak window</div>
            </div>

            <div className="card">
              <label style={{ display: 'block', marginBottom: '8px' }}>
                <div style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>Sustained Rate Alert</div>
                <input
                  type="number"
                  value={thresholds.sustained_rate}
                  onChange={(e) => handleThresholdChange('sustained_rate', e.target.value)}
                  style={{ width: '100%' }}
                />
              </label>
              <div style={{ fontSize: '11px', color: '#cbd5e1' }}>Tools/hour sustained</div>
            </div>

            <div className="card">
              <label style={{ display: 'block', marginBottom: '8px' }}>
                <div style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>Min Task Tracking %</div>
                <input
                  type="number"
                  value={thresholds.task_tracking_min}
                  onChange={(e) => handleThresholdChange('task_tracking_min', e.target.value)}
                  step="0.1"
                  style={{ width: '100%' }}
                />
              </label>
              <div style={{ fontSize: '11px', color: '#cbd5e1' }}>Alert if below</div>
            </div>

            <div className="card">
              <label style={{ display: 'block', marginBottom: '8px' }}>
                <div style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>Min Agent Usage %</div>
                <input
                  type="number"
                  value={thresholds.agent_usage_min}
                  onChange={(e) => handleThresholdChange('agent_usage_min', e.target.value)}
                  style={{ width: '100%' }}
                />
              </label>
              <div style={{ fontSize: '11px', color: '#cbd5e1' }}>Alert if below</div>
            </div>
          </div>
        </div>

        <div className="section" style={{ marginBottom: '40px' }}>
          <h3 style={{ marginBottom: '16px' }}>🔴 Active Alerts ({activeAlerts.length})</h3>
          {activeAlerts.length === 0 ? (
            <div style={{ color: '#cbd5e1' }}>No active alerts</div>
          ) : (
            activeAlerts.map((alert) => (
              <div
                key={alert.id}
                className="card"
                style={{
                  marginBottom: '12px',
                  borderLeft: `4px solid ${getLevelColor(alert.level)}`,
                  backgroundColor: `rgba(${alert.level === 'danger' ? '239, 68, 68' : alert.level === 'warning' ? '245, 158, 11' : '37, 99, 235'}, 0.05)`
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                  <div>
                    <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '8px' }}>
                      <span className="status-badge" style={{
                        backgroundColor: `rgba(${alert.level === 'danger' ? '239, 68, 68' : alert.level === 'warning' ? '245, 158, 11' : '37, 99, 235'}, 0.2)`,
                        color: getLevelColor(alert.level)
                      }}>
                        {alert.level.toUpperCase()}
                      </span>
                      <span style={{ fontSize: '12px', color: '#94a3b8' }}>
                        {new Date(alert.timestamp).toLocaleString()}
                      </span>
                    </div>
                    <h4 style={{ marginBottom: '4px', color: getLevelColor(alert.level) }}>{alert.title}</h4>
                    <p style={{ fontSize: '14px', color: '#cbd5e1' }}>{alert.message}</p>
                  </div>
                  <button onClick={() => handleResolveAlert(alert.id)}>Resolve</button>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="section">
          <h3 style={{ marginBottom: '16px' }}>✅ Resolved Alerts ({resolvedAlerts.length})</h3>
          {resolvedAlerts.length === 0 ? (
            <div style={{ color: '#cbd5e1' }}>No resolved alerts</div>
          ) : (
            resolvedAlerts.map((alert) => (
              <div
                key={alert.id}
                className="card"
                style={{ marginBottom: '12px', backgroundColor: 'rgba(16, 185, 129, 0.05)', opacity: 0.7 }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                  <div>
                    <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '8px' }}>
                      <span className="status-badge status-success">RESOLVED</span>
                      <span style={{ fontSize: '12px', color: '#94a3b8' }}>
                        {new Date(alert.timestamp).toLocaleString()}
                      </span>
                    </div>
                    <h4 style={{ marginBottom: '4px' }}>{alert.title}</h4>
                    <p style={{ fontSize: '14px', color: '#cbd5e1' }}>{alert.message}</p>
                  </div>
                  <button onClick={() => handleResolveAlert(alert.id)}>Reopen</button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export default Alerts;
