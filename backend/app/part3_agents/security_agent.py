"""
Part 3 – Security Agent
=======================
Wraps the Part 1 ``StaticSecurityScanner`` to analyse a code diff and
return a structured finding report with an overall PASS / FAIL verdict.
"""

import logging
from typing import Any, Dict, List

from backend.app.part1_parser.static_scanner import StaticSecurityScanner, Finding

logger = logging.getLogger("repoguard.part3.security_agent")


class SecurityAgent:
    """
    Part 3: Security vulnerability analysis agent.

    Integrates the Part 1 ``StaticSecurityScanner`` to scan a PR diff
    and produce a structured security report.
    """

    def __init__(self) -> None:
        self._scanner = StaticSecurityScanner()

    # ── Public API ──────────────────────────────────────────────────────

    def analyze(self, code_diff: str) -> Dict[str, Any]:
        """
        Scan a code diff for security vulnerabilities.

        Parameters
        ----------
        code_diff:
            Raw unified diff string (``git diff`` output) or any code snippet.

        Returns
        -------
        dict with keys:
            agent, status (PASS | FAIL), risk_score (LOW | MEDIUM | HIGH | CRITICAL),
            findings (list of finding dicts), finding_count, recommendation.
        """
        findings: List[Finding] = self._scanner.scan_code(
            code=code_diff, filename="<pr_diff>"
        )

        # Determine overall status and risk score from highest-severity finding
        status, risk_score = self._verdict(findings)

        logger.info(
            "SecurityAgent: %d findings, status=%s, risk=%s",
            len(findings),
            status,
            risk_score,
        )

        return {
            "agent": "SecurityAgent",
            "status": status,
            "risk_score": risk_score,
            "finding_count": len(findings),
            "findings": [f.to_dict() for f in findings],
            "recommendation": self._recommendation(status),
        }

    # ── Internals ───────────────────────────────────────────────────────

    @staticmethod
    def _verdict(findings: List[Finding]):
        """Return (status, risk_score) based on the highest-severity finding."""
        severity_rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}
        max_rank = max((severity_rank.get(f.severity, 0) for f in findings), default=0)
        risk_map = {4: "CRITICAL", 3: "HIGH", 2: "MEDIUM", 1: "LOW", 0: "LOW"}
        risk_score = risk_map[max_rank]
        status = "PASS" if max_rank < 3 else "FAIL"   # CRITICAL or HIGH → FAIL
        return status, risk_score

    @staticmethod
    def _recommendation(status: str) -> str:
        if status == "PASS":
            return "No critical security issues detected. Maintain environment secrets in .env."
        return (
            "Critical/high-severity vulnerabilities found. "
            "Fix before merging — see individual findings for remediation steps."
        )
