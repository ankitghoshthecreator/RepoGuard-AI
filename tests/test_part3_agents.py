from backend.app.part3_agents.orchestrator import LangGraphOrchestrator
from backend.app.part3_agents.security_agent import SecurityAgent

def test_orchestrator():
    orchestrator = LangGraphOrchestrator()
    res = orchestrator.run_pr_review_workflow("diff --git ...", {})
    assert res["status"] == "completed"
    assert "pr_summary" in res

def test_security_agent():
    agent = SecurityAgent()
    res = agent.analyze("+ import os")
    assert res["status"] == "PASS"
