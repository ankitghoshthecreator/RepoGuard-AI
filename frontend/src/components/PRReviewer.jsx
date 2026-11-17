import React, { useEffect, useState } from 'react';

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

async function request(path, options) {
  const response = await fetch(`${API}${path}`, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body?.detail?.error?.message || body?.detail || 'Request failed');
  return body;
}

export default function PRReviewer() {
  const [prUrl, setPrUrl] = useState('');
  const [reviewing, setReviewing] = useState(false);
  const [result, setResult] = useState(null);
  const [diffText, setDiffText] = useState('');
  const [error, setError] = useState('');
  const [reviews, setReviews] = useState([]);

  useEffect(() => {
    request('/reviews/').then((data) => setReviews(data.items)).catch(() => {});
  }, []);

  const handleReview = async () => {
    setError('');
    setResult(null);
    setReviewing(true);
    try {
      const job = await request('/reviews/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(diffText.trim() ? { diff_text: diffText } : { pr_url: prUrl }) });
      setResult({ id: job.id, status: job.status });
      const stream = new EventSource(`${API}/reviews/${job.id}/stream/`);
      stream.addEventListener('node_started', (event) => setResult((current) => ({ ...current, progress: [...(current.progress || []), `${JSON.parse(event.data).node} started`] })));
      stream.addEventListener('done', async () => { stream.close(); setResult(await request(`/reviews/${job.id}/`)); setReviews((await request('/reviews/')).items); setReviewing(false); });
      stream.addEventListener('error', async () => { stream.close(); try { setResult(await request(`/reviews/${job.id}/`)); } catch { setError('Review failed.'); } setReviewing(false); });
    } catch (err) { setError(err.message); setReviewing(false); }
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
            placeholder="Public GitHub pull request URL"
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
        <label style={{ display: 'block', marginTop: 14, color: 'var(--text-muted)' }} htmlFor="diff-text">Or paste a unified diff</label>
        <textarea id="diff-text" value={diffText} onChange={(e) => setDiffText(e.target.value)} rows={5} placeholder="diff --git …" style={{ width: '100%', marginTop: 8, padding: 12, borderRadius: 8, background: 'rgba(0,0,0,0.3)', color: '#fff', border: '1px solid var(--border-card)' }} />
      </div>

      {error && <p role="alert" style={{ color: '#f87171' }}>{error}</p>}

      {result && (
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: '600' }}>Review {result.id?.slice(0, 8)}</h3>
            <span style={{ background: 'rgba(16, 185, 129, 0.2)', color: 'var(--accent-emerald)', padding: '6px 12px', borderRadius: '20px', fontWeight: '600' }}>
              {result.result?.overall_status || result.status}
            </span>
          </div>
          <ul style={{ listStyle: 'none', padding: 0 }}>
            {(result.progress || []).map((h, i) => (
              <li key={i} style={{ padding: '8px 0', borderBottom: '1px solid var(--border-card)', fontSize: '0.9rem' }}>
                {h}
              </li>
            ))}
          </ul>
          {result.summary && <p>{result.summary}</p>}
          {result.findings?.map((finding, index) => <article key={index} style={{ padding: 12, borderBottom: '1px solid var(--border-card)' }}><b>{finding.severity} · {finding.category}</b><div>{finding.file_path}{finding.line ? `:${finding.line}` : ''}</div><p>{finding.message}</p>{finding.suggested_fix && <pre>{finding.suggested_fix}</pre>}</article>)}
        </div>
      )}
      <section style={{ padding: 24 }}><h3>Recent reviews</h3>{reviews.length ? reviews.map((review) => <p key={review.id}>{review.repo_url || 'Pasted diff'} · {review.status} · {review.id.slice(0, 8)}</p>) : <p style={{ color: 'var(--text-muted)' }}>No saved reviews yet.</p>}</section>
    </div>
  );
}
