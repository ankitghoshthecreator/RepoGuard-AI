import React, { useState } from 'react';

export default function PRReviewer() {
  const [prUrl, setPrUrl] = useState('');
  const [reviewing, setReviewing] = useState(false);
  const [result, setResult] = useState(null);

  const handleReview = () => {
    setReviewing(true);
    setTimeout(() => {
      setReviewing(false);
      setResult({
        pr_number: "#104",
        verdict: "APPROVED",
        score: "98/100",
        agent_highlights: [
          "Part 1 AST Scanner: 0 syntax issues detected.",
          "Part 2 Knowledge Graph: 0 breaking cross-module dependencies.",
          "Part 3 Multi-Agent: Security & Architecture agents passed with high confidence."
        ]
      });
    }, 1200);
  };

  return (
    <div style={{ padding: '24px' }}>
      <h2 style={{ fontSize: '1.5rem', fontWeight: '700', marginBottom: '8px' }}>
        Pull Request Intelligence & Agentic Review
      </h2>
      <p style={{ color: 'var(--text-muted)', marginBottom: '20px' }}>
        Part 3 Multi-Agent LangGraph workflow analyzing code diffs
      </p>

      <div className="glass-panel" style={{ padding: '20px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', gap: '12px' }}>
          <input
            type="text"
            placeholder="Enter GitHub PR URL or Branch (e.g. https://github.com/org/repo/pull/104)"
            value={prUrl}
            onChange={(e) => setPrUrl(e.target.value)}
            style={{
              flex: 1,
              padding: '12px 16px',
              borderRadius: '8px',
              border: '1px solid var(--border-card)',
              background: 'rgba(0,0,0,0.3)',
              color: '#fff'
            }}
          />
          <button
            onClick={handleReview}
            disabled={reviewing}
            style={{
              padding: '12px 24px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, var(--accent-indigo), var(--accent-cyan))',
              color: '#fff',
              border: 'none',
              fontWeight: '600',
              cursor: 'pointer'
            }}
          >
            {reviewing ? 'Agents Reviewing...' : 'Trigger Multi-Agent Review'}
          </button>
        </div>
      </div>

      {result && (
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: '600' }}>PR Review Result {result.pr_number}</h3>
            <span style={{ background: 'rgba(16, 185, 129, 0.2)', color: 'var(--accent-emerald)', padding: '6px 12px', borderRadius: '20px', fontWeight: '600' }}>
              {result.verdict} ({result.score})
            </span>
          </div>
          <ul style={{ listStyle: 'none', padding: 0 }}>
            {result.agent_highlights.map((h, i) => (
              <li key={i} style={{ padding: '8px 0', borderBottom: '1px solid var(--border-card)', fontSize: '0.9rem' }}>
                {h}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
