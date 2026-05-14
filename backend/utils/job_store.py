import json
from pathlib import Path
from typing import Any

from backend.models.job import JobResponse, JobStage, JobStatus, STAGE_LABELS, utcnow
from backend.utils.file_manager import delete_job_dir, ensure_job_dir


def _job_file(job_id: str) -> Path:
    return ensure_job_dir(job_id) / "job.json"


def _existing_job_file(job_id: str) -> Path:
    from backend.config import get_settings

    return get_settings().temp_dir / job_id / "job.json"


def create_job(job_id: str) -> dict[str, Any]:
    now = utcnow()
    job = {
        "job_id": job_id,
        "status": JobStatus.queued.value,
        "progress": 0,
        "stage": JobStage.queued.value,
        "stage_label": STAGE_LABELS[JobStage.queued],
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "error": None,
        "download_url": None,
        "srt_url": None,
        "video_title": None,
        "duration_seconds": None,
        "subtitle_count": None,
    }
    _job_file(job_id).write_text(json.dumps(job, ensure_ascii=True, indent=2), encoding="utf-8")
    return job


def get_job(job_id: str) -> dict[str, Any] | None:
    path = _existing_job_file(job_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_job(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    payload["updated_at"] = utcnow().isoformat()
    _job_file(job_id).write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return payload


def update_job(job_id: str, **kwargs: Any) -> dict[str, Any]:
    payload = get_job(job_id)
    if payload is None:
        payload = create_job(job_id)
    payload.update(kwargs)
    return save_job(job_id, payload)


def complete_job(
    job_id: str,
    *,
    video_title: str,
    duration_seconds: float,
    subtitle_count: int,
) -> dict[str, Any]:
    return update_job(
        job_id,
        status=JobStatus.done.value,
        progress=100,
        stage=JobStage.done.value,
        stage_label=STAGE_LABELS[JobStage.done],
        error=None,
        download_url=f"/api/jobs/{job_id}/download",
        srt_url=f"/api/jobs/{job_id}/srt",
        video_title=video_title,
        duration_seconds=duration_seconds,
        subtitle_count=subtitle_count,
    )


def fail_job(job_id: str, message: str) -> dict[str, Any]:
    return update_job(
        job_id,
        status=JobStatus.error.value,
        stage=JobStage.error.value,
        stage_label=message,
        error=message,
    )


def delete_job(job_id: str) -> None:
    delete_job_dir(job_id)


def as_response(job_id: str) -> JobResponse | None:
    payload = get_job(job_id)
    if payload is None:
        return None
    return JobResponse.model_validate(payload)
