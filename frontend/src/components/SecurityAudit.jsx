import React from 'react';

export default function SecurityAudit() {
  return (
    <div style={{ padding: '24px' }}>
      <h2 style={{ fontSize: '1.5rem', fontWeight: '700', marginBottom: '8px' }}>
        Static & LLM Security Vulnerability Audit
      </h2>
      <p style={{ color: 'var(--text-muted)', marginBottom: '20px' }}>
        Part 1 AST Scanner & Part 3 Security Agent Audit Trail
      </p>

      <div className="glass-panel" style={{ padding: '20px' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-card)', color: 'var(--text-muted)' }}>
              <th style={{ padding: '12px' }}>Module</th>
              <th style={{ padding: '12px' }}>Scanner</th>
              <th style={{ padding: '12px' }}>Status</th>
              <th style={{ padding: '12px' }}>Vulnerabilities Found</th>
            </tr>
          </thead>
          <tbody>
            <tr style={{ borderBottom: '1px solid var(--border-card)' }}>
              <td style={{ padding: '12px' }}>part1_parser/static_scanner.py</td>
              <td style={{ padding: '12px' }}>Part 1 Symbolic Scan</td>
              <td style={{ padding: '12px', color: 'var(--accent-emerald)' }}>PASSED</td>
              <td style={{ padding: '12px' }}>0 Credentials, 0 Injections</td>
            </tr>
            <tr style={{ borderBottom: '1px solid var(--border-card)' }}>
              <td style={{ padding: '12px' }}>part3_agents/security_agent.py</td>
              <td style={{ padding: '12px' }}>Part 3 LLM Security Agent</td>
              <td style={{ padding: '12px', color: 'var(--accent-emerald)' }}>PASSED</td>
              <td style={{ padding: '12px' }}>0 Unsafe Deserializations</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
