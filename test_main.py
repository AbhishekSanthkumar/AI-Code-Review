import pytest
from fastapi.testclient import TestClient
import hmac, hashlib, json, os, tempfile
from unittest.mock import patch, AsyncMock
from main import app, WEBHOOK_SECRET
from storage import init_db, already_reviewed, save_review

client = TestClient(app)

def make_signature(payload: bytes) -> str:
    sig = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return f"sha256={sig}"

def make_pr_payload(action="opened", draft=False):
    return {
        "action": action,
        "pull_request": {
            "number": 1,
            "title": "Test PR",
            "body": "Test description",
            "draft": draft,
            "head": {"sha": "abc123def456", "ref": "feature/test"},
            "base": {"sha": "def456", "ref": "main"},
            "changed_files": 2,
        },
        "repository": {"full_name": "user/test-repo"},
        "sender": {"login": "testuser"},
        "installation": {"id": 12345},
    }

# ── Signature tests ───────────────────────────────────────

def test_invalid_signature_returns_401():
    payload = json.dumps(make_pr_payload()).encode()
    response = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "sha256=invalidsignature",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 401

def test_missing_signature_returns_401():
    payload = json.dumps(make_pr_payload()).encode()
    response = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-GitHub-Event": "pull_request",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 401

# ── Event routing tests ───────────────────────────────────

def test_non_pr_event_is_ignored():
    payload = json.dumps({"action": "created"}).encode()
    response = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": make_signature(payload),
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"

def test_draft_pr_is_ignored():
    payload = json.dumps(make_pr_payload(draft=True)).encode()
    response = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": make_signature(payload),
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"

def test_closed_action_is_ignored():
    payload = json.dumps(make_pr_payload(action="closed")).encode()
    response = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": make_signature(payload),
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"

# ── Valid PR test ─────────────────────────────────────────

def test_valid_pr_is_queued():
    payload = json.dumps(make_pr_payload()).encode()
    with patch("main.run_review", new_callable=AsyncMock):
        response = client.post(
            "/webhook",
            content=payload,
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": make_signature(payload),
                "Content-Type": "application/json",
            },
        )
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert response.json()["pr"] == 1

# ── Storage tests ─────────────────────────────────────────

def test_idempotency_prevents_duplicate_review():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        test_db = f.name

    with patch("storage.DB_PATH", test_db):
        init_db()
        assert already_reviewed("user/repo", 1, "sha123") == False
        save_review("user/repo", 1, "Test PR", "testuser", "sha123", "main", 1, 0, 0, 0)
        assert already_reviewed("user/repo", 1, "sha123") == True
        assert already_reviewed("user/repo", 1, "sha456") == False

    os.unlink(test_db)