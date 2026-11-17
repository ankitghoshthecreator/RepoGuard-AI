"""Run with: python -m backend.app.mcp_server (stdio transport)."""
from mcp.server.fastmcp import FastMCP
from backend.app.part3_agents.orchestrator import LangGraphOrchestrator
from backend.app.part4_api.persistence import SessionLocal, ReviewRecord, FindingRecord

mcp = FastMCP("RepoGuard AI")


@mcp.tool()
def review_diff(diff_text: str) -> dict:
    """Run the RepoGuard multi-agent review on a unified diff."""
    return LangGraphOrchestrator().run_pr_review_workflow(diff_text, {})


@mcp.tool()
def get_review(review_id: str) -> dict:
    """Get the status and result of a persisted review."""
    with SessionLocal() as db:
        review = db.get(ReviewRecord, review_id)
        if not review:
            return {"error": "Review not found"}
        return {"id": review.id, "status": review.status, "result": review.result,
                "error": review.error}


@mcp.tool()
def list_findings(review_id: str) -> list[dict]:
    """List persisted findings for a review."""
    with SessionLocal() as db:
        return [{"file_path": item.file_path, "line": item.line,
                 "severity": item.severity, "category": item.category,
                 "message": item.message, "suggested_fix": item.suggested_fix,
                 "agent_name": item.agent_name}
                for item in db.query(FindingRecord).filter_by(review_id=review_id).all()]


if __name__ == "__main__":
    mcp.run(transport="stdio")
