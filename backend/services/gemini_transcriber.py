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

    def transcribe_to_vietnamese(self, video_path: Path) -> pysrt.SubRipFile:
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
            "Xem video nay va tao subtitle tieng Viet tu nhien. "
            "Tra ve DUY NHAT JSON array. Moi phan tu co 3 key: start, end, text. "
            "start/end la so giay dang thap phan voi 3 chu so sau dau phay. "
            "text la cau subtitle tieng Viet. Khong tra ve markdown, khong giai thich."
        )
        response = self.model.generate_content([uploaded, prompt])
        raw = (response.text or "").strip().strip("`")
        logger.info("Gemini returned subtitle payload length=%s", len(raw))
        if raw.startswith("json"):
            raw = raw[4:].strip()
        try:
            items = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GeminiTranscriptionError("Gemini tra ve subtitle video sai dinh dang JSON.") from exc
        if not isinstance(items, list) or not items:
            raise GeminiTranscriptionError("Gemini khong tra ve segment subtitle hop le.")

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
        if len(subs) == 0:
            raise GeminiTranscriptionError("Gemini khong tao duoc subtitle tu video.")
        return subs
