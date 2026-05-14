import json
from urllib.parse import parse_qs, urlparse
from dataclasses import dataclass
from pathlib import Path

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from backend.config import get_settings
from backend.services.browser_bridge import BrowserBridgeError, resolve_video_via_host_bridge
from backend.utils.preflight import resolve_cookie_path


class DownloaderError(RuntimeError):
    pass


@dataclass
class DownloadResult:
    job_dir: Path
    video_path: Path
    info_path: Path
    title: str
    duration_seconds: float
    subtitle_candidates: list[Path]


def normalize_douyin_url(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    modal_id = query.get("modal_id", [None])[0]
    if modal_id and modal_id.isdigit():
        return f"https://www.douyin.com/video/{modal_id}"
    return url


def _collect_subtitle_candidates(job_dir: Path) -> list[Path]:
    exts = ("*.srt", "*.ass", "*.vtt", "*.ttml")
    candidates: list[Path] = []
    for pattern in exts:
        candidates.extend(sorted(job_dir.glob(pattern)))
    return candidates


def _download_via_host_bridge(url: str, job_dir: Path, cookies_text: str) -> DownloadResult:
    video_path = job_dir / "video.mp4"
    info_path = job_dir / "info.json"
    try:
        payload = resolve_video_via_host_bridge(url, cookies_text, job_dir)
    except BrowserBridgeError:
        if video_path.exists() and video_path.stat().st_size > 0 and info_path.exists():
            payload = json.loads(info_path.read_text(encoding="utf-8"))
        else:
            raise
    if not video_path.exists() or video_path.stat().st_size == 0:
        raise BrowserBridgeError("Host bridge khong tao duoc file video tren thu muc dung chung.")
    info_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return DownloadResult(
        job_dir=job_dir,
        video_path=video_path,
        info_path=info_path,
        title=payload.get("title") or "Douyin Video",
        duration_seconds=float(payload.get("duration_seconds") or 0),
        subtitle_candidates=[],
    )


def download_video(url: str, job_dir: Path) -> DownloadResult:
    settings = get_settings()
    info_path = job_dir / "info.json"
    normalized_url = normalize_douyin_url(url)
    resolved_cookie_path = resolve_cookie_path()
    cookiefile = str(resolved_cookie_path) if resolved_cookie_path else None
    cookies_text = resolved_cookie_path.read_text(encoding="utf-8", errors="ignore") if resolved_cookie_path else ""
    bridge_error: str | None = None

    if cookies_text and settings.host_downloader_url:
        try:
            return _download_via_host_bridge(normalized_url, job_dir, cookies_text)
        except BrowserBridgeError as exc:
            bridge_error = str(exc)

    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": str(job_dir / "video.%(ext)s"),
        "merge_output_format": "mp4",
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["zh-Hans", "zh", "zh-TW"],
        "subtitlesformat": "srt/ass/vtt/best",
        "noplaylist": True,
        "restrictfilenames": True,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.douyin.com/",
        },
        "proxy": settings.ytdlp_proxy or None,
        "cookiefile": cookiefile,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "extractor_retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
        "geo_bypass": True,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(normalized_url, download=True)
            info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    except DownloadError as exc:
        error_text = str(exc)
        if "Fresh cookies" in error_text:
            if cookies_text and settings.host_downloader_url:
                try:
                    return _download_via_host_bridge(normalized_url, job_dir, cookies_text)
                except BrowserBridgeError as bridge_exc:
                    bridge_error = str(bridge_exc)
            message = "Douyin yeu cau cookies moi hoac session cookie chua hop le cho trang video nay."
            if bridge_error:
                message += f" Host bridge: {bridge_error}."
            message += f" yt-dlp: {error_text}"
            raise DownloaderError(message) from exc
        if "Unsupported URL" in error_text:
            raise DownloaderError(
                "URL Douyin nay khong duoc ho tro truc tiep. He thong da thu resolve sang dang /video/, "
                "nhung van khong tai duoc."
            ) from exc
        if cookiefile is None:
            raise DownloaderError(
                "Douyin da chan tai video. Hay export cookies.txt vao thu muc runtime/ "
                "va dat YTDLP_COOKIES_FILE=/app/runtime/cookies.txt."
            ) from exc
        raise DownloaderError(
            "Video khong the tai. Kiem tra lai cookies.txt, URL co con hoat dong, "
            f"hoac video dang private/bi xoa. yt-dlp: {error_text}"
        ) from exc

    video_candidates = sorted(job_dir.glob("video.*"))
    video_path = next((path for path in video_candidates if path.suffix.lower() == ".mp4"), None)
    if video_path is None:
        video_path = next((path for path in video_candidates if path.name != "video.info.json"), None)
    if video_path is None:
        raise DownloaderError("Khong tim thay file video sau khi tai xong.")

    size_mb = video_path.stat().st_size / (1024 * 1024)
    if size_mb > settings.max_video_size_mb:
        raise DownloaderError(f"Video qua lon, gioi han {settings.max_video_size_mb}MB.")

    subtitle_candidates = _collect_subtitle_candidates(job_dir)
    return DownloadResult(
        job_dir=job_dir,
        video_path=video_path,
        info_path=info_path,
        title=info.get("title") or "Douyin Video",
        duration_seconds=float(info.get("duration") or 0),
        subtitle_candidates=subtitle_candidates,
    )
