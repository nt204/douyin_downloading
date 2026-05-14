import shutil
import os
from celery import Celery
from celery.exceptions import SoftTimeLimitExceeded

from backend.config import get_settings
from backend.models.job import JobStage, JobStatus, SubtitleOptions
from backend.services.downloader import download_video
from backend.services.gemini_transcriber import GeminiVideoTranscriber
from backend.services.renderer import render_video
from backend.services.subtitle_extractor import SubtitleExtractionError, extract_subtitles
from backend.services.translator import GeminiTranslator
from backend.utils.file_manager import ensure_job_dir
from backend.utils.job_store import complete_job, fail_job, update_job
from backend.utils.srt_parser import save_srt


settings = get_settings()
celery_app = Celery("douyin_translator", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_time_limit=settings.job_timeout_minutes * 60,
    task_soft_time_limit=max(settings.job_timeout_minutes * 60 - 30, 30),
)


def _set_stage(job_id: str, stage: JobStage, progress: int, status: JobStatus = JobStatus.processing) -> None:
    from backend.models.job import STAGE_LABELS

    update_job(
        job_id,
        status=status.value,
        stage=stage.value,
        progress=progress,
        stage_label=STAGE_LABELS[stage],
    )


@celery_app.task(name="backend.tasks.pipeline.process_job")
def process_job(job_id: str, url: str, options: dict) -> None:
    try:
        job_dir = ensure_job_dir(job_id)
        subtitle_options = SubtitleOptions.model_validate(options)

        _set_stage(job_id, JobStage.downloading, 10)
        download = download_video(url, job_dir)

        _set_stage(job_id, JobStage.extracting, 30)
        vi_srt_path = job_dir / "subtitle.vi.srt"
        subtitle_count = 0
        margin_v_pct = 25
        try:
            _, source_subs = extract_subtitles(download)
            _set_stage(job_id, JobStage.translating, 55)
            translator = GeminiTranslator()
            translated = translator.translate(source_subs)
            save_srt(translated, vi_srt_path)
            subtitle_count = len(translated)
            
            # Smart detection for source subs
            try:
                margin_v_pct = translator.detect_position(download.video_path)
            except Exception:
                margin_v_pct = 25
        except SubtitleExtractionError:
            _set_stage(job_id, JobStage.transcribing, 55)
            transcribed, margin_v_pct = GeminiVideoTranscriber().transcribe_to_vietnamese(download.video_path)
            save_srt(transcribed, vi_srt_path)
            subtitle_count = len(transcribed)

        _set_stage(job_id, JobStage.rendering, 80)
        output_path = job_dir / "output.mp4"
        render_video(download.video_path, vi_srt_path, output_path, subtitle_options, margin_v_pct=margin_v_pct)

        complete_job(
            job_id,
            video_title=download.title,
            duration_seconds=download.duration_seconds,
            subtitle_count=subtitle_count,
        )

        # Copy results to output directory
        try:
            output_dir = settings.output_dir / job_id
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy final video
            if output_path.exists():
                shutil.copy2(output_path, output_dir / f"{download.title or job_id}.mp4")
                
            # Copy SRTs
            zh_srt = job_dir / "subtitle.zh.srt"
            if zh_srt.exists():
                shutil.copy2(zh_srt, output_dir / f"{download.title or job_id}.zh.srt")
            if vi_srt_path.exists():
                shutil.copy2(vi_srt_path, output_dir / f"{download.title or job_id}.vi.srt")
        except Exception as e:
            # Don't fail the job if just copying fails, but log it
            print(f"Error copying results to output_dir: {e}")

    except SoftTimeLimitExceeded as exc:
        fail_job(job_id, "Xu ly qua lau, vui long thu video ngan hon.")
        raise exc
    except Exception as exc:
        fail_job(job_id, str(exc))
        raise
