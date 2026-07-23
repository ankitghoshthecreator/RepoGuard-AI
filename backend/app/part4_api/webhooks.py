from fastapi import APIRouter, Request, Header, HTTPException

webhook_router = APIRouter()

@webhook_router.post("/github")
async def github_webhook(request: Request, x_github_event: str = Header(None)):
    """Receives and processes GitHub Webhooks (Pull Requests, Pushes)."""
    payload = await request.json()
    if x_github_event == "pull_request":
        action = payload.get("action")
        pr_number = payload.get("number")
        return {
            "status": "received",
            "event": x_github_event,
            "action": action,
            "pr_number": pr_number,
            "message": "Triggered Multi-Agent Review Workflow."
        }
    return {"status": "ignored", "event": x_github_event}
