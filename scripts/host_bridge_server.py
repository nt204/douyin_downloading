#!/usr/bin/env python3
import json
import shutil
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import urllib.request

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException


CHROME_BINARY = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def _download_video_file(url: str, target_path: Path) -> int:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0 Safari/537.36"
        ),
        "Referer": "https://www.douyin.com/",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as response, target_path.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            handle.write(chunk)
    return target_path.stat().st_size


def _cookies_from_text(cookies_text: str) -> list[dict]:
    cookies = []
    for line in cookies_text.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, _, path, secure, expiry, name, value = parts[:7]
        if not name:
            continue
        cookie = {
            "name": name,
            "value": value,
            "domain": domain,
            "path": path or "/",
            "secure": secure.upper() == "TRUE",
        }
        if expiry.isdigit() and int(expiry) > 0:
            cookie["expiry"] = int(expiry)
        cookies.append(cookie)
    return cookies


def resolve_video(url: str, cookies_text: str, job_dir: str | None = None) -> dict:
    user_dir = tempfile.mkdtemp(prefix="douyin-bridge-")
    opts = Options()
    opts.binary_location = CHROME_BINARY
    opts.page_load_strategy = "eager"
    opts.add_argument(f"--user-data-dir={user_dir}")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_argument("--autoplay-policy=no-user-gesture-required")
    opts.add_argument("--window-size=1440,1200")
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(20)
    try:
        print(f"[bridge] start resolve url={url}", file=sys.stderr, flush=True)
        try:
            driver.get("https://www.douyin.com")
        except TimeoutException:
            print("[bridge] initial douyin homepage load timed out; continuing", file=sys.stderr, flush=True)
        for cookie in _cookies_from_text(cookies_text):
            try:
                driver.add_cookie(cookie)
            except Exception:
                continue
        try:
            driver.get(url)
        except TimeoutException:
            print(f"[bridge] target page load timed out for {url}; continuing with DOM poll", file=sys.stderr, flush=True)
        data = None
        for attempt in range(6):
            time.sleep(4)
            data = driver.execute_script(
                """
                const video = document.querySelector('video');
                const src = video ? (video.currentSrc || video.src || null) : null;
                const duration = video ? (video.duration || null) : null;
                return {
                  title: document.title,
                  video_src: src,
                  duration_seconds: duration,
                  body_text: document.body ? document.body.innerText.slice(0, 500) : '',
                };
                """
            )
            src = data.get("video_src") or ""
            duration = float(data.get("duration_seconds") or 0)
            if (
                src
                and "uuu_265.mp4" not in src
                and "douyinstatic.com/obj/douyin-pc-web" not in src
                and duration > 5
            ):
                print(
                    f"[bridge] got real video src on attempt={attempt + 1} duration={duration}",
                    file=sys.stderr,
                    flush=True,
                )
                break
            if attempt in {1, 3}:
                print(f"[bridge] refreshing page attempt={attempt + 1}", file=sys.stderr, flush=True)
                driver.refresh()
        if not data or not data.get("video_src"):
            raise RuntimeError("Chrome da mo trang nhung khong lay duoc video src.")
        if "uuu_265.mp4" in data["video_src"] or "douyinstatic.com/obj/douyin-pc-web" in data["video_src"]:
            raise RuntimeError("Chrome chi lay duoc video placeholder, chua vao duoc luong video that.")
        result = {"ok": True, **data}
        if job_dir:
            target_dir = Path(job_dir)
            target_dir.mkdir(parents=True, exist_ok=True)
            video_path = target_dir / "video.mp4"
            print(f"[bridge] downloading media to {video_path}", file=sys.stderr, flush=True)
            size = _download_video_file(data["video_src"], video_path)
            print(f"[bridge] downloaded size={size}", file=sys.stderr, flush=True)
            result["video_path"] = str(video_path)
            result["video_size"] = size
            (target_dir / "info.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
    finally:
        print("[bridge] cleanup webdriver", file=sys.stderr, flush=True)
        driver.quit()
        shutil.rmtree(user_dir, ignore_errors=True)


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._json(200, {"ok": True})
            return
        self._json(404, {"ok": False, "error": "Not found"})

    def do_POST(self) -> None:
        if self.path != "/resolve":
            self._json(404, {"ok": False, "error": "Not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        try:
            data = resolve_video(payload["url"], payload.get("cookies_text", ""), payload.get("job_dir"))
            self._json(200, data)
        except Exception as exc:
            self._json(500, {"ok": False, "error": str(exc)})


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 8765), Handler)
    print("Host bridge listening on 0.0.0.0:8765", flush=True)
    server.serve_forever()
