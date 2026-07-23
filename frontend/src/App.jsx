import React, { useState } from 'react';
import Dashboard from './components/Dashboard';
import PRReviewer from './components/PRReviewer';
import ArchitectureGraph from './components/ArchitectureGraph';
import SecurityAudit from './components/SecurityAudit';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <header style={{
        padding: '16px 24px',
        borderBottom: '1px solid var(--border-card)',
        background: 'rgba(9, 13, 22, 0.8)',
        backdropFilter: 'blur(12px)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '36px',
            height: '36px',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, var(--accent-indigo), var(--accent-cyan))',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 'bold',
            fontSize: '1.2rem'
          }}>
            🛡️
          </div>
          <div>
            <h1 style={{ fontSize: '1.25rem', fontWeight: '700', margin: 0, background: 'linear-gradient(90deg, #fff, #94a3b8)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              RepoGuard AI
            </h1>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: 0 }}>
              AI Code Review & Engineering Intelligence Platform
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav style={{ display: 'flex', gap: '8px' }}>
          {[
            { id: 'dashboard', label: 'Dashboard' },
            { id: 'pr_reviewer', label: 'PR Reviewer' },
            { id: 'architecture', label: 'Architecture Graph' },
            { id: 'security', label: 'Security Audit' }
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: '8px 16px',
                borderRadius: '8px',
                border: 'none',
                background: activeTab === tab.id ? 'var(--accent-indigo)' : 'transparent',
                color: activeTab === tab.id ? '#fff' : 'var(--text-muted)',
                fontWeight: activeTab === tab.id ? '600' : '400',
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      {/* Main Content */}
      <main style={{ flex: 1, maxWidth: '1200px', width: '100%', margin: '0 auto' }}>
        {activeTab === 'dashboard' && <Dashboard />}
        {activeTab === 'pr_reviewer' && <PRReviewer />}
        {activeTab === 'architecture' && <ArchitectureGraph />}
        {activeTab === 'security' && <SecurityAudit />}
      </main>

      {/* Footer */}
      <footer style={{
        padding: '16px 24px',
        borderTop: '1px solid var(--border-card)',
        textAlign: 'center',
        fontSize: '0.8rem',
        color: 'var(--text-muted)'
      }}>
        RepoGuard AI &copy; 2026 &bull; Architected in 4 Core Modules
      </footer>
    </div>
  );
}
