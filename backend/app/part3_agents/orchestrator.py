"""
Part 3 – LangGraph Orchestrator
================================
Coordinates the multi-agent PR review pipeline:

  SecurityAgent → ArchitectureAgent → PerformanceAgent
       → TestingAgent → ReviewerAgent → Final Report

Each agent is run sequentially and its output passed into the next
stage where relevant.  The orchestrator mirrors the LangGraph
"state-machine over agents" pattern without requiring a running
LangGraph server.
"""

import logging
from typing import Any, Dict

from backend.app.part3_agents.security_agent     import SecurityAgent
from backend.app.part3_agents.architecture_agent import ArchitectureAgent
from backend.app.part3_agents.performance_agent  import PerformanceAgent
from backend.app.part3_agents.testing_agent      import TestingAgent
from backend.app.part3_agents.review_agent       import ReviewerAgent

logger = logging.getLogger("repoguard.part3.orchestrator")


class LangGraphOrchestrator:
    """
    Part 3: Multi-agent workflow orchestrator using LangGraph patterns.

    Runs a deterministic pipeline over a PR diff:
      1. SecurityAgent   – scans diff for vulnerabilities
      2. ArchitectureAgent – evaluates module-graph cohesion / coupling
      3. PerformanceAgent  – detects performance hotspots
      4. TestingAgent      – generates unit test stubs for new functions
      5. ReviewerAgent     – aggregates all findings into a final verdict

    Usage
    -----
    >>> orchestrator = LangGraphOrchestrator()
    >>> report = orchestrator.run_pr_review_workflow(pr_diff, repo_context)
    >>> print(report["overall_status"])   # APPROVED | CHANGES_REQUESTED | BLOCKED
    """

    def __init__(self) -> None:
        self._security     = SecurityAgent()
        self._architecture = ArchitectureAgent()
        self._performance  = PerformanceAgent()
        self._testing      = TestingAgent()
        self._reviewer     = ReviewerAgent()

    # ── Public API ──────────────────────────────────────────────────────

    def run_pr_review_workflow(
        self,
        pr_diff: str,
        repo_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute the full multi-agent PR review pipeline.

        Parameters
        ----------
        pr_diff:
            Raw unified diff string (output of ``git diff``).
        repo_context:
            Arbitrary context dict.  May contain:
            - ``"graph"``: a pre-built ``networkx.DiGraph`` for the
              ArchitectureAgent; if absent the agent builds its own.

        Returns
        -------
        Aggregated reviewer report dict with keys:
            status, overall_status, risk_score, pr_summary,
            checklist, agent_findings.
        """
        logger.info("Orchestrator: starting PR review pipeline (diff length=%d)", len(pr_diff))

        # ── Stage 1: Security ──────────────────────────────────────────
        sec_result = self._security.analyze(pr_diff)
        logger.info("Stage 1/4 Security done — status=%s", sec_result.get("status"))

        # ── Stage 2: Architecture ──────────────────────────────────────
        # If the security scan surfaced a CRITICAL risk, still continue
        # but flag it in the context for the reviewer.
        arch_result = self._architecture.analyze(repo_context or {})
        logger.info("Stage 2/4 Architecture done — verdict=%s", arch_result.get("verdict"))

        # ── Stage 3: Performance ───────────────────────────────────────
        perf_result = self._performance.analyze(pr_diff)
        logger.info("Stage 3/4 Performance done — complexity=%s", perf_result.get("time_complexity"))

        # ── Stage 4: Testing ───────────────────────────────────────────
        test_result = self._testing.analyze_diff(pr_diff)
        logger.info("Stage 4/4 Testing done — %d stub(s) generated", test_result.get("stub_count", 0))

        # ── Stage 5: Reviewer aggregation ─────────────────────────────
        final_report = self._reviewer.synthesize_report([
            sec_result,
            arch_result,
            perf_result,
            test_result,
        ])

        logger.info(
            "Orchestrator: pipeline complete — overall_status=%s risk=%s",
            final_report.get("overall_status"),
            final_report.get("risk_score"),
        )
        return final_report
