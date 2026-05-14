from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl, field_validator


class JobStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    done = "done"
    error = "error"
    deleted = "deleted"


class JobStage(str, Enum):
    queued = "queued"
    downloading = "downloading"
    extracting = "extracting"
    transcribing = "transcribing"
    translating = "translating"
    rendering = "rendering"
    done = "done"
    error = "error"


STAGE_LABELS = {
    JobStage.queued: "Dang cho trong hang doi...",
    JobStage.downloading: "Dang tai video tu Douyin...",
    JobStage.extracting: "Dang trich xuat phu de tieng Trung...",
    JobStage.transcribing: "Gemini dang tao subtitle tu video...",
    JobStage.translating: "Gemini dang dich phu de sang tieng Viet...",
    JobStage.rendering: "Dang ghep phu de vao video...",
    JobStage.done: "Hoan thanh! Video san sang tai ve.",
    JobStage.error: "Co loi xay ra trong qua trinh xu ly.",
}


class SubtitleOptions(BaseModel):
    font_size: int = Field(default=24, ge=16, le=60)
    font_color: str = Field(default="white", min_length=3, max_length=20)
    position: str = Field(default="bottom", pattern="^(bottom|top)$")

    @field_validator("font_color")
    @classmethod
    def normalize_color(cls, value: str) -> str:
        return value.strip().lower()


class JobCreate(BaseModel):
    url: HttpUrl
    options: SubtitleOptions = Field(default_factory=SubtitleOptions)

    @field_validator("url")
    @classmethod
    def validate_douyin_url(cls, value: HttpUrl) -> HttpUrl:
        allowed_hosts = {"www.douyin.com", "v.douyin.com", "douyin.com"}
        if value.host not in allowed_hosts:
            raise ValueError("URL Douyin khong dung dinh dang")
        return value


class JobCreatedResponse(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    stage: JobStage
    stage_label: str
    created_at: datetime
    updated_at: datetime
    error: str | None = None
    download_url: str | None = None
    srt_url: str | None = None
    video_title: str | None = None
    duration_seconds: float | None = None
    subtitle_count: int | None = None


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
