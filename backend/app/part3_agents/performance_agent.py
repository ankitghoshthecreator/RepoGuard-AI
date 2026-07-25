"""
Part 3 – Performance Agent
===========================
Analyses a code diff for performance-related issues using
heuristic static analysis (loop detection, complexity estimation,
expensive-pattern detection).
"""

import re
import logging
from typing import Any, Dict, List

logger = logging.getLogger("repoguard.part3.performance_agent")


# ── Pattern definitions ────────────────────────────────────────────────

# (regex, issue_name, description, suggestion)
_PERF_PATTERNS: List = [
    (
        re.compile(r"\bfor\b.+\bfor\b", re.DOTALL),
        "Nested Loops",
        "Nested loops may cause O(N²) or worse complexity.",
        "Consider flattening with list comprehensions, numpy, or a hash-based approach.",
    ),
    (
        re.compile(r"\.append\s*\("),
        "List append in loop (potential)",
        "Repeated list.append() inside tight loops can be slow; prefer list comprehensions.",
        "Use list comprehensions or pre-allocated arrays where possible.",
    ),
    (
        re.compile(r"time\.sleep\s*\("),
        "Blocking sleep",
        "time.sleep() blocks the event loop in async contexts.",
        "Use asyncio.sleep() in async functions.",
    ),
    (
        re.compile(r"SELECT \*", re.IGNORECASE),
        "SELECT * query",
        "Fetching all columns is wasteful. Select only the required columns.",
        "Specify explicit column names in SELECT statements.",
    ),
    (
        re.compile(r"\.read\(\)"),
        "Full file read into memory",
        "Reading an entire file at once may cause memory spikes on large files.",
        "Use chunked reading or streaming where possible.",
    ),
    (
        re.compile(r"\+\s*['\"]|['\"][^'\"]*\+"),
        "String concatenation in loop (potential)",
        "String concatenation with + in Python creates new objects each time.",
        "Use ''.join() or f-strings instead.",
    ),
    (
        re.compile(r"re\.compile\s*\(", re.IGNORECASE),
        "Regex compiled inside function (potential)",
        "Compiling regex inside a frequently-called function is expensive.",
        "Move re.compile() to module level as a constant.",
    ),
]


class PerformanceAgent:
    """
    Part 3: Code performance & complexity optimization agent.

    Scans code diffs line-by-line using heuristic patterns to surface
    potential performance hotspots. Does not require LLM calls.
    """

    def analyze(self, code_diff: str) -> Dict[str, Any]:
        """
        Analyse a code diff for performance issues.

        Parameters
        ----------
        code_diff:
            Raw unified diff string or code snippet.

        Returns
        -------
        dict with keys:
            agent, time_complexity, memory_usage, issue_count,
            issues (list of dicts), suggestions (list of strings), verdict.
        """
        issues: List[Dict[str, Any]] = []
        lines = code_diff.splitlines()

        # Count structural complexity indicators
        loop_count = sum(
            1 for ln in lines
            if re.search(r"\b(for|while)\b", ln)
        )
        has_nested = any(
            re.search(r"\bfor\b.*\bfor\b", ln, re.DOTALL)
            for ln in lines
        )

        for line_no, line in enumerate(lines, 1):
            stripped = line.strip()
            # Skip diff metadata and blank lines
            if not stripped or stripped.startswith(("---", "+++", "@@", "#")):
                continue
            for pattern, name, desc, suggestion in _PERF_PATTERNS:
                if pattern.search(line):
                    issues.append({
                        "line": line_no,
                        "issue": name,
                        "description": desc,
                        "suggestion": suggestion,
                        "evidence": stripped[:120],
                    })
                    break  # one issue per line

        time_complexity = (
            "O(N²)" if (loop_count > 3 or has_nested)
            else "O(N log N)" if loop_count > 1
            else "O(N)"
        )
        memory_usage = "REVIEW" if any("read()" in ln for ln in lines) else "OPTIMAL"
        verdict = "WARN" if issues else "PASS"

        logger.info(
            "PerformanceAgent: %d issues, complexity=%s, memory=%s",
            len(issues),
            time_complexity,
            memory_usage,
        )

        return {
            "agent": "PerformanceAgent",
            "time_complexity": time_complexity,
            "memory_usage": memory_usage,
            "issue_count": len(issues),
            "issues": issues,
            "suggestions": list({i["suggestion"] for i in issues}),
            "verdict": verdict,
        }
