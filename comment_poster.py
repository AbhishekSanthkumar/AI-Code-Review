import httpx, os
from dataclasses import dataclass
from dotenv import load_dotenv
from github_client import get_installation_token, API_HEADERS, API_BASE
from reviewer import ReviewComment

load_dotenv()

# ── Formatting ────────────────────────────────────────────

def format_inline(c: ReviewComment) -> str:
    icons = {"critical": "🔴", "warning": "🟡", "suggestion": "🔵"}
    icon  = icons.get(c.severity, "⚪")
    return f"{icon} **{c.severity.capitalize()}**\n\n{c.body}"

def format_summary(summary: str, comments: list[ReviewComment]) -> str:
    critical   = sum(1 for c in comments if c.severity == "critical")
    warnings   = sum(1 for c in comments if c.severity == "warning")
    suggestions= sum(1 for c in comments if c.severity == "suggestion")
    return f"""## 🤖 AI Code Review

{summary}

---
**{len(comments)} comment(s)** — 🔴 {critical} critical · 🟡 {warnings} warnings · 🔵 {suggestions} suggestions

*Reviewed by AI — always verify suggestions before merging.*"""

# ── Poster ────────────────────────────────────────────────

async def post_review(
    repo_name: str,
    pr_number: int,
    head_sha: str,
    installation_id: str,
    comments: list[ReviewComment],
    summary: str,
):
    token   = await get_installation_token(installation_id)
    headers = {**API_HEADERS, "Authorization": f"Bearer {token}"}
    base    = f"{API_BASE}/repos/{repo_name}"

    async with httpx.AsyncClient() as client:
        # post inline comments as a single review
        if comments:
            inline = [
                {
                    "path": c.path,
                    "line": c.line,
                    "side": "RIGHT",
                    "body": format_inline(c),
                }
                for c in comments
            ]
            resp = await client.post(
                f"{base}/pulls/{pr_number}/reviews",
                headers=headers,
                json={
                    "commit_id": head_sha,
                    "body": "",
                    "event": "COMMENT",
                    "comments": inline,
                },
            )
            if resp.status_code not in (200, 201):
                print(f"[poster] Inline comments failed: {resp.status_code} {resp.text}")

        # always post the summary as a conversation comment
        await client.post(
            f"{base}/issues/{pr_number}/comments",
            headers=headers,
            json={"body": format_summary(summary, comments)},
        )
        print(f"[poster] Posted review — {len(comments)} inline comments")

async def post_error_comment(
    repo_name: str,
    pr_number: int,
    installation_id: str,
    error: str,
):
    token   = await get_installation_token(installation_id)
    headers = {**API_HEADERS, "Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        await client.post(
            f"{API_BASE}/repos/{repo_name}/issues/{pr_number}/comments",
            headers=headers,
            json={"body": f"""## 🤖 AI Code Review — Failed
                  The automated review encountered an error and could not complete.
                  Please check the server logs or retry by pushing a new commit."""},
        )
    print(f"[poster] Posted error comment to PR #{pr_number}")