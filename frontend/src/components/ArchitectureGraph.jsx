import React from 'react';

export default function ArchitectureGraph() {
  return (
    <div style={{ padding: '24px' }}>
      <h2 style={{ fontSize: '1.5rem', fontWeight: '700', marginBottom: '8px' }}>
        Knowledge Graph & Dependency Visualizer
      </h2>
      <p style={{ color: 'var(--text-muted)', marginBottom: '20px' }}>
        Part 2: Neo4j cross-module software relationships and import topology
      </p>

      <div className="glass-panel" style={{ padding: '30px', textAlign: 'center' }}>
        <div style={{ padding: '40px', border: '2px dashed var(--border-card)', borderRadius: '12px' }}>
          <p style={{ fontSize: '1.1rem', color: 'var(--accent-cyan)', marginBottom: '8px' }}>
            🕸️ Neo4j Dependency & Knowledge Graph Node Viewer
          </p>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Visualizing imports between <code style={{ color: 'var(--accent-indigo)' }}>backend.app.part1_parser</code> &rarr; <code style={{ color: 'var(--accent-indigo)' }}>backend.app.part2_knowledge</code> &rarr; <code style={{ color: 'var(--accent-indigo)' }}>backend.app.part3_agents</code>
          </p>
        </div>
      </div>
    </div>
  );
}
