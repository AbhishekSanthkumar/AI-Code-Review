from fastapi import APIRouter, HTTPException, Query
from storage import get_repos, get_reviews, get_metrics

router = APIRouter(prefix="/api")

@router.get("/repos")
def list_repos():
    """List all repos that have been reviewed."""
    repos = get_repos()
    return {"repos": repos}

@router.get("/reviews")
def list_reviews(
    repo: str = Query(..., description="Repo name e.g. user/repo"),
    limit: int = Query(50, ge=1, le=200),
):
    """Return review history for a repo."""
    reviews = get_reviews(repo, limit)
    return {"repo": repo, "reviews": reviews}

@router.get("/metrics")
def repo_metrics(
    repo: str = Query(..., description="Repo name e.g. user/repo"),
):
    """Return aggregated metrics for a repo."""
    metrics = get_metrics(repo)
    return {"repo": repo, **metrics}

@router.get("/health")
def health():
    return {"status": "ok"}