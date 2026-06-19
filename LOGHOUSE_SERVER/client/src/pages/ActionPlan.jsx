import React, { useState } from 'react';

function ActionPlan() {
  const [actions, setActions] = useState([
    {
      id: 1,
      priority: 1,
      title: 'Load Balancing',
      description: 'Redistribute 25% of peak-hour (16:00-19:59 UTC) work to 07:00-09:00 UTC',
      effort: '2-3h',
      impact: 'High',
      status: 'pending',
      timeline: 'Week 1',
      result: 'Peak rate 1,225 → 920 tools/hour (-25%)'
    },
    {
      id: 2,
      priority: 2,
      title: 'Task Tracking',
      description: 'Increase from 0.8% to 5% task operations using bd (beads)',
      effort: '1-2h',
      impact: 'High',
      status: 'pending',
      timeline: 'Week 1',
      result: 'Full sprint lineage (turn → task → commit)'
    },
    {
      id: 3,
      priority: 3,
      title: 'Cache Cleanup',
      description: 'Archive pre-2026-05 CLI cache (3,310 files)',
      effort: '1h',
      impact: 'High',
      status: 'pending',
      timeline: 'Week 1',
      result: 'Footprint 8.7 MB → 2.5 MB (-71%)'
    },
    {
      id: 4,
      priority: 4,
      title: 'Agent Parallelization',
      description: 'Convert sequential shell ops to forked agents',
      effort: 'Medium',
      impact: 'High',
      status: 'pending',
      timeline: 'Sprint 2',
      result: '+25% throughput potential'
    },
    {
      id: 5,
      priority: 5,
      title: 'Audit Automation',
      description: 'Weekly reports + anomaly alerts (Friday 18:00 UTC)',
      effort: '3-4h',
      impact: 'Medium',
      status: 'pending',
      timeline: 'Week 2',
      result: 'Zero manual work, continuous visibility'
    }
  ]);

  const handleStatusChange = (id, newStatus) => {
    setActions(actions.map(a => a.id === id ? { ...a, status: newStatus } : a));
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'complete':
        return 'var(--success)';
      case 'in-progress':
        return 'var(--warning)';
      default:
        return 'var(--text-secondary)';
    }
  };

  return (
    <div className="container">
      <div className="section">
        <h2 className="section-title">🎯 Action Plan Tracker</h2>
        <p style={{ color: '#cbd5e1', marginBottom: '20px' }}>
          5 prioritized actions to improve workflow efficiency and scalability.
        </p>

        {actions.map((action) => (
          <div key={action.id} className="card" style={{ marginBottom: '20px', borderLeft: '4px solid var(--primary)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '12px' }}>
              <div>
                <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '8px' }}>
                  <span className="status-badge" style={{
                    backgroundColor: `rgba(${action.priority === 1 ? '239, 68, 68' : action.priority <= 3 ? '245, 158, 11' : '37, 99, 235'}, 0.2)`,
                    color: action.priority === 1 ? 'var(--danger)' : action.priority <= 3 ? 'var(--warning)' : 'var(--primary)'
                  }}>
                    P{action.priority}
                  </span>
                  <span className="status-badge" style={{
                    backgroundColor: `rgba(${action.impact === 'High' ? '16, 185, 129' : '245, 158, 11'}, 0.2)`,
                    color: action.impact === 'High' ? 'var(--success)' : 'var(--warning)'
                  }}>
                    {action.impact} Impact
                  </span>
                </div>
                <h3 style={{ marginBottom: '8px' }}>{action.title}</h3>
                <p style={{ fontSize: '14px', color: '#cbd5e1' }}>{action.description}</p>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '12px', marginBottom: '12px' }}>
              <div>
                <div style={{ fontSize: '11px', color: '#94a3b8' }}>EFFORT</div>
                <div style={{ fontSize: '14px', fontWeight: '600' }}>{action.effort}</div>
              </div>
              <div>
                <div style={{ fontSize: '11px', color: '#94a3b8' }}>TIMELINE</div>
                <div style={{ fontSize: '14px', fontWeight: '600' }}>{action.timeline}</div>
              </div>
              <div>
                <div style={{ fontSize: '11px', color: '#94a3b8' }}>RESULT</div>
                <div style={{ fontSize: '12px', fontWeight: '600' }}>{action.result}</div>
              </div>
            </div>

            <div style={{ borderTop: '1px solid var(--border)', paddingTop: '12px' }}>
              <div style={{ fontSize: '11px', color: '#94a3b8', marginBottom: '8px' }}>STATUS</div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={() => handleStatusChange(action.id, 'pending')}
                  style={{
                    backgroundColor: action.status === 'pending' ? 'var(--primary)' : 'rgba(255, 255, 255, 0.1)',
                    color: action.status === 'pending' ? 'white' : 'var(--text-secondary)'
                  }}
                >
                  Pending
                </button>
                <button
                  onClick={() => handleStatusChange(action.id, 'in-progress')}
                  style={{
                    backgroundColor: action.status === 'in-progress' ? 'var(--warning)' : 'rgba(255, 255, 255, 0.1)',
                    color: action.status === 'in-progress' ? 'white' : 'var(--text-secondary)'
                  }}
                >
                  In Progress
                </button>
                <button
                  onClick={() => handleStatusChange(action.id, 'complete')}
                  style={{
                    backgroundColor: action.status === 'complete' ? 'var(--success)' : 'rgba(255, 255, 255, 0.1)',
                    color: action.status === 'complete' ? 'white' : 'var(--text-secondary)'
                  }}
                >
                  Complete
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="section">
        <h2 className="section-title">📊 Progress Summary</h2>
        <div className="grid">
          <div className="card">
            <div className="metric-label">Pending</div>
            <div className="metric" style={{ color: 'var(--text-secondary)' }}>
              {actions.filter(a => a.status === 'pending').length}
            </div>
          </div>
          <div className="card">
            <div className="metric-label">In Progress</div>
            <div className="metric" style={{ color: 'var(--warning)' }}>
              {actions.filter(a => a.status === 'in-progress').length}
            </div>
          </div>
          <div className="card">
            <div className="metric-label">Complete</div>
            <div className="metric" style={{ color: 'var(--success)' }}>
              {actions.filter(a => a.status === 'complete').length}
            </div>
          </div>
          <div className="card">
            <div className="metric-label">Completion %</div>
            <div className="metric" style={{ color: 'var(--success)' }}>
              {Math.round((actions.filter(a => a.status === 'complete').length / actions.length) * 100)}%
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ActionPlan;
