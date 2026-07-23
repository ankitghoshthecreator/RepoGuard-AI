import React from 'react';

export default function Dashboard() {
  const parts = [
    {
      id: "Part 1",
      name: "Code Ingestion & AST Parser",
      desc: "Tree-sitter AST extraction, multi-language symbolic parser, static analysis & credential scanner.",
      status: "Active",
      files: "42 Files Parsed"
    },
    {
      id: "Part 2",
      name: "Knowledge Graph & Hybrid RAG",
      desc: "Dependency graph builder (Neo4j), Qdrant vector database code chunk embeddings, and BM25 hybrid search.",
      status: "Indexed",
      nodes: "184 Graph Nodes"
    },
    {
      id: "Part 3",
      name: "Multi-Agent AI Reasoning Core",
      desc: "LangGraph autonomous team (Security, Architecture, Performance, Testing, Reviewer Agents).",
      status: "Ready",
      agents: "6 Active Agents"
    },
    {
      id: "Part 4",
      name: "FastAPI Backend & UI Portal",
      desc: "Async REST APIs, GitHub webhooks triggers, authentication, and enterprise dashboard.",
      status: "Online",
      latency: "12ms Latency"
    }
  ];

  return (
    <div style={{ padding: '24px' }}>
      <h2 style={{ fontSize: '1.5rem', fontWeight: '700', marginBottom: '8px' }}>
        RepoGuard AI System Overview
      </h2>
      <p style={{ color: 'var(--text-muted)', marginBottom: '24px' }}>
        4-Part Enterprise Software Engineering Intelligence & Automated Code Review Architecture
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
        {parts.map((p) => (
          <div key={p.id} className="glass-panel" style={{ padding: '20px' }}>
            <span className="badge-part" style={{ marginBottom: '12px' }}>{p.id}</span>
            <h3 style={{ fontSize: '1.1rem', fontWeight: '600', margin: '8px 0' }}>{p.name}</h3>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', lineHeight: '1.5', marginBottom: '16px' }}>
              {p.desc}
            </p>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
              <span>Status: {p.status}</span>
              <span>{p.files || p.nodes || p.agents || p.latency}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
