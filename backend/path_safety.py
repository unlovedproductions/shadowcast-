"""Path containment for job-relative file serving under OUTPUT_BASE."""

from pathlib import Path

from fastapi import HTTPException

OUTPUT_BASE = Path(__file__).parent / "output"
OUTPUT_BASE.mkdir(exist_ok=True)

# Job ids that must never be served via /api/download or /api/files (creds live off-tree now;
# keep the name blocked so legacy output/credentials cannot be fetched as a "job").
_PROTECTED_OUTPUT_NAMES = frozenset({"credentials"})


def _safe_job_file(job_id: str, rel_path: str) -> Path:
    """Resolve a job-relative file under OUTPUT_BASE; reject traversal and protected names."""
    if (
        not job_id
        or job_id in _PROTECTED_OUTPUT_NAMES
        or job_id in {".", ".."}
        or "/" in job_id
        or "\\" in job_id
        or ".." in job_id
    ):
        raise HTTPException(status_code=404, detail="File not found")
    if not rel_path or Path(rel_path).is_absolute():
        raise HTTPException(status_code=404, detail="File not found")

    output_root = OUTPUT_BASE.resolve()
    job_root = (OUTPUT_BASE / job_id).resolve()
    if not job_root.is_relative_to(output_root) or job_root == output_root:
        raise HTTPException(status_code=404, detail="File not found")

    candidate = (job_root / rel_path).resolve()
    if not candidate.is_relative_to(job_root):
        raise HTTPException(status_code=404, detail="File not found")
    return candidate
