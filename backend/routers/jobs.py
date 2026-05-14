from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from backend.config import get_settings
from backend.models.job import JobCreate, JobCreatedResponse, JobStatus
from backend.tasks.pipeline import process_job
from backend.utils.file_manager import prune_old_jobs
from backend.utils.job_store import as_response, create_job, delete_job, get_job, update_job
from backend.utils.preflight import assert_runtime_ready


router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _count_active_jobs() -> int:
    settings = get_settings()
    count = 0
    for path in settings.temp_dir.glob("*/job.json"):
        payload = get_job(path.parent.name)
        if payload and payload.get("status") in {JobStatus.queued.value, JobStatus.processing.value}:
            count += 1
    return count


def _require_existing(job_id: str):
    job = as_response(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Khong tim thay job.")
    return job


@router.post("", response_model=JobCreatedResponse, status_code=status.HTTP_202_ACCEPTED)
def create_processing_job(payload: JobCreate) -> JobCreatedResponse:
    prune_old_jobs()
    try:
        assert_runtime_ready()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    settings = get_settings()
    if _count_active_jobs() >= settings.max_concurrent_jobs:
        raise HTTPException(status_code=429, detail="He thong dang ban, vui long thu lai sau.")

    job_id = uuid4().hex[:12]
    job = create_job(job_id)
    update_job(job_id, source_url=str(payload.url), options=payload.options.model_dump())
    process_job.delay(job_id, str(payload.url), payload.options.model_dump())
    return JobCreatedResponse(job_id=job_id, status=job["status"], created_at=job["created_at"])


@router.get("/{job_id}")
def get_processing_job(job_id: str):
    prune_old_jobs()
    return _require_existing(job_id)


@router.get("/{job_id}/download")
def download_processed_video(job_id: str):
    _require_existing(job_id)
    output_path = get_settings().temp_dir / job_id / "output.mp4"
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Video output chua san sang.")
    return FileResponse(output_path, media_type="video/mp4", filename=f"{job_id}.mp4")


@router.get("/{job_id}/srt")
def download_translated_srt(job_id: str):
    _require_existing(job_id)
    subtitle_path = get_settings().temp_dir / job_id / "subtitle.vi.srt"
    if not subtitle_path.exists():
        raise HTTPException(status_code=404, detail="Subtitle chua san sang.")
    return FileResponse(subtitle_path, media_type="application/x-subrip", filename=f"{job_id}.srt")


@router.delete("/{job_id}")
def delete_processing_job(job_id: str):
    if as_response(job_id) is None:
        raise HTTPException(status_code=404, detail="Khong tim thay job.")
    delete_job(job_id)
    return {"success": True}
