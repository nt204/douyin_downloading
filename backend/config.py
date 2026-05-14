from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gemini_api_key: str = Field(..., alias="GEMINI_API_KEY")
    gemini_model: str = Field("models/gemini-2.5-flash", alias="GEMINI_MODEL")
    gemini_batch_size: int = Field(50, alias="GEMINI_BATCH_SIZE")
    temp_dir: Path = Field(Path("/tmp/jobs"), alias="TEMP_DIR")
    output_dir: Path = Field(Path("./runtime/output"), alias="OUTPUT_DIR")
    max_file_age_hours: int = Field(2, alias="MAX_FILE_AGE_HOURS")
    max_video_size_mb: int = Field(500, alias="MAX_VIDEO_SIZE_MB")
    redis_url: str = Field("redis://redis:6379/0", alias="REDIS_URL")
    celery_concurrency: int = Field(2, alias="CELERY_CONCURRENCY")
    ytdlp_proxy: str | None = Field(None, alias="YTDLP_PROXY")
    ytdlp_cookies_file: str | None = Field(None, alias="YTDLP_COOKIES_FILE")
    ffmpeg_threads: int = Field(4, alias="FFMPEG_THREADS")
    video_crf: int = Field(18, alias="VIDEO_CRF")
    max_concurrent_jobs: int = Field(5, alias="MAX_CONCURRENT_JOBS")
    job_timeout_minutes: int = Field(15, alias="JOB_TIMEOUT_MINUTES")
    app_version: str = Field("1.0.0", alias="APP_VERSION")
    api_base_url: str = Field("http://localhost:8000", alias="API_BASE_URL")
    host_downloader_url: str | None = Field("http://host.docker.internal:8765", alias="HOST_DOWNLOADER_URL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    return settings


def has_real_gemini_key(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    key = settings.gemini_api_key.strip()
    return bool(key) and key != "your_gemini_api_key"
