import json
from pathlib import Path
import time
import urllib.request

import httpx

from backend.config import get_settings


class BrowserBridgeError(RuntimeError):
    pass


def resolve_video_via_host_bridge(url: str, cookies_text: str, job_dir: Path | None = None) -> dict:
    settings = get_settings()
    if not settings.host_downloader_url:
        raise BrowserBridgeError("Host bridge chua duoc cau hinh.")

    try:
        response = httpx.post(
            f"{settings.host_downloader_url.rstrip('/')}/resolve",
            json={"url": url, "cookies_text": cookies_text, "job_dir": str(job_dir) if job_dir else None},
            timeout=120.0,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise BrowserBridgeError("Khong goi duoc host browser bridge.") from exc

    if not payload.get("ok"):
        raise BrowserBridgeError(payload.get("error") or "Host browser bridge khong resolve duoc video.")
    return payload
