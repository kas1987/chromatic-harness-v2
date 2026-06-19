import React, { useState, useEffect } from 'react';
import axios from 'axios';

function Correlations() {
  const [correlations, setCorrelations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedDate, setSelectedDate] = useState(null);
  const [gitCommits, setGitCommits] = useState([]);

  useEffect(() => {
    const fetchCorrelations = async () => {
      try {
        const res = await axios.get('/api/audits/correlations');
        setCorrelations(res.data.reports);
        if (res.data.reports.length > 0) {
          setSelectedDate(res.data.reports[0].date);
        }
        setLoading(false);
      } catch (err) {
        setError(err.message);
        setLoading(false);
      }
    };

    fetchCorrelations();
  }, []);

  const handleDateSelect = async (date) => {
    setSelectedDate(date);
    try {
      const res = await axios.get(`/api/audits/git-correlation/${date}`);
      setGitCommits(res.data.commits);
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) return <div className="loading">Loading correlations...</div>;
  if (error) return <div className="error">Error: {error}</div>;

  return (
    <div className="container">
      <div className="section">
        <h2 className="section-title">🔗 Audit & Git Correlations</h2>
        <p style={{ color: '#cbd5e1', marginBottom: '20px' }}>
          Match audit spikes to git commit history to understand what work triggered activity surges.
        </p>

        <div className="grid" style={{ gridTemplateColumns: '1fr 2fr' }}>
          <div>
            <h3 style={{ marginBottom: '12px' }}>Correlation Reports</h3>
            <ul className="list">
              {correlations.map((corr, i) => (
                <li
                  key={i}
                  className="list-item"
                  onClick={() => handleDateSelect(corr.date)}
                  style={{
                    cursor: 'pointer',
                    backgroundColor: selectedDate === corr.date ? 'rgba(37, 99, 235, 0.2)' : undefined
                  }}
                >
                  <div className="list-item-title">{corr.date}</div>
                  <div className="list-item-date">{corr.title}</div>
                </li>
              ))}
            </ul>
          </div>

          <div>
            {selectedDate && gitCommits.length > 0 && (
              <>
                <h3 style={{ marginBottom: '12px' }}>Git Commits: {selectedDate}</h3>
                <div style={{ fontSize: '12px', marginBottom: '12px', color: '#cbd5e1' }}>
                  Found {gitCommits.length} commit{gitCommits.length !== 1 ? 's' : ''}
                </div>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Hash</th>
                      <th>Timestamp</th>
                      <th>Message</th>
                    </tr>
                  </thead>
                  <tbody>
                    {gitCommits.map((commit, i) => (
                      <tr key={i}>
                        <td><code style={{ fontSize: '11px' }}>{commit.hash}</code></td>
                        <td style={{ fontSize: '12px' }}>{commit.timestamp}</td>
                        <td style={{ fontSize: '12px' }}>{commit.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}

            {selectedDate && gitCommits.length === 0 && (
              <div style={{ color: '#cbd5e1' }}>No commits found for {selectedDate}</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Correlations;
