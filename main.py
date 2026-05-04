from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from dataclasses import dataclass
from dotenv import load_dotenv
import hmac, hashlib, os, json

load_dotenv()

app = FastAPI()
WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")

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

    # skip draft PRs and bots
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

# ── Review pipeline (stub for now) ───────────────────────

async def run_review(event: PREvent):
    print(f"[review] Starting review for PR #{event.pr_number} in {event.repo_name}")
    print(f"[review] Author: {event.author} | Files changed: {event.changed_files}")
    print(f"[review] Head SHA: {event.head_sha}")
    # github_client.py wired in next step

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