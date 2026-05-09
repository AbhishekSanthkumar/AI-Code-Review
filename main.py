from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from dataclasses import dataclass
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from github_client import fetch_pr_files
from reviewer import review_pr
from comment_poster import post_review, post_error_comment
from storage import init_db, already_reviewed, save_review, save_comments, DB_PATH
import hmac, hashlib, os, json

load_dotenv()

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")

# ── Lifespan ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app):
    init_db()
    print("[server] Database initialized")
    yield

app = FastAPI(lifespan=lifespan)

# ── Data model ────────────────────────────────────────────

@dataclass
class PREvent:
    action: str
    repo_name: str
    pr_number: int
    pr_title: str
    pr_body: str
    head_sha: str
    base_ref: str
    author: str
    is_draft: bool
    changed_files: int
    installation_id: str

# ── Signature verification ────────────────────────────────

def verify_signature(payload: bytes, signature: str) -> bool:
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

# ── Payload parser ────────────────────────────────────────

def parse_pr_payload(payload: dict) -> PREvent | None:
    action = payload.get("action", "")

    if action not in ("opened", "synchronize", "reopened"):
        return None

    pr     = payload["pull_request"]
    author = payload["sender"]["login"]

    if pr.get("draft", False):
        return None
    if author.endswith("[bot]") or author in ("dependabot", "renovate"):
        return None

    return PREvent(
        action=action,
        repo_name=payload["repository"]["full_name"],
        pr_number=pr["number"],
        pr_title=pr["title"],
        pr_body=pr.get("body") or "",
        head_sha=pr["head"]["sha"],
        base_ref=pr["base"]["ref"],
        author=author,
        is_draft=pr["draft"],
        changed_files=pr["changed_files"],
        installation_id=str(payload["installation"]["id"]),
    )

# ── Review pipeline ───────────────────────────────────────

async def run_review(event: PREvent):
    print(f"[review] PR #{event.pr_number} in {event.repo_name}")
    print(f"[idempotency] SHA: {event.head_sha[:12]} | DB: {DB_PATH}")

    if already_reviewed(event.repo_name, event.pr_number, event.head_sha):
        print(f"[idempotency] Already reviewed — SKIPPING ✓")
        return

    try:
        files = await fetch_pr_files(
            event.repo_name, event.pr_number, event.installation_id
        )
        print(f"[review] Fetched {len(files)} files")

        if not files:
            print("[review] No reviewable files — skipping")
            return

        summary, comments = await review_pr(
            event.pr_title, event.pr_body, files
        )

        await post_review(
            repo_name=event.repo_name,
            pr_number=event.pr_number,
            head_sha=event.head_sha,
            installation_id=event.installation_id,
            comments=comments,
            summary=summary,
        )

        critical    = sum(1 for c in comments if c.severity == "critical")
        warnings    = sum(1 for c in comments if c.severity == "warning")
        suggestions = sum(1 for c in comments if c.severity == "suggestion")

        review_id = save_review(
            repo=event.repo_name,
            pr_number=event.pr_number,
            pr_title=event.pr_title,
            author=event.author,
            head_sha=event.head_sha,
            base_ref=event.base_ref,
            total_files=len(files),
            critical=critical,
            warnings=warnings,
            suggestions=suggestions,
        )
        save_comments(review_id, event.repo_name, event.pr_number, comments)
        score = 100 - (critical * 25) - (warnings * 10) - (suggestions * 2)
        print(f"[db] Saved review {review_id} — score: {max(0, score)}")

    except Exception as e:
        print(f"[review] ERROR: {e}")
        await post_error_comment(
            repo_name=event.repo_name,
            pr_number=event.pr_number,
            installation_id=event.installation_id,
            error=str(e),
        )

# ── Webhook endpoint ──────────────────────────────────────

@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    payload_bytes = await request.body()
    sig = request.headers.get("X-Hub-Signature-256", "")

    if not verify_signature(payload_bytes, sig):
        raise HTTPException(status_code=401, detail="Invalid signature")

    event_type = request.headers.get("X-GitHub-Event")

    if event_type != "pull_request":
        return {"status": "ignored"}

    payload  = json.loads(payload_bytes)
    pr_event = parse_pr_payload(payload)

    if pr_event is None:
        return {"status": "ignored"}

    background_tasks.add_task(run_review, pr_event)
    return {"status": "queued", "pr": pr_event.pr_number}