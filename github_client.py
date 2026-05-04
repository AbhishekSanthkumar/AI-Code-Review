import httpx, jwt, time, os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

APP_ID           = os.getenv("GITHUB_APP_ID")
PRIVATE_KEY_PATH = os.getenv("GITHUB_PRIVATE_KEY_PATH")
API_BASE         = "https://api.github.com"
API_HEADERS      = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

SKIP_EXTENSIONS = {
    ".lock", ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".ico", ".pdf", ".woff", ".woff2", ".ttf",
    ".min.js", ".min.css", ".map",
}
SKIP_FILES = {"package-lock.json", "yarn.lock", "poetry.lock"}

# ── Data model ────────────────────────────────────────────

@dataclass
class FileChange:
    filename: str
    status: str
    patch: str
    additions: int
    deletions: int

# ── Auth ──────────────────────────────────────────────────

def _load_private_key() -> str:
    # production — key stored as environment variable
    key_from_env = os.getenv("GITHUB_PRIVATE_KEY")
    if key_from_env:
        key = key_from_env.replace("\\n", "\n")
        print(f"[auth] Key loaded from env — {len(key)} chars")
        return key

    # local development — key loaded from .pem file
    if PRIVATE_KEY_PATH:
        with open(PRIVATE_KEY_PATH, "r") as f:
            key = f.read()
        print(f"[auth] Key loaded from file — {len(key)} chars")
        return key

    raise ValueError("No private key found. Set GITHUB_PRIVATE_KEY or GITHUB_PRIVATE_KEY_PATH.")

def _generate_jwt() -> str:
    private_key = _load_private_key()
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + 540,
        "iss": APP_ID,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")

_token_cache: dict[str, tuple[str, float]] = {}

async def get_installation_token(installation_id: str) -> str:
    cached = _token_cache.get(installation_id)
    if cached and time.time() < cached[1] - 60:
        return cached[0]

    jwt_token = _generate_jwt()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{API_BASE}/app/installations/{installation_id}/access_tokens",
            headers={**API_HEADERS, "Authorization": f"Bearer {jwt_token}"},
        )
        resp.raise_for_status()
        data = resp.json()

    token = data["token"]
    _token_cache[installation_id] = (token, time.time() + 3600)
    return token

# ── Diff fetcher ──────────────────────────────────────────

def _should_skip(filename: str) -> bool:
    if filename in SKIP_FILES:
        return True
    return any(filename.endswith(ext) for ext in SKIP_EXTENSIONS)

async def fetch_pr_files(
    repo_name: str,
    pr_number: int,
    installation_id: str,
) -> list[FileChange]:
    token   = await get_installation_token(installation_id)
    headers = {**API_HEADERS, "Authorization": f"Bearer {token}"}
    url     = f"{API_BASE}/repos/{repo_name}/pulls/{pr_number}/files"
    files   = []

    async with httpx.AsyncClient() as client:
        page = 1
        while True:
            resp = await client.get(
                url, headers=headers,
                params={"per_page": 100, "page": page}
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break

            for f in batch:
                if _should_skip(f["filename"]):
                    continue
                if f["status"] == "removed":
                    continue
                patch = f.get("patch", "")
                if not patch:
                    continue

                files.append(FileChange(
                    filename=f["filename"],
                    status=f["status"],
                    patch=patch,
                    additions=f["additions"],
                    deletions=f["deletions"],
                ))
            page += 1

    return files