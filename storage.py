import sqlite3, os
from dataclasses import dataclass
from typing import Optional

DB_PATH = os.getenv("DB_PATH") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "reviews.db"
)

# ── Schema ────────────────────────────────────────────────

def init_db():
    con = sqlite3.connect(DB_PATH)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS reviews (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            repo          TEXT    NOT NULL,
            pr_number     INTEGER NOT NULL,
            pr_title      TEXT,
            author        TEXT,
            head_sha      TEXT    NOT NULL,
            base_ref      TEXT,
            critical      INTEGER DEFAULT 0,
            warnings      INTEGER DEFAULT 0,
            suggestions   INTEGER DEFAULT 0,
            total_files   INTEGER DEFAULT 0,
            score         INTEGER DEFAULT 100,
            reviewed_at   TEXT    DEFAULT (datetime('now')),
            UNIQUE(repo, pr_number, head_sha)
        );

        CREATE TABLE IF NOT EXISTS review_comments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id   INTEGER NOT NULL REFERENCES reviews(id),
            repo        TEXT    NOT NULL,
            pr_number   INTEGER NOT NULL,
            filename    TEXT    NOT NULL,
            line        INTEGER,
            severity    TEXT    NOT NULL,
            body        TEXT    NOT NULL,
            created_at  TEXT    DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_reviews_repo
            ON reviews(repo);
        CREATE INDEX IF NOT EXISTS idx_reviews_author
            ON reviews(author);
        CREATE INDEX IF NOT EXISTS idx_comments_repo
            ON review_comments(repo);
        CREATE INDEX IF NOT EXISTS idx_comments_severity
            ON review_comments(severity);
    """)
    con.commit()
    con.close()
    print("[db] Schema initialized")

# ── Idempotency ───────────────────────────────────────────

def already_reviewed(repo: str, pr_number: int, head_sha: str) -> bool:
    con = sqlite3.connect(DB_PATH)
    row = con.execute(
        "SELECT 1 FROM reviews WHERE repo=? AND pr_number=? AND head_sha=?",
        (repo, pr_number, head_sha)
    ).fetchone()
    con.close()
    return row is not None

# ── Write ─────────────────────────────────────────────────

def calculate_score(critical: int, warnings: int, suggestions: int) -> int:
    """Score from 0-100. Critical issues heavily penalised."""
    score = 100 - (critical * 25) - (warnings * 10) - (suggestions * 2)
    return max(0, score)

def save_review(
    repo: str,
    pr_number: int,
    pr_title: str,
    author: str,
    head_sha: str,
    base_ref: str,
    total_files: int,
    critical: int,
    warnings: int,
    suggestions: int,
) -> int:
    """Saves a review and returns its id."""
    score = calculate_score(critical, warnings, suggestions)
    con = sqlite3.connect(DB_PATH)
    cur = con.execute(
        """INSERT OR IGNORE INTO reviews
           (repo, pr_number, pr_title, author, head_sha, base_ref,
            total_files, critical, warnings, suggestions, score)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (repo, pr_number, pr_title, author, head_sha, base_ref,
         total_files, critical, warnings, suggestions, score)
    )
    review_id = cur.lastrowid
    con.commit()
    con.close()
    return review_id

def save_comments(review_id: int, repo: str, pr_number: int, comments: list):
    """Saves all inline comments for a review."""
    if not comments:
        return
    con = sqlite3.connect(DB_PATH)
    con.executemany(
        """INSERT INTO review_comments
           (review_id, repo, pr_number, filename, line, severity, body)
           VALUES (?,?,?,?,?,?,?)""",
        [
            (review_id, repo, pr_number,
             c.path, c.line, c.severity, c.body)
            for c in comments
        ]
    )
    con.commit()
    con.close()

# ── Read (used by API) ────────────────────────────────────

def get_repos() -> list[str]:
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        "SELECT DISTINCT repo FROM reviews ORDER BY repo"
    ).fetchall()
    con.close()
    return [r[0] for r in rows]

def get_reviews(repo: str, limit: int = 50) -> list[dict]:
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        """SELECT id, pr_number, pr_title, author, head_sha,
                  critical, warnings, suggestions, total_files,
                  score, reviewed_at
           FROM reviews
           WHERE repo=?
           ORDER BY reviewed_at DESC
           LIMIT ?""",
        (repo, limit)
    ).fetchall()
    con.close()
    return [
        {
            "id": r[0], "pr_number": r[1], "pr_title": r[2],
            "author": r[3], "head_sha": r[4][:8],
            "critical": r[5], "warnings": r[6],
            "suggestions": r[7], "total_files": r[8],
            "score": r[9], "reviewed_at": r[10],
        }
        for r in rows
    ]

def get_metrics(repo: str) -> dict:
    con = sqlite3.connect(DB_PATH)

    totals = con.execute(
        """SELECT COUNT(*), AVG(score), SUM(critical),
                  SUM(warnings), SUM(suggestions)
           FROM reviews WHERE repo=?""",
        (repo,)
    ).fetchone()

    top_files = con.execute(
        """SELECT filename, COUNT(*) as cnt
           FROM review_comments
           WHERE repo=? AND severity='critical'
           GROUP BY filename
           ORDER BY cnt DESC
           LIMIT 5""",
        (repo,)
    ).fetchall()

    trend = con.execute(
        """SELECT DATE(reviewed_at) as day, AVG(score) as avg_score,
                  SUM(critical) as criticals
           FROM reviews WHERE repo=?
           GROUP BY day
           ORDER BY day DESC
           LIMIT 30""",
        (repo,)
    ).fetchall()

    authors = con.execute(
        """SELECT author, COUNT(*) as prs, AVG(score) as avg_score
           FROM reviews WHERE repo=?
           GROUP BY author
           ORDER BY prs DESC
           LIMIT 10""",
        (repo,)
    ).fetchall()

    con.close()
    return {
        "total_reviews": totals[0] or 0,
        "avg_score":     round(totals[1] or 0, 1),
        "total_critical": totals[2] or 0,
        "total_warnings": totals[3] or 0,
        "total_suggestions": totals[4] or 0,
        "top_files": [{"file": r[0], "critical_count": r[1]} for r in top_files],
        "trend": [{"day": r[0], "score": round(r[1], 1), "criticals": r[2]} for r in trend],
        "authors": [{"author": r[0], "prs": r[1], "avg_score": round(r[2], 1)} for r in authors],
    }