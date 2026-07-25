"""
Part 3 – Architecture Agent
============================
Analyses the codebase's module dependency graph (from Part 2
``KnowledgeGraphBuilder``) to produce cohesion / coupling metrics
and an architecture pattern assessment.
"""

import logging
from typing import Any, Dict

from backend.app.part2_knowledge.graph_builder import KnowledgeGraphBuilder

logger = logging.getLogger("repoguard.part3.architecture_agent")


class ArchitectureAgent:
    """
    Part 3: Architectural review agent.

    Uses the Part 2 ``KnowledgeGraphBuilder`` to compute graph-based
    cohesion and coupling metrics, then produces an architectural verdict.
    """

    _ARCHITECTURE_PATTERNS = [
        "4-Part Modular Enterprise Layering",
        "Hexagonal Architecture",
        "MVC / MVT",
        "Microservices",
        "Monolith",
    ]

    def __init__(self) -> None:
        self._graph_builder = KnowledgeGraphBuilder()

    # ── Public API ──────────────────────────────────────────────────────

    def analyze(self, graph_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate architectural quality from the knowledge graph.

        Parameters
        ----------
        graph_context:
            Optional dict that may contain a pre-built ``networkx.DiGraph``
            under the key ``"graph"``.  If absent the agent falls back to the
            live ``KnowledgeGraphBuilder`` graph.

        Returns
        -------
        dict with keys:
            agent, architecture_pattern, cohesion_score (0–1),
            coupling_issue_detected (bool), coupling_ratio,
            node_count, edge_count, verdict (EXCELLENT | GOOD | WARN | POOR).
        """
        graph = graph_context.get("graph") if graph_context else None
        if graph is None:
            graph = self._graph_builder.graph

        node_count = graph.number_of_nodes()
        edge_count = graph.number_of_edges()

        # Cohesion: edges relative to maximum possible for a directed graph
        max_edges = node_count * (node_count - 1) if node_count > 1 else 1
        cohesion = round(edge_count / max_edges, 4)

        # Coupling: average out-degree (fan-out)
        avg_out_degree = round(edge_count / node_count, 2) if node_count else 0.0
        coupling_issue = avg_out_degree > 5  # heuristic threshold

        pattern = self._detect_pattern(node_count, edge_count)
        verdict = self._verdict(cohesion, coupling_issue)

        logger.info(
            "ArchitectureAgent: nodes=%d edges=%d cohesion=%.4f coupling_issue=%s",
            node_count,
            edge_count,
            cohesion,
            coupling_issue,
        )

        return {
            "agent": "ArchitectureAgent",
            "architecture_pattern": pattern,
            "cohesion_score": cohesion,
            "coupling_issue_detected": coupling_issue,
            "coupling_ratio": avg_out_degree,
            "node_count": node_count,
            "edge_count": edge_count,
            "verdict": verdict,
        }

    # ── Internals ───────────────────────────────────────────────────────

    @staticmethod
    def _detect_pattern(nodes: int, edges: int) -> str:
        """Heuristic pattern detection based on graph shape."""
        if nodes == 0:
            return "Unknown"
        if nodes <= 10 and edges <= 15:
            return "4-Part Modular Enterprise Layering"
        if edges / nodes > 4:
            return "Highly Connected / Potential Monolith"
        return "Modular Layered Architecture"

    @staticmethod
    def _verdict(cohesion: float, coupling_issue: bool) -> str:
        if cohesion >= 0.8 and not coupling_issue:
            return "EXCELLENT"
        if cohesion >= 0.5 and not coupling_issue:
            return "GOOD"
        if coupling_issue:
            return "WARN"
        return "POOR"
