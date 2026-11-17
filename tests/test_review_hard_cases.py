"""Adversarial and boundary tests for the persistent review API."""
import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.main import app
from backend.app.part3_agents.orchestrator import LangGraphOrchestrator
from backend.app.part4_api import reviews
from backend.app.part4_api.persistence import (
    Base, FindingRecord, ReviewEvent, ReviewRecord, SessionLocal, engine,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_review_tables():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


@pytest.mark.parametrize("payload", [
    {}, {"diff_text": ""}, {"diff_text": " \n\t "},
])
def test_missing_or_blank_review_input_is_rejected(payload):
    with pytest.raises(ValidationError):
        reviews.CreateReview.model_validate(payload)


def test_diff_exactly_at_limit_is_valid(monkeypatch):
    monkeypatch.setattr(reviews.settings, "MAX_DIFF_SIZE", 8)
    assert reviews.CreateReview(diff_text="12345678").diff_text == "12345678"


def test_diff_one_character_over_limit_is_rejected(monkeypatch):
    monkeypatch.setattr(reviews.settings, "MAX_DIFF_SIZE", 8)
    with pytest.raises(ValidationError):
        reviews.CreateReview(diff_text="123456789")


@pytest.mark.parametrize("options", [
    {}, {"agents": []}, {"agents": ["security"]}, {"unknown": {"nested": True}},
    {"agents": ["security", "performance"], "budget": 0},
])
def test_options_are_json_safe_and_defaulted(options):
    assert reviews.CreateReview(diff_text="+x=1", options=options).options == options


@pytest.mark.parametrize("url", [
    "http://github.com/org/repo", "https://gitlab.com/org/repo",
    "https://github.com.evil.invalid/org/repo", "https://evil.github.com/org/repo",
    "https://127.0.0.1/org/repo", "https://localhost/org/repo",
    "https://[::1]/org/repo", "file:///etc/passwd", "ftp://github.com/org/repo",
    "//github.com/org/repo", "https://github.com@127.0.0.1/org/repo",
    "https://user:pass@github.com/org/repo", "https://github.com:8443/org/repo",
    "https://github.com:bad/org/repo", "https://github.com/org/repo#fragment",
    "https://github.com/org", "https://github.com/org/repo/extra",
    "https://github.com//repo", "https://github.com/org/../repo",
    "https://github.com/org/repo/pull/1",
])
def test_invalid_repo_urls_are_rejected(url):
    with pytest.raises(ValidationError):
        reviews.CreateReview(repo_url=url)


@pytest.mark.parametrize("url", [
    "https://github.com/org/repo/pull/0", "https://github.com/org/repo/pull/1",
    "https://www.github.com/org/repo/pull/42/files", "https://github.com/org/repo/pull/17?x=1",
    "https://github.com/org/repo/pull/999999999999999999999999",
])
def test_valid_public_pull_request_urls_are_accepted(url):
    assert reviews.CreateReview(pr_url=url).pr_url == url


@pytest.mark.parametrize("url", [
    "https://github.com/org/repo", "https://github.com/org/repo/issues/3",
    "https://github.com/org/repo/pull/not-a-number", "https://github.com/org/repo/pull/",
    "https://github.com/org/repo/pull/-1", "https://github.com/org/repo/tree/main",
    "https://github.com/org/repo/pull/1/pull/2", "https://github.com/org/repo/pull/1/../../other",
])
def test_malformed_pull_request_paths_are_rejected(url):
    with pytest.raises(ValidationError):
        reviews.CreateReview(pr_url=url)


@pytest.mark.parametrize("url,expected", [
    ("https://github.com/org/repo/pull/9", "https://github.com/org/repo/pull/9.diff"),
    ("https://github.com/org/repo/pull/9/files", "https://github.com/org/repo/pull/9.diff"),
    ("https://www.github.com/org/repo/pull/9?tab=files", "https://github.com/org/repo/pull/9.diff"),
])
def test_diff_fetch_uses_canonical_github_diff_url(url, expected):
    response = MagicMock(status_code=200, text="diff --git a/a b/a\n")
    client_mock = MagicMock()
    client_mock.__enter__.return_value.get.return_value = response
    with patch.object(reviews.httpx, "Client", return_value=client_mock) as factory:
        result = reviews.resolve_diff(type("Job", (), {"repo_url": url})())
    assert result.startswith("diff --git")
    factory.assert_called_once_with(follow_redirects=False, timeout=20)
    client_mock.__enter__.return_value.get.assert_called_once()
    assert client_mock.__enter__.return_value.get.call_args.args[0] == expected


@pytest.mark.parametrize("status_code", [301, 302, 403, 404, 429, 500])
def test_diff_fetch_rejects_redirects_and_http_errors(status_code):
    response = MagicMock(status_code=status_code, text="blocked")
    response.raise_for_status.side_effect = RuntimeError("HTTP error")
    client_mock = MagicMock()
    client_mock.__enter__.return_value.get.return_value = response
    with patch.object(reviews.httpx, "Client", return_value=client_mock):
        with pytest.raises(RuntimeError):
            reviews.resolve_diff(type("Job", (), {"repo_url": "https://github.com/a/b/pull/1"})())


def test_diff_fetch_rejects_payload_larger_than_configured_limit(monkeypatch):
    monkeypatch.setattr(reviews.settings, "MAX_DIFF_SIZE", 5)
    client_mock = MagicMock()
    client_mock.__enter__.return_value.get.return_value = MagicMock(text="123456", raise_for_status=MagicMock())
    with patch.object(reviews.httpx, "Client", return_value=client_mock):
        with pytest.raises(ValueError, match="size limit"):
            reviews.resolve_diff(type("Job", (), {"repo_url": "https://github.com/a/b/pull/1"})())


@pytest.mark.parametrize("page,page_size", [(0, 20), (-1, 20), (1, 0), (1, 101)])
def test_review_list_rejects_out_of_range_pagination(page, page_size):
    response = client.get(f"/api/v1/reviews/?page={page}&page_size={page_size}")
    assert response.status_code == 422


def test_unknown_review_detail_has_consistent_not_found_payload():
    response = client.get(f"/api/v1/reviews/{uuid.uuid4()}/")
    assert response.status_code == 404
    assert response.json()["detail"]["error"]["code"] == "not_found"


def test_list_filters_status_and_repository_and_returns_page_metadata():
    with SessionLocal() as db:
        db.add_all([
            ReviewRecord(id="a", repo_url="https://github.com/acme/api", status="completed"),
            ReviewRecord(id="b", repo_url="https://github.com/acme/web", status="failed"),
            ReviewRecord(id="c", repo_url="https://github.com/other/api", status="completed"),
        ])
        db.commit()
    response = client.get("/api/v1/reviews/?status=completed&repo=acme&page=1&page_size=1")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert body["items"][0]["id"] == "a"


def test_review_detail_includes_findings_events_and_result():
    with SessionLocal() as db:
        db.add(ReviewRecord(id="review-1", status="completed", result={"pr_summary": "safe"}))
        db.flush()
        db.add(FindingRecord(review_id="review-1", message="unsafe", severity="HIGH"))
        db.add(ReviewEvent(review_id="review-1", event="done", data={"status": "completed"}))
        db.commit()
    body = client.get("/api/v1/reviews/review-1/").json()
    assert body["summary"] == "safe"
    assert body["findings"][0]["severity"] == "HIGH"
    assert body["events"][0]["event"] == "done"


def test_create_diff_review_returns_accepted_and_persists_input():
    with patch("backend.app.part4_api.reviews.run_job"):
        response = client.post("/api/v1/reviews/", json={"diff_text": "+def f(): pass"})
    assert response.status_code == 202
    job_id = response.json()["id"]
    with SessionLocal() as db:
        job = db.get(ReviewRecord, job_id)
        assert job.status == "queued"
        assert job.input_diff == "+def f(): pass"


def test_create_review_rejects_invalid_url_before_enqueue():
    response = client.post("/api/v1/reviews/", json={"pr_url": "https://127.0.0.1/a/b/pull/1"})
    assert response.status_code == 422


def test_create_review_without_input_returns_validation_error():
    assert client.post("/api/v1/reviews/", json={}).status_code == 422


def test_rerun_reuses_stored_diff_and_creates_new_job():
    with SessionLocal() as db:
        db.add(ReviewRecord(id="old", repo_url="https://github.com/a/b/pull/1", input_diff="+x=2"))
        db.commit()
    with patch("backend.app.part4_api.reviews.run_job"):
        response = client.post("/api/v1/reviews/old/rerun/")
    assert response.status_code == 202
    assert response.json()["id"] != "old"
    with SessionLocal() as db:
        assert db.get(ReviewRecord, response.json()["id"]).input_diff == "+x=2"


def test_rerun_missing_review_returns_404():
    assert client.post("/api/v1/reviews/not-here/rerun/").status_code == 404


def test_rerun_without_retained_input_returns_409():
    with SessionLocal() as db:
        db.add(ReviewRecord(id="no-input"))
        db.commit()
    assert client.post("/api/v1/reviews/no-input/rerun/").status_code == 409


def test_sse_unknown_review_returns_404():
    assert client.get(f"/api/v1/reviews/{uuid.uuid4()}/stream/").status_code == 404


def test_sse_emits_saved_events_for_finished_job():
    with SessionLocal() as db:
        db.add(ReviewRecord(id="stream-1", status="completed"))
        db.flush()
        db.add(ReviewEvent(review_id="stream-1", event="node_started", data={"node": "security"}))
        db.add(ReviewEvent(review_id="stream-1", event="done", data={"status": "completed"}))
        db.commit()
    response = client.get("/api/v1/reviews/stream-1/stream/")
    assert response.status_code == 200
    assert "event: node_started" in response.text
    assert '"node": "security"' in response.text
    assert "event: done" in response.text


def test_orchestrator_emits_all_agent_boundaries_in_order(monkeypatch):
    class Security:
        def analyze(self, _): return {"agent": "SecurityAgent"}
    class Architecture:
        def analyze(self, _): return {"agent": "ArchitectureAgent"}
    class Performance:
        def analyze(self, _): return {"agent": "PerformanceAgent"}
    class Testing:
        def analyze_diff(self, _): return {"agent": "TestingAgent"}
    class Reviewer:
        def synthesize_report(self, _): return {"status": "completed"}
    monkeypatch.setattr("backend.app.part3_agents.orchestrator.SecurityAgent", Security)
    monkeypatch.setattr("backend.app.part3_agents.orchestrator.ArchitectureAgent", Architecture)
    monkeypatch.setattr("backend.app.part3_agents.orchestrator.PerformanceAgent", Performance)
    monkeypatch.setattr("backend.app.part3_agents.orchestrator.TestingAgent", Testing)
    monkeypatch.setattr("backend.app.part3_agents.orchestrator.ReviewerAgent", Reviewer)
    events = []
    result = LangGraphOrchestrator().run_pr_review_workflow("diff", {}, lambda name, data: events.append((name, data["node"])))
    assert result["status"] == "completed"
    assert events == [(kind, node) for node in ("security", "architecture", "performance", "testing", "synthesis")
                      for kind in ("node_started", "node_completed")]

