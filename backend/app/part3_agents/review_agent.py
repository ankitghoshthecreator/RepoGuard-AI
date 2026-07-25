"""
Part 3 – Reviewer Agent
========================
Aggregates the outputs of all specialist agents into a single,
human-readable PR review report with an overall verdict and checklist.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger("repoguard.part3.review_agent")

# Severity rankings used when computing the overall risk score
_RISK_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}


class ReviewerAgent:
    """
    Part 3: Final pull request review aggregator agent.

    Takes the outputs of SecurityAgent, ArchitectureAgent,
    PerformanceAgent, and TestingAgent and synthesises a unified
    PR review report with:
      - overall_status  (APPROVED | CHANGES_REQUESTED | BLOCKED)
      - risk_score      (LOW | MEDIUM | HIGH | CRITICAL)
      - pr_summary      (concise human-readable summary)
      - checklist       (per-agent pass/fail items)
      - agent_findings  (raw agent outputs for transparency)
    """

    def synthesize_report(self, agent_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Build the final review report.

        Parameters
        ----------
        agent_outputs:
            List of dicts returned by each specialist agent's ``analyze``
            (or equivalent) method.  Unknown agents are included in
            ``agent_findings`` but do not affect scoring.

        Returns
        -------
        Unified review report dict.
        """
        security   = self._find(agent_outputs, "SecurityAgent")
        arch       = self._find(agent_outputs, "ArchitectureAgent")
        perf       = self._find(agent_outputs, "PerformanceAgent")
        testing    = self._find(agent_outputs, "TestingAgent")

        overall_risk = self._compute_risk(security, arch, perf)
        overall_status = self._compute_status(overall_risk, security)

        checklist = self._build_checklist(security, arch, perf, testing)
        pr_summary = self._build_summary(overall_status, overall_risk, security, perf, testing)

        logger.info(
            "ReviewerAgent: status=%s risk=%s checklist=%d items",
            overall_status,
            overall_risk,
            len(checklist),
        )

        return {
            "status": "completed",
            "overall_status": overall_status,
            "risk_score": overall_risk,
            "pr_summary": pr_summary,
            "checklist": checklist,
            "agent_findings": {
                "security":     security,
                "architecture": arch,
                "performance":  perf,
                "testing":      testing,
            },
        }

    # ── Internals ───────────────────────────────────────────────────────

    @staticmethod
    def _find(outputs: List[Dict[str, Any]], agent_name: str) -> Dict[str, Any]:
        """Return the dict whose 'agent' key matches *agent_name*, or {}."""
        for o in outputs:
            if isinstance(o, dict) and o.get("agent") == agent_name:
                return o
        return {}

    @staticmethod
    def _compute_risk(
        security: Dict, arch: Dict, perf: Dict
    ) -> str:
        """Derive overall risk from the highest sub-agent risk."""
        ranks = []
        # SecurityAgent exposes risk_score
        if security:
            ranks.append(_RISK_RANK.get(security.get("risk_score", "LOW"), 1))
        # ArchitectureAgent exposes verdict → map to risk
        arch_map = {"EXCELLENT": 0, "GOOD": 0, "WARN": 1, "POOR": 2}
        if arch:
            ranks.append(arch_map.get(arch.get("verdict", "GOOD"), 0))
        # PerformanceAgent exposes verdict
        perf_map = {"PASS": 0, "WARN": 1}
        if perf:
            ranks.append(perf_map.get(perf.get("verdict", "PASS"), 0))

        max_rank = max(ranks, default=0)
        return {4: "CRITICAL", 3: "HIGH", 2: "MEDIUM", 1: "LOW", 0: "LOW"}[min(max_rank, 4)]

    @staticmethod
    def _compute_status(risk: str, security: Dict) -> str:
        """Determine overall PR disposition."""
        if security.get("status") == "FAIL" and risk in ("CRITICAL", "HIGH"):
            return "BLOCKED"
        if risk in ("CRITICAL", "HIGH", "MEDIUM"):
            return "CHANGES_REQUESTED"
        return "APPROVED"

    @staticmethod
    def _build_checklist(
        security: Dict, arch: Dict, perf: Dict, testing: Dict
    ) -> List[str]:
        items = []

        # Security
        sec_status = security.get("status", "UNKNOWN")
        n_findings = security.get("finding_count", 0)
        if sec_status == "PASS":
            items.append(f"✅ Security Audit Passed ({n_findings} findings, none critical/high)")
        else:
            items.append(f"❌ Security Audit FAILED ({n_findings} findings require attention)")

        # Architecture
        arch_verdict = arch.get("verdict", "UNKNOWN")
        icon = "✅" if arch_verdict in ("EXCELLENT", "GOOD") else "⚠️"
        items.append(f"{icon} Architecture & Cohesion: {arch_verdict}")

        # Performance
        perf_verdict = perf.get("verdict", "UNKNOWN")
        complexity   = perf.get("time_complexity", "Unknown")
        icon = "✅" if perf_verdict == "PASS" else "⚠️"
        items.append(f"{icon} Performance & Complexity: {complexity} — {perf_verdict}")

        # Testing
        stub_count = testing.get("stub_count", 0) if testing else 0
        if stub_count > 0:
            items.append(f"📝 Unit Test Stubs Generated: {stub_count} function(s) covered")
        else:
            items.append("📝 Unit Test Stubs: no new functions detected in diff")

        return items

    @staticmethod
    def _build_summary(
        status: str, risk: str,
        security: Dict, perf: Dict, testing: Dict
    ) -> str:
        n_sec = security.get("finding_count", 0)
        complexity = perf.get("time_complexity", "O(N)")
        n_stubs = testing.get("stub_count", 0) if testing else 0

        status_msg = {
            "APPROVED": "✅ Pull request is APPROVED.",
            "CHANGES_REQUESTED": "⚠️  Changes requested before merge.",
            "BLOCKED": "🚫 Pull request is BLOCKED due to critical security issues.",
        }.get(status, "Review complete.")

        return (
            f"{status_msg} "
            f"Overall risk: {risk}. "
            f"Security: {n_sec} finding(s). "
            f"Estimated complexity: {complexity}. "
            f"Test stubs generated for {n_stubs} function(s)."
        )
