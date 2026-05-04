import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reviews.db")

def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS reviewed_commits (
            repo        TEXT NOT NULL,
            pr_number   INTEGER NOT NULL,
            head_sha    TEXT NOT NULL,
            reviewed_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (repo, pr_number, head_sha)
        )
    """)
    con.commit()
    con.close()

def already_reviewed(repo: str, pr_number: int, head_sha: str) -> bool:
    con = sqlite3.connect(DB_PATH)
    row = con.execute(
        "SELECT 1 FROM reviewed_commits WHERE repo=? AND pr_number=? AND head_sha=?",
        (repo, pr_number, head_sha)
    ).fetchone()
    con.close()
    return row is not None

def mark_reviewed(repo: str, pr_number: int, head_sha: str):
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT OR IGNORE INTO reviewed_commits (repo, pr_number, head_sha) VALUES (?,?,?)",
        (repo, pr_number, head_sha)
    )
    con.commit()
    con.close()