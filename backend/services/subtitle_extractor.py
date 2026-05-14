import subprocess
from pathlib import Path

import pysrt

from backend.services.downloader import DownloadResult
from backend.utils.srt_parser import load_srt, normalize_subtitles, save_srt


class SubtitleExtractionError(RuntimeError):
    pass


def _convert_to_srt(source: Path, target: Path) -> Path:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        str(target),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SubtitleExtractionError(f"Khong the convert subtitle {source.name} sang SRT.")
    return target


def _extract_embedded_subtitle(video_path: Path, target: Path) -> Path | None:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-map",
        "0:s:0",
        str(target),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return target if target.exists() else None


def extract_subtitles(download: DownloadResult) -> tuple[Path, pysrt.SubRipFile]:
    job_dir = download.job_dir
    candidates = list(download.subtitle_candidates)

    if not candidates:
        embedded = _extract_embedded_subtitle(download.video_path, job_dir / "embedded.srt")
        if embedded:
            candidates.append(embedded)

    if not candidates:
        raise SubtitleExtractionError("Video nay khong co phu de tieng Trung de xu ly.")

    preferred = sorted(candidates, key=lambda path: (path.suffix.lower() != ".srt", path.name))
    source = preferred[0]
    normalized_path = job_dir / "subtitle.zh.srt"

    if source.suffix.lower() == ".srt":
        subs = load_srt(source)
    else:
        converted = _convert_to_srt(source, normalized_path)
        subs = load_srt(converted)

    normalized = normalize_subtitles(subs)
    save_srt(normalized, normalized_path)

    if len(normalized) == 0:
        raise SubtitleExtractionError("Khong doc duoc noi dung subtitle tu video.")

    return normalized_path, normalized
