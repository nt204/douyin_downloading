import json
import logging
import time
from pathlib import Path

import google.generativeai as genai
import pysrt

from backend.config import get_settings

logger = logging.getLogger(__name__)


class GeminiTranscriptionError(RuntimeError):
    pass


class GeminiVideoTranscriber:
    def __init__(self) -> None:
        settings = get_settings()
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)

    def transcribe_to_vietnamese(self, video_path: Path) -> tuple[pysrt.SubRipFile, int]:
        logger.info("Gemini transcriber uploading video: %s", video_path)
        uploaded = genai.upload_file(path=str(video_path))
        while uploaded.state.name == "PROCESSING":
            logger.info("Gemini file still processing: %s", uploaded.name)
            time.sleep(5)
            uploaded = genai.get_file(uploaded.name)
        if uploaded.state.name != "ACTIVE":
            raise GeminiTranscriptionError(f"Gemini khong xu ly duoc video: {uploaded.state.name}")

        logger.info("Gemini file active, generating subtitle JSON: %s", uploaded.name)
        prompt = (
            "Xem video nay va thuc hien 2 viec:\n"
            "1. Tao subtitle tieng Viet tu nhien (dich tu am thanh va phu de Trung neu co).\n"
            "2. Xac dinh vi tri phu de tieng Trung (khoang cach tu mep duoi video len phu de, tinh theo phan tram chieu cao video, vi du: 15).\n"
            "Tra ve DUY NHAT JSON object co 2 key: 'subtitles' (array) va 'margin_v_pct' (so nguyen 0-100).\n"
            "Moi phan tu trong 'subtitles' co 3 key: start, end, text.\n"
            "Khong tra ve markdown, khong giai thich."
        )
        response = self.model.generate_content([uploaded, prompt])
        raw = (response.text or "").strip().strip("`")
        if raw.startswith("json"):
            raw = raw[4:].strip()
        try:
            data = json.loads(raw)
            items = data.get("subtitles", [])
            margin_v_pct = int(data.get("margin_v_pct", 25))
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.error("Gemini raw response: %s", raw)
            raise GeminiTranscriptionError("Gemini tra ve ket qua sai dinh dang JSON.") from exc

        subs = pysrt.SubRipFile()
        for index, item in enumerate(items, start=1):
            start = float(item["start"])
            end = float(item["end"])
            text = str(item["text"]).strip()
            if not text or end <= start:
                continue
            subs.append(
                pysrt.SubRipItem(
                    index=index,
                    start=pysrt.SubRipTime.from_ordinal(int(start * 1000)),
                    end=pysrt.SubRipTime.from_ordinal(int(end * 1000)),
                    text=text,
                )
            )
        return subs, margin_v_pct
