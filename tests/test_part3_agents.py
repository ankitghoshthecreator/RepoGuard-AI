"""
Part 3 – Multi-Agent Reasoning Core: Tests
===========================================
Covers:
  - SecurityAgent:     clean diff → PASS; dangerous diff → FAIL
  - ArchitectureAgent: empty graph → valid metrics; populated graph → metrics
  - PerformanceAgent:  clean diff → PASS; nested loops → WARN
  - TestingAgent:      generates stubs for new function definitions
  - ReviewerAgent:     aggregates agent outputs correctly
  - LangGraphOrchestrator: end-to-end pipeline returns expected keys
"""

import pytest
from backend.app.part3_agents.orchestrator        import LangGraphOrchestrator
from backend.app.part3_agents.security_agent      import SecurityAgent
from backend.app.part3_agents.architecture_agent  import ArchitectureAgent
from backend.app.part3_agents.performance_agent   import PerformanceAgent
from backend.app.part3_agents.testing_agent       import TestingAgent
from backend.app.part3_agents.review_agent        import ReviewerAgent


# ══════════════════════════════════════════════════════════════════════
#  SecurityAgent
# ══════════════════════════════════════════════════════════════════════

class TestSecurityAgent:
    def test_clean_diff_passes(self):
        agent = SecurityAgent()
        res = agent.analyze("def hello(): return 'world'")
        assert res["agent"] == "SecurityAgent"
        assert res["status"] == "PASS"
        assert isinstance(res["findings"], list)
        assert isinstance(res["finding_count"], int)
        assert res["risk_score"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_hardcoded_secret_fails(self):
        agent = SecurityAgent()
        dangerous = 'api_key = "sk-super-secret-key-longerthan16chars"'
        res = agent.analyze(dangerous)
        # Should detect the hardcoded secret
        assert res["finding_count"] >= 1
        assert res["risk_score"] in ("MEDIUM", "HIGH", "CRITICAL")

    def test_eval_usage_detected(self):
        agent = SecurityAgent()
        res = agent.analyze("result = eval(user_input)")
        assert res["finding_count"] >= 1

    def test_result_schema(self):
        agent = SecurityAgent()
        res = agent.analyze("x = 1")
        for key in ("agent", "status", "risk_score", "finding_count", "findings", "recommendation"):
            assert key in res


# ══════════════════════════════════════════════════════════════════════
#  ArchitectureAgent
# ══════════════════════════════════════════════════════════════════════

class TestArchitectureAgent:
    def test_empty_graph_returns_valid_dict(self):
        agent = ArchitectureAgent()
        res = agent.analyze({})
        assert res["agent"] == "ArchitectureAgent"
        assert isinstance(res["cohesion_score"], float)
        assert isinstance(res["coupling_issue_detected"], bool)
        assert res["verdict"] in ("EXCELLENT", "GOOD", "WARN", "POOR")

    def test_populated_graph(self):
        """Inject a small NetworkX graph via graph_context."""
        import networkx as nx
        g = nx.DiGraph()
        g.add_edges_from([("A", "B"), ("B", "C"), ("A", "C")])
        agent = ArchitectureAgent()
        res = agent.analyze({"graph": g})
        assert res["node_count"] == 3
        assert res["edge_count"] == 3
        assert 0.0 <= res["cohesion_score"] <= 1.0

    def test_result_schema(self):
        agent = ArchitectureAgent()
        res = agent.analyze({})
        for key in ("agent", "architecture_pattern", "cohesion_score",
                    "coupling_issue_detected", "verdict", "node_count", "edge_count"):
            assert key in res


# ══════════════════════════════════════════════════════════════════════
#  PerformanceAgent
# ══════════════════════════════════════════════════════════════════════

class TestPerformanceAgent:
    def test_clean_code_passes(self):
        agent = PerformanceAgent()
        res = agent.analyze("def foo(): return 42")
        assert res["agent"] == "PerformanceAgent"
        assert res["verdict"] == "PASS"
        assert res["issue_count"] == 0

    def test_nested_loops_warn(self):
        agent = PerformanceAgent()
        diff = "\n".join([
            "for i in range(n):",
            "    for j in range(n):",
            "        result += i * j",
        ])
        res = agent.analyze(diff)
        assert res["time_complexity"] in ("O(N²)", "O(N log N)")

    def test_result_schema(self):
        agent = PerformanceAgent()
        res = agent.analyze("x = 1")
        for key in ("agent", "time_complexity", "memory_usage",
                    "issue_count", "issues", "suggestions", "verdict"):
            assert key in res


# ══════════════════════════════════════════════════════════════════════
#  TestingAgent
# ══════════════════════════════════════════════════════════════════════

class TestTestingAgent:
    def test_generate_tests_returns_string(self):
        agent = TestingAgent()
        result = agent.generate_tests("my_function", "def my_function(): pass")
        assert isinstance(result, str)
        assert "test_my_function" in result

    def test_analyze_diff_detects_new_functions(self):
        agent = TestingAgent()
        diff = (
            "+def compute_hash(data: str) -> str:\n"
            "+    return hashlib.sha256(data.encode()).hexdigest()\n"
        )
        res = agent.analyze_diff(diff)
        assert res["agent"] == "TestingAgent"
        assert "compute_hash" in res["functions_found"]
        assert res["stub_count"] >= 1
        assert "pytest" in res["generated_tests"]

    def test_no_functions_in_diff(self):
        agent = TestingAgent()
        res = agent.analyze_diff("x = 1\ny = 2\n")
        assert res["stub_count"] == 0


# ══════════════════════════════════════════════════════════════════════
#  ReviewerAgent
# ══════════════════════════════════════════════════════════════════════

class TestReviewerAgent:
    def _sample_outputs(self, sec_status="PASS", sec_risk="LOW",
                         arch_verdict="GOOD", perf_verdict="PASS"):
        return [
            {"agent": "SecurityAgent",     "status": sec_status,
             "risk_score": sec_risk,       "finding_count": 0, "findings": []},
            {"agent": "ArchitectureAgent", "verdict": arch_verdict,
             "cohesion_score": 0.5,        "coupling_issue_detected": False,
             "node_count": 5,              "edge_count": 4},
            {"agent": "PerformanceAgent",  "verdict": perf_verdict,
             "time_complexity": "O(N)",    "issue_count": 0, "issues": []},
            {"agent": "TestingAgent",      "stub_count": 2,
             "functions_found": ["foo", "bar"], "generated_tests": "import pytest\n"},
        ]

    def test_approved_on_clean_inputs(self):
        agent = ReviewerAgent()
        res = agent.synthesize_report(self._sample_outputs())
        assert res["status"] == "completed"
        assert res["overall_status"] == "APPROVED"
        assert res["risk_score"] == "LOW"

    def test_blocked_on_critical_security(self):
        agent = ReviewerAgent()
        outputs = self._sample_outputs(sec_status="FAIL", sec_risk="CRITICAL")
        res = agent.synthesize_report(outputs)
        assert res["overall_status"] == "BLOCKED"

    def test_result_schema(self):
        agent = ReviewerAgent()
        res = agent.synthesize_report(self._sample_outputs())
        for key in ("status", "overall_status", "risk_score",
                    "pr_summary", "checklist", "agent_findings"):
            assert key in res

    def test_checklist_has_four_items(self):
        agent = ReviewerAgent()
        res = agent.synthesize_report(self._sample_outputs())
        assert len(res["checklist"]) == 4


# ══════════════════════════════════════════════════════════════════════
#  LangGraphOrchestrator — end-to-end pipeline
# ══════════════════════════════════════════════════════════════════════

class TestLangGraphOrchestrator:
    _CLEAN_DIFF = (
        "diff --git a/utils.py b/utils.py\n"
        "--- a/utils.py\n"
        "+++ b/utils.py\n"
        "@@ -1,3 +1,6 @@\n"
        "+def format_name(first: str, last: str) -> str:\n"
        '+    """Return a formatted full name."""\n'
        "+    return f'{first} {last}'.strip()\n"
    )

    def test_pipeline_returns_completed_status(self):
        orc = LangGraphOrchestrator()
        res = orc.run_pr_review_workflow(self._CLEAN_DIFF, {})
        assert res["status"] == "completed"

    def test_pipeline_overall_status_present(self):
        orc = LangGraphOrchestrator()
        res = orc.run_pr_review_workflow(self._CLEAN_DIFF, {})
        assert res["overall_status"] in ("APPROVED", "CHANGES_REQUESTED", "BLOCKED")

    def test_pipeline_pr_summary_present(self):
        orc = LangGraphOrchestrator()
        res = orc.run_pr_review_workflow(self._CLEAN_DIFF, {})
        assert "pr_summary" in res
        assert isinstance(res["pr_summary"], str)
        assert len(res["pr_summary"]) > 10

    def test_pipeline_all_agents_in_findings(self):
        orc = LangGraphOrchestrator()
        res = orc.run_pr_review_workflow(self._CLEAN_DIFF, {})
        findings = res["agent_findings"]
        assert "security" in findings
        assert "architecture" in findings
        assert "performance" in findings
        assert "testing" in findings

    def test_pipeline_checklist_populated(self):
        orc = LangGraphOrchestrator()
        res = orc.run_pr_review_workflow(self._CLEAN_DIFF, {})
        assert isinstance(res["checklist"], list)
        assert len(res["checklist"]) > 0

    def test_pipeline_with_dangerous_diff(self):
        """A diff containing eval() should not crash the pipeline."""
        orc = LangGraphOrchestrator()
        dangerous = '+result = eval(user_input)\n+exec(cmd)\n'
        res = orc.run_pr_review_workflow(dangerous, {})
        assert res["status"] == "completed"
        sec = res["agent_findings"]["security"]
        assert sec.get("finding_count", 0) >= 1

    def test_empty_diff_handled_gracefully(self):
        orc = LangGraphOrchestrator()
        res = orc.run_pr_review_workflow("", {})
        assert res["status"] == "completed"
