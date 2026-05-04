import re, json, os
from dataclasses import dataclass
from anthropic import Anthropic
from github_client import FileChange

client = Anthropic()

MAX_PATCH_CHARS = 8_000
MAX_FILES       = 20

# ── Data model ────────────────────────────────────────────

@dataclass
class ReviewComment:
    path: str
    line: int
    body: str
    severity: str   # critical | warning | suggestion

# ── Context budget ────────────────────────────────────────

def prioritise_files(files: list[FileChange]) -> list[FileChange]:
    def score(f: FileChange) -> int:
        bonus = 10 if any(f.filename.endswith(e)
                    for e in (".py", ".ts", ".js", ".go", ".java")) else 0
        return f.additions + f.deletions + bonus

    ranked   = sorted(files, key=score, reverse=True)
    selected = ranked[:MAX_FILES]

    for f in selected:
        if len(f.patch) > MAX_PATCH_CHARS:
            f.patch = f.patch[:MAX_PATCH_CHARS] + "\n... (truncated)"

    return selected

def format_diff(files: list[FileChange]) -> str:
    sections = []
    for f in files:
        sections.append(
            f"### {f.filename} ({f.status})\n"
            f"+{f.additions} -{f.deletions} lines\n"
            f"```diff\n{f.patch}\n```"
        )
    return "\n\n".join(sections)

# ── Prompt ────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert code reviewer. 
You review pull request diffs and return structured JSON feedback.
You are precise, helpful, and focus on real issues — not style nitpicks.
Never invent line numbers. Only reference lines visible in the diff."""

def build_prompt(pr_title: str, pr_body: str, diff: str) -> str:
    return f"""Review this pull request and respond ONLY with a JSON object. No preamble, no markdown fences.

PR Title: {pr_title}
PR Description: {pr_body or "No description provided."}

Diff:
{diff}

Respond with exactly this shape:
{{
  "summary": "One paragraph overall assessment of the PR.",
  "comments": [
    {{
      "path": "filename.py",
      "line": 12,
      "severity": "critical",
      "body": "Specific actionable feedback referencing this exact line."
    }}
  ]
}}

Severity rules:
- critical  → bugs, security vulnerabilities, data loss risks
- warning   → performance issues, missing error handling, bad patterns  
- suggestion → readability, minor improvements, optional refactors

Only include comments on lines that appear in the diff above.
If no issues found, return an empty comments array with a positive summary."""

# ── AI call ───────────────────────────────────────────────

def parse_response(raw: str) -> tuple[str, list[ReviewComment]]:
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return raw, []

    summary  = data.get("summary", "Review complete.")
    comments = [
        ReviewComment(
            path=c["path"],
            line=int(c["line"]),
            body=c["body"],
            severity=c.get("severity", "suggestion"),
        )
        for c in data.get("comments", [])
        if c.get("path") and c.get("line") and c.get("body")
    ]
    return summary, comments

async def review_pr(
    pr_title: str,
    pr_body: str,
    files: list[FileChange],
) -> tuple[str, list[ReviewComment]]:
    selected  = prioritise_files(files)
    diff_text = format_diff(selected)
    prompt    = build_prompt(pr_title, pr_body, diff_text)

    print(f"[ai] Sending {len(selected)} files to Claude...")

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text
    print(f"[ai] Got response ({len(raw)} chars)")
    return parse_response(raw)