# Review pipeline agents

The existing pipeline runs sequentially in `backend/app/part3_agents/orchestrator.py`. Optional progress callbacks emit each node's start and completion.

| Agent | Input | Output |
| --- | --- | --- |
| `SecurityAgent` | Unified diff text | Static security findings, severity-based status and risk |
| `ArchitectureAgent` | Repository context (optional dependency graph) | Architecture/cohesion verdict |
| `PerformanceAgent` | Unified diff text | Complexity estimate and performance verdict |
| `TestingAgent` | Unified diff text | Suggested test stubs and count |
| `ReviewerAgent` | The four specialist outputs | Overall status, risk, summary, checklist, per-agent details |

Prompts are not used by this deterministic pipeline. Individual findings are persisted when agents return a `findings` list. Progress is stored as review events and exposed through the review detail endpoint and SSE stream.
