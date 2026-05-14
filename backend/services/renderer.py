import subprocess
from pathlib import Path

from backend.config import get_settings
from backend.models.job import SubtitleOptions


class RenderError(RuntimeError):
    pass


COLOR_MAP = {
    "white": "&H00FFFFFF",
    "yellow": "&H0000FFFF",
    "cyan": "&H00FFFF00",
    "green": "&H0000FF00",
    "red": "&H000000FF",
}


def _escape_subtitle_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace(",", "\\,")


def render_video(video_path: Path, subtitle_path: Path, output_path: Path, options: SubtitleOptions) -> Path:
    settings = get_settings()
    alignment = "8" if options.position == "top" else "2"
    subtitle_filter = (
        f"subtitles={_escape_subtitle_path(subtitle_path)}:"
        "charenc=UTF-8:"
        f"force_style='FontName=Liberation Sans,FontSize={options.font_size},"
        "PrimaryColour=&H000000,BackColour=&HFFFFFF,BorderStyle=3,Outline=0,Shadow=0,"
        f"Alignment={alignment},MarginV=50'"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        subtitle_filter,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        str(settings.video_crf),
        "-threads",
        str(settings.ffmpeg_threads),
        "-c:a",
        "copy",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RenderError("Loi khi ghep video, vui long thu lai.")
    return output_path
