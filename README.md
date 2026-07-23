# RepoGuard AI

### 📌 4-Part Core Architecture Overview

RepoGuard AI is architected into **4 primary functional parts**:

1. **Part 1: Code Ingestion, AST & Static Analysis Engine** (`backend/app/part1_parser/`)  
   Handles local/remote repository cloning, Tree-sitter & AST parsing, code metadata extraction, dependency mapping, and symbolic static code/security scanning.
2. **Part 2: Knowledge Graph & Hybrid RAG Engine** (`backend/app/part2_knowledge/`)  
   Builds repository-wide software dependency graphs (Neo4j / NetworkX), generates code embeddings stored in vector databases (Qdrant), and executes multi-modal hybrid retrieval (Semantic + Keyword + Graph).
3. **Part 3: Multi-Agent AI Reasoning & PR Intelligence** (`backend/app/part3_agents/`)  
   Orchestrates autonomous LLM agents (Security Agent, Architecture Agent, Performance Agent, Testing Agent, Documentation Agent, and Reviewer Agent) using LangGraph to analyze code diffs and synthesize actionable code review reports.
4. **Part 4: FastAPI Server, UI Dashboard & DevOps Infrastructure** (`backend/app/part4_api/` & `frontend/`)  
   Exposes high-performance REST APIs, GitHub webhook integration, a modern web dashboard for engineering intelligence, and Docker containerized deployment setups.

---

### Enterprise AI Platform for Automated Code Review, Security Analysis, Architecture Inspection, and Pull Request Intelligence

> An enterprise-grade AI software engineering platform that analyzes source code repositories, detects bugs, identifies security vulnerabilities, reviews pull requests, understands software architecture, and generates actionable recommendations using Large Language Models, Static Analysis, Knowledge Graphs, and Multi-Agent AI.

---

## Overview

**RepoGuard AI** is an end-to-end software engineering assistant that automates complex technical code reviews and architectural audits.

Instead of relying solely on LLM prompt engineering, RepoGuard AI deeply understands entire software repositories by unifying:

- Abstract Syntax Tree (AST) Analysis
- Static Code Analysis & Linting
- Software Dependency & Knowledge Graphs
- Retrieval-Augmented Generation (RAG)
- Multi-Agent Orchestrated Reasoning
- Large Language Models (LLMs)

---

## Core 4-Part Breakdown & Features

### 🔹 Part 1: Ingestion, AST & Static Analysis Engine
- **Multi-Source Ingestion**: Ingests GitHub repositories, local project directories, and ZIP archives.
- **Language Parsers**: Supports Python, JavaScript, TypeScript, Java, C++, and Go.
- **AST Extraction**: Extracts functions, classes, imports, class hierarchies, and variable scopes.
- **Static Code Analysis**: Detects dead code, unreachable logic, long functions, cognitive complexity, and deep nesting.
- **Static Security Scanner**: Identifies hardcoded secrets, SQL injection patterns, unsafe deserialization, and crypto flaws.

### 🔹 Part 2: Knowledge Graph & Hybrid RAG Engine
- **Dependency Graph**: Maps cross-module imports, package calls, and circular dependencies.
- **Knowledge Graph**: Stores relationships between microservices, classes, DB models, and API routes in Neo4j / graph structures.
- **Code Vector Embeddings**: Generates dense semantic vectors for functions, documentation, and commits.
- **Hybrid Retrieval**: Blends semantic similarity (Qdrant), keyword search (BM25), and graph traversal for context assembly.

### 🔹 Part 3: Multi-Agent AI Reasoning & PR Intelligence
- **LangGraph Multi-Agent Team**:
  - 🛡️ **Security Agent**: Audits vulnerability vectors and authentication paths.
  - 🏗️ **Architecture Agent**: Evaluates system design patterns and structural decoupling.
  - ⚡ **Performance Agent**: Detects $O(N^2)$ loops, N+1 DB queries, and memory leaks.
  - 🧪 **Testing Agent**: Drafts missing unit tests and edge cases.
  - 📝 **Documentation Agent**: Writes docstrings, API specs, and architectural documentation.
  - 🔍 **Review Agent**: Aggregates multi-agent findings into structured PR reviews.
- **Pull Request Intelligence**: Generates automated PR summaries, risk scores, breaking change warnings, and reviewer checklists.

### 🔹 Part 4: FastAPI Backend, UI Dashboard & DevOps Infrastructure
- **FastAPI Web Service**: Provides asynchronous endpoints for repository indexing, code reviews, and webhook events.
- **GitHub Webhooks**: Triggers automated agent reviews on every new Pull Request or Commit.
- **Developer Dashboard**: High-impact modern UI for inspecting repository architecture, security health scores, and agent PR reviews.
- **Enterprise DevOps**: Fully containerized using Docker, Docker Compose, and Kubernetes manifests with telemetry via Prometheus & Langfuse.

---

## System Architecture

```
                       ┌─────────────────────────┐
                       │    Developer / PR       │
                       └────────────┬────────────┘
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │  Part 4: React Dashboard│
                       │     & GitHub Webhooks   │
                       └────────────┬────────────┘
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │  Part 4: FastAPI Server │
                       └────────────┬────────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            │                       │                       │
            ▼                       ▼                       ▼
 ┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐
 │ Part 1: Ingestion &  │ │ Part 2: Knowledge &  │ │ Part 3: Multi-Agent  │
 │ Static AST Parser    │ │ Hybrid RAG Indexer   │ │ LangGraph Reasoning  │
 ├──────────────────────┤ ├──────────────────────┤ ├──────────────────────┤
 │ • Git/ZIP Loader     │ │ • Neo4j Graph DB     │ │ • Security Agent     │
 │ • Tree-sitter / AST  │ │ • Qdrant Vector DB   │ │ • Architecture Agent │
 │ • Dependency Mapper  │ │ • Dense Embeddings   │ │ • Performance Agent  │
 │ • Security Scanner   │ │ • Hybrid RAG Engine  │ │ • PR Review Agent    │
 └──────────────────────┘ └──────────────────────┘ └──────────────────────┘
            │                       │                       │
            └───────────────────────┼───────────────────────┘
                                    ▼
                       ┌─────────────────────────┐
                       │ Actionable PR Review    │
                       │ & Engineering Report    │
                       └─────────────────────────┘
```

---

## Tech Stack

| Domain | Technologies |
| :--- | :--- |
| **Frontend** | React, Vite, JavaScript / TypeScript, Vanilla CSS / Tailwind CSS |
| **Backend** | Python 3.11+, FastAPI, Uvicorn, Pydantic |
| **Parsing & Static Analysis** | Tree-sitter, Python AST |
| **Graph & RAG** | Neo4j, NetworkX, Qdrant, BGE / OpenAI Embeddings, LangChain |
| **Multi-Agent Orchestration** | LangGraph, LangChain, OpenAI / Anthropic / Gemini LLMs |
| **DevOps & Infrastructure** | Docker, Docker Compose, Redis, PostgreSQL |

---

## Repository Structure

```
RepoGuard-AI/
├── backend/
│   ├── main.py                    # Entry point for FastAPI server
│   └── app/
│       ├── config.py              # Application settings & environment vars
│       ├── part1_parser/          # Part 1: Code Ingestion & AST Analysis
│       │   ├── ingestion.py       # Git repo & file tree ingestion
│       │   ├── ast_analyzer.py    # AST & symbol extractor
│       │   └── static_scanner.py  # Static code & security vulnerability scanner
│       ├── part2_knowledge/       # Part 2: Knowledge Graph & Hybrid RAG Engine
│       │   ├── graph_builder.py   # Neo4j & NetworkX dependency graphs
│       │   ├── embeddings.py      # Code chunking & vector embedding generation
│       │   └── hybrid_retrieval.py# Vector + Graph + Keyword hybrid RAG
│       ├── part3_agents/          # Part 3: Multi-Agent AI Reasoning & PR Review
│       │   ├── orchestrator.py    # LangGraph workflow manager
│       │   ├── security_agent.py  # Security vulnerability analysis agent
│       │   ├── architecture_agent.py # Architectural design agent
│       │   ├── performance_agent.py  # Code optimization agent
│       │   ├── testing_agent.py   # Unit test generation agent
│       │   └── review_agent.py    # PR Review aggregator agent
│       └── part4_api/             # Part 4: API Backend & Webhooks
│           ├── router.py          # API route definitions
│           ├── auth.py            # Authentication & JWT security
│           └── webhooks.py        # GitHub PR webhook triggers
├── frontend/                      # Part 4: Modern Web User Interface
│   ├── package.json
│   ├── index.html
│   └── src/
│       ├── App.jsx
│       ├── index.css
│       └── components/
│           ├── Dashboard.jsx
│           ├── PRReviewer.jsx
│           ├── ArchitectureGraph.jsx
│           └── SecurityAudit.jsx
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Quick Start Guide

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ (for frontend development)
- Docker & Docker Compose (optional, for containerized run)

### 2. Virtual Environment Setup
```bash
# Clone the repository
git clone https://github.com/ankitghoshthecreator/RepoGuard-AI.git
cd RepoGuard-AI

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env` and provide your API keys:
```bash
cp .env.example .env
```

### 4. Running Backend Server
```bash
uvicorn backend.main:app --reload --port 8000
```

### 5. Running with Docker Compose
```bash
docker-compose -f docker/docker-compose.yml up --build
```

---

## License

This project is licensed under the MIT License.