import hmac
import hashlib
import httpx
import logging
from fastapi import APIRouter, Request, Header, HTTPException, BackgroundTasks, status
from backend.app.config import settings
from backend.app.part3_agents.orchestrator import LangGraphOrchestrator

logger = logging.getLogger("repoguard.part4.webhooks")
webhook_router = APIRouter()

async def verify_signature(request: Request):
    """HMAC SHA256 verification of GitHub webhook signature."""
    signature_header = request.headers.get("X-Hub-Signature-256")
    if not signature_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Hub-Signature-256 header missing"
        )
    
    if not signature_header.startswith("sha256="):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature format"
        )
    
    signature = signature_header.split("sha256=")[1]
    body = await request.body()
    
    secret = settings.GITHUB_WEBHOOK_SECRET.encode("utf-8")
    computed = hmac.new(secret, body, hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(computed, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook signature verification failed"
        )

async def fetch_pr_diff(diff_url: str) -> str:
    """Fetch the PR diff from GitHub using the GITHUB_TOKEN."""
    if not settings.GITHUB_TOKEN:
        logger.warning("GITHUB_TOKEN not configured. Using simulated diff.")
        return "+# Simulated diff: GITHUB_TOKEN not configured\n+def dummy_func():\n+    pass\n"
    
    headers = {
        "Authorization": f"token {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3.diff"
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(diff_url, headers=headers, timeout=10.0)
            if resp.status_code == 200:
                return resp.text
            else:
                logger.error("Failed to fetch diff: HTTP %d", resp.status_code)
                return f"+# Error fetching diff: HTTP {resp.status_code}\n"
    except Exception as e:
        logger.exception("Exception fetching diff")
        return f"+# Exception fetching diff: {str(e)}\n"

def process_webhook_review(pr_diff: str, repo_context: dict):
    """Run multi-agent orchestrator in the background."""
    try:
        orchestrator = LangGraphOrchestrator()
        orchestrator.run_pr_review_workflow(pr_diff, repo_context)
    except Exception as e:
        logger.error("Background PR review failed: %s", str(e), exc_info=True)

@webhook_router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(None)
):
    """Receives and processes GitHub Webhooks (Pull Requests, Pushes)."""
    await verify_signature(request)
    payload = await request.json()
    
    if x_github_event == "pull_request":
        action = payload.get("action")
        pr_number = payload.get("number")
        
        if action in ("opened", "synchronize", "reopened"):
            pr_data = payload.get("pull_request", {})
            diff_url = pr_data.get("diff_url")
            
            if diff_url:
                pr_diff = await fetch_pr_diff(diff_url)
                repo_context = {
                    "repo_name": payload.get("repository", {}).get("full_name"),
                    "pr_number": pr_number,
                    "action": action
                }
                background_tasks.add_task(process_webhook_review, pr_diff, repo_context)
                
                return {
                    "status": "received",
                    "event": x_github_event,
                    "action": action,
                    "pr_number": pr_number,
                    "message": "Triggered Multi-Agent Review Workflow in background."
                }
        
        return {
            "status": "ignored",
            "event": x_github_event,
            "action": action,
            "message": "PR action not active for review"
        }
        
    return {"status": "ignored", "event": x_github_event}
