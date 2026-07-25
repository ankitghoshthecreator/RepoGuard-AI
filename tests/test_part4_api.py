import jwt
import json
import hmac
import hashlib
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.config import settings

client = TestClient(app)

def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "modules" in data

@patch("backend.app.part1_parser.ingestion.RepoIngestor.from_github")
@patch("backend.app.part1_parser.ingestion.RepoIngestor.manifest")
def test_unauthenticated_ingest_succeeds_with_guest_fallback(mock_manifest, mock_from_github):
    mock_manifest.return_value = {"total_files": 5, "files": []}
    
    response = client.post("/api/v1/ingest", json={"repo_url": "https://github.com/test/repo"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "5 files" in data["summary"]

@patch("backend.app.part1_parser.ingestion.RepoIngestor.from_github")
@patch("backend.app.part1_parser.ingestion.RepoIngestor.manifest")
def test_authenticated_ingest_success(mock_manifest, mock_from_github):
    mock_manifest.return_value = {"total_files": 10, "files": []}
    
    token_payload = {"user": "admin", "role": "lead_engineer"}
    token = jwt.encode(token_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/api/v1/ingest",
        json={"repo_url": "https://github.com/test/repo"},
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

def test_invalid_jwt_token():
    headers = {"Authorization": "Bearer invalid_token_value"}
    response = client.post(
        "/api/v1/ingest",
        json={"repo_url": "https://github.com/test/repo"},
        headers=headers
    )
    assert response.status_code == 401

def test_webhook_invalid_signature():
    headers = {
        "X-Github-Event": "pull_request",
        "X-Hub-Signature-256": "sha256=invalid_signature"
    }
    response = client.post("/api/v1/webhooks/github", json={}, headers=headers)
    assert response.status_code == 401

@patch("backend.app.part4_api.webhooks.fetch_pr_diff")
@patch("backend.app.part4_api.webhooks.process_webhook_review")
def test_webhook_valid_signature(mock_process, mock_fetch):
    mock_fetch.return_value = "+# def foo():\n+    pass\n"
    
    payload = {
        "action": "opened",
        "number": 1,
        "pull_request": {
            "diff_url": "https://github.com/test/repo/pull/1.diff",
            "url": "https://github.com/test/repo/pull/1"
        },
        "repository": {
            "full_name": "test/repo"
        }
    }
    
    body = json.dumps(payload).encode("utf-8")
    
    secret = settings.GITHUB_WEBHOOK_SECRET.encode("utf-8")
    signature = hmac.new(secret, body, hashlib.sha256).hexdigest()
    
    headers = {
        "X-Github-Event": "pull_request",
        "X-Hub-Signature-256": f"sha256={signature}",
        "Content-Type": "application/json"
    }
    
    response = client.post("/api/v1/webhooks/github", content=body, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert "background" in data["message"]
