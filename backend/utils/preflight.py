from pathlib import Path
import shutil
from urllib.parse import urlparse

import httpx

from backend.config import get_settings, has_real_gemini_key


def resolve_cookie_path() -> Path | None:
    settings = get_settings()
    candidates: list[Path] = []
    if settings.ytdlp_cookies_file:
        candidates.append(Path(settings.ytdlp_cookies_file))
    candidates.extend([Path("/app/runtime/cookies.txt"), Path("runtime/cookies.txt").resolve()])
    for path in candidates:
        try:
            if path.exists() and path.stat().st_size > 0:
                return path
        except OSError:
            continue
    return None


def host_bridge_status() -> dict[str, object]:
    settings = get_settings()
    url = settings.host_downloader_url
    if not url:
        return {"configured": False, "reachable": False, "url": None, "detail": "Host bridge chua duoc cau hinh."}

    health_url = f"{url.rstrip('/')}/health"
    try:
        response = httpx.get(health_url, timeout=3.0)
        payload = response.json()
        if response.is_success and payload.get("ok") is True:
            return {"configured": True, "reachable": True, "url": url, "detail": "ok"}
        return {
            "configured": True,
            "reachable": False,
            "url": url,
            "detail": f"Host bridge tra ve HTTP {response.status_code}.",
        }
    except Exception as exc:
        parsed = urlparse(url)
        host_hint = ""
        if parsed.hostname == "host.docker.internal":
            host_hint = " Neu dang chay Docker tren Linux, can them extra_hosts hoac doi HOST_DOWNLOADER_URL."
        return {"configured": True, "reachable": False, "url": url, "detail": f"{exc}.{host_hint}"}


def runtime_status() -> dict[str, object]:
    settings = get_settings()
    cookie_path = resolve_cookie_path()
    cookies_exists = cookie_path is not None
    ffmpeg_ok = shutil.which("ffmpeg") is not None
    bridge = host_bridge_status()
    return {
        "gemini_key_configured": has_real_gemini_key(settings),
        "cookies_configured": cookies_exists,
        "cookies_path": str(cookie_path) if cookie_path else None,
        "ffmpeg_available": ffmpeg_ok,
        "host_bridge": bridge,
        "temp_dir": str(settings.temp_dir),
        "ready_for_douyin": has_real_gemini_key(settings) and cookies_exists and ffmpeg_ok and bridge["reachable"],
    }


def assert_runtime_ready() -> None:
    status = runtime_status()
    if not status["gemini_key_configured"]:
        raise RuntimeError("GEMINI_API_KEY chua duoc cau hinh key that trong .env.")
    if not status["cookies_configured"]:
        raise RuntimeError(
            "Chua co cookies Douyin. Hay dat file runtime/cookies.txt va cau hinh "
            "YTDLP_COOKIES_FILE=/app/runtime/cookies.txt."
        )
    bridge = status["host_bridge"]
    if not bridge["reachable"]:
        raise RuntimeError(
            "Host bridge chua san sang. "
            f"URL: {bridge['url']}. Chi tiet: {bridge['detail']}"
        )
    if not status["ffmpeg_available"]:
        raise RuntimeError("ffmpeg khong san sang trong runtime.")
