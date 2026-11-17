"""Persistent asynchronous review jobs, detail, and SSE event stream."""
import json
import logging
import re
import threading
import uuid
from types import SimpleNamespace
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

from backend.app.config import settings
from backend.app.part3_agents.orchestrator import LangGraphOrchestrator
from .persistence import SessionLocal, ReviewRecord, ReviewEvent, FindingRecord

logger = logging.getLogger("repoguard.reviews")
reviews_router = APIRouter()


class CreateReview(BaseModel):
    repo_url: str | None = None
    pr_url: str | None = None
    diff_text: str | None = None
    options: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_source(self):
        if not (self.diff_text and self.diff_text.strip()) and not (self.repo_url or self.pr_url):
            raise ValueError("Provide repo_url, pr_url, or diff_text")
        if self.diff_text and len(self.diff_text) > settings.MAX_DIFF_SIZE:
            raise ValueError(f"diff_text exceeds {settings.MAX_DIFF_SIZE} characters")
        for value in (self.repo_url, self.pr_url):
            if value:
                parsed = urlparse(value)
                if (parsed.scheme != "https" or parsed.hostname not in {"github.com", "www.github.com"}
                        or parsed.username or parsed.password or parsed.port not in (None, 443)
                        or parsed.fragment):
                    raise ValueError("Only public GitHub HTTPS URLs are supported")
                segments = parsed.path.strip("/").split("/")
                if value == self.pr_url:
                    valid_tail = len(segments) == 4 or (
                        len(segments) == 5 and segments[4] in {"files", "commits", "checks", "conversation"}
                    )
                    if (len(segments) < 4 or segments[2] != "pull" or not segments[3].isdigit()
                            or not valid_tail):
                        raise ValueError("pr_url must identify a GitHub pull request")
                elif len(segments) != 2 or not all(segments):
                    raise ValueError("repo_url must identify a GitHub repository")
        return self


def emit(review_id: str, event: str, data: dict):
    with SessionLocal() as db:
        db.add(ReviewEvent(review_id=review_id, event=event, data=data))
        db.commit()


def resolve_diff(job: ReviewRecord) -> str:
    if hasattr(job, "_diff_text"):
        return job._diff_text
    url = job.repo_url or ""
    if "/pull/" not in url:
        raise ValueError("A PR URL or diff_text is required to run a review")
    parsed = urlparse(url)
    parts = parsed.path.strip("/").split("/")
    if len(parts) < 4 or parts[2] != "pull" or not parts[3].isdigit():
        raise ValueError("Invalid GitHub pull request URL")
    diff_url = f"https://github.com/{parts[0]}/{parts[1]}/pull/{parts[3]}.diff"
    headers = {"Accept": "application/vnd.github.v3.diff"}
    if settings.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"
    with httpx.Client(follow_redirects=False, timeout=20) as client:
        response = client.get(diff_url, headers=headers)
        response.raise_for_status()
    if len(response.text) > settings.MAX_DIFF_SIZE:
        raise ValueError("GitHub diff exceeds configured size limit")
    return response.text


def run_job(review_id: str, diff_text: str):
    with SessionLocal() as db:
        job = db.get(ReviewRecord, review_id)
        if not job:
            return
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        db.commit()
    emit(review_id, "started", {"review_id": review_id})
    try:
        report = LangGraphOrchestrator().run_pr_review_workflow(
            diff_text, {}, progress_callback=lambda event, data: emit(review_id, event, data)
        )
        with SessionLocal() as db:
            job = db.get(ReviewRecord, review_id)
            job.status = "completed"
            job.finished_at = datetime.now(timezone.utc)
            job.result = report
            for agent, output in report.get("agent_findings", {}).items():
                for finding in output.get("findings", []) if isinstance(output, dict) else []:
                    if isinstance(finding, dict):
                        db.add(FindingRecord(review_id=review_id,
                            file_path=finding.get("file_path", finding.get("filename", "<diff>")),
                            line=finding.get("line"), severity=str(finding.get("severity", "INFO")).upper(),
                            category=finding.get("category", agent), message=finding.get("message", str(finding)),
                            suggested_fix=finding.get("suggested_fix"), agent_name=agent))
            db.commit()
        emit(review_id, "done", {"status": "completed"})
    except Exception:
        logger.exception("Review %s failed", review_id)
        with SessionLocal() as db:
            job = db.get(ReviewRecord, review_id)
            if job:
                job.status = "failed"
                job.error = "Review failed; see server logs for details."
                job.finished_at = datetime.now(timezone.utc)
                db.commit()
        emit(review_id, "error", {"message": "Review failed"})


def serialize(record: ReviewRecord):
    return {"id": record.id, "repo_url": record.repo_url, "ref": record.ref,
            "status": record.status, "created_at": record.created_at.isoformat() if record.created_at else None,
            "started_at": record.started_at.isoformat() if record.started_at else None,
            "finished_at": record.finished_at.isoformat() if record.finished_at else None,
            "summary": (record.result or {}).get("pr_summary"),
            "result": record.result, "error": record.error}


@reviews_router.post("/reviews/", status_code=202)
def create_review(payload: CreateReview):
    review_id = str(uuid.uuid4())
    url = payload.pr_url or payload.repo_url
    ref = urlparse(url).path if url else None
    job = ReviewRecord(id=review_id, repo_url=url, ref=ref, input_diff=payload.diff_text)
    with SessionLocal() as db:
        db.add(job)
        db.commit()
    emit(review_id, "queued", {"status": "queued"})
    diff_text = payload.diff_text
    if diff_text is None:
        # URL resolution and the existing review pipeline run in the worker.
        threading.Thread(target=_run_url_job, args=(review_id,), daemon=True).start()
    else:
        threading.Thread(target=run_job, args=(review_id, diff_text), daemon=True).start()
    return {"id": review_id, "status": "queued"}


def _run_url_job(review_id: str):
    with SessionLocal() as db:
        job = db.get(ReviewRecord, review_id)
        if not job:
            return
        repo_url = job.repo_url
    try:
        diff = resolve_diff(SimpleNamespace(repo_url=repo_url))
        run_job(review_id, diff)
    except Exception:
        logger.exception("Unable to prepare review %s", review_id)
        with SessionLocal() as db:
            job = db.get(ReviewRecord, review_id)
            if job:
                job.status = "failed"
                job.error = "Unable to fetch the GitHub pull request diff."
                job.finished_at = datetime.now(timezone.utc)
                db.commit()
        emit(review_id, "error", {"message": "Unable to fetch the GitHub pull request diff"})


@reviews_router.get("/reviews/")
def list_reviews(status: str | None = None, repo: str | None = None,
                 page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    with SessionLocal() as db:
        query = db.query(ReviewRecord)
        if status:
            query = query.filter(ReviewRecord.status == status)
        if repo:
            query = query.filter(ReviewRecord.repo_url.contains(repo))
        total = query.count()
        records = query.order_by(ReviewRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return {"items": [serialize(record) for record in records], "page": page, "page_size": page_size, "total": total}


@reviews_router.get("/reviews/{review_id}/")
def get_review(review_id: str):
    with SessionLocal() as db:
        job = db.get(ReviewRecord, review_id)
        if not job:
            raise HTTPException(404, detail={"error": {"code": "not_found", "message": "Review not found"}})
        result = serialize(job)
        result["findings"] = [dict(file_path=f.file_path, line=f.line, severity=f.severity,
                                   category=f.category, message=f.message,
                                   suggested_fix=f.suggested_fix, agent_name=f.agent_name)
                              for f in db.query(FindingRecord).filter_by(review_id=review_id).all()]
        result["events"] = [dict(event=e.event, data=e.data, created_at=e.created_at.isoformat())
                            for e in db.query(ReviewEvent).filter_by(review_id=review_id).order_by(ReviewEvent.id).all()]
        return result


@reviews_router.post("/reviews/{review_id}/rerun/", status_code=202)
def rerun_review(review_id: str):
    with SessionLocal() as db:
        old = db.get(ReviewRecord, review_id)
        if not old:
            raise HTTPException(404, detail={"error": {"code": "not_found", "message": "Review not found"}})
        diff = old.input_diff
        url = old.repo_url
        if diff:
            rerun_payload = CreateReview(diff_text=diff, pr_url=url if url and "/pull/" in url else None,
                                         repo_url=url if url and "/pull/" not in url else None)
        else:
            rerun_payload = None
        if not old.repo_url:
            raise HTTPException(409, detail={"error": {"code": "missing_input", "message": "Original diff was not retained; submit a new diff"}})
    if rerun_payload:
        return create_review(rerun_payload)
    return create_review(CreateReview(pr_url=url) if "/pull/" in url else CreateReview(repo_url=url))


@reviews_router.get("/reviews/{review_id}/stream/")
async def review_stream(review_id: str, request: Request):
    with SessionLocal() as db:
        if not db.get(ReviewRecord, review_id):
            raise HTTPException(404, detail={"error": {"code": "not_found", "message": "Review not found"}})

    async def events():
        cursor = 0
        while not await request.is_disconnected():
            with SessionLocal() as db:
                rows = db.query(ReviewEvent).filter(ReviewEvent.review_id == review_id, ReviewEvent.id > cursor).order_by(ReviewEvent.id).all()
                job = db.get(ReviewRecord, review_id)
                for row in rows:
                    cursor = row.id
                    yield f"event: {row.event}\ndata: {json.dumps(row.data)}\n\n"
                if job and job.status in {"completed", "failed"} and cursor >= (rows[-1].id if rows else cursor):
                    if job.status == "completed" or any(row.event == "error" for row in rows):
                        return
            import asyncio
            await asyncio.sleep(0.5)
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
