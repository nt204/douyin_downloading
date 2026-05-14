import shutil
from datetime import datetime
from datetime import timedelta
from pathlib import Path

from backend.config import get_settings
from backend.models.job import utcnow


def ensure_job_dir(job_id: str) -> Path:
    settings = get_settings()
    job_dir = settings.temp_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir


def delete_job_dir(job_id: str) -> None:
    job_dir = get_settings().temp_dir / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)


def prune_old_jobs() -> None:
    settings = get_settings()
    cutoff = utcnow() - timedelta(hours=settings.max_file_age_hours)
    if not settings.temp_dir.exists():
        return
    for job_dir in settings.temp_dir.iterdir():
        if not job_dir.is_dir():
            continue
        modified = datetime.fromtimestamp(job_dir.stat().st_mtime, tz=cutoff.tzinfo)
        if modified < cutoff:
            shutil.rmtree(job_dir, ignore_errors=True)


def find_first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None
