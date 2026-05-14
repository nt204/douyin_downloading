import json
import socket
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import httpx

from backend.config import get_settings


class BrowserBridgeError(RuntimeError):
    pass


def _post_json(url: str, payload: dict) -> httpx.Response:
    return httpx.post(url, json=payload, timeout=120.0)


def _ipv4_fallback_url(url: str) -> str | None:
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return None
    try:
        infos = socket.getaddrinfo(hostname, parsed.port or 80, family=socket.AF_INET, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return None
    if not infos:
        return None
    ipv4 = infos[0][4][0]
    netloc = ipv4
    if parsed.port:
        netloc = f"{ipv4}:{parsed.port}"
    return urlunparse(parsed._replace(netloc=netloc))


def resolve_video_via_host_bridge(url: str, cookies_text: str, job_dir: Path | None = None) -> dict:
    settings = get_settings()
    if not settings.host_downloader_url:
        raise BrowserBridgeError("Host bridge chua duoc cau hinh.")

    request_payload = {"url": url, "cookies_text": cookies_text, "job_dir": str(job_dir) if job_dir else None}

    try:
        bridge_url = f"{settings.host_downloader_url.rstrip('/')}/resolve"
        response = _post_json(bridge_url, request_payload)
    except httpx.HTTPError as exc:
        fallback_url = _ipv4_fallback_url(bridge_url)
        if fallback_url and fallback_url != bridge_url:
            try:
                response = _post_json(fallback_url, request_payload)
            except httpx.HTTPError:
                raise BrowserBridgeError(f"Khong goi duoc host browser bridge: {exc}") from exc
        else:
            raise BrowserBridgeError(f"Khong goi duoc host browser bridge: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise BrowserBridgeError(f"Host browser bridge tra ve JSON khong hop le (HTTP {response.status_code}).") from exc

    if response.is_error:
        detail = payload.get("error") if isinstance(payload, dict) else None
        message = detail or f"Host browser bridge loi HTTP {response.status_code}."
        raise BrowserBridgeError(message)

    if not payload.get("ok"):
        raise BrowserBridgeError(payload.get("error") or "Host browser bridge khong resolve duoc video.")
    return payload
