import time
from dataclasses import dataclass

import google.generativeai as genai
import pysrt

from backend.config import get_settings


class TranslationError(RuntimeError):
    pass


PROMPT_RULES = """Ban la dich gia chuyen nghiep Trung-Viet cho video ngan.
Quy tac bat buoc:
1. Dich tu nhien nhu nguoi Viet that su noi, khong dich tung chu.
2. Giu nguyen format: moi dong tuong ung 1 index, phan cach bang '|||'.
3. Khong them giai thich, ghi chu, markdown hoac ky tu la.
4. Tieng long thi doi sang cach noi tu nhien cua nguoi Viet.
5. Do dai ban dich khong vuot qua 1.5x do dai goc.
6. Neu gap ten rieng, giu hop ly theo ngu canh.
"""


@dataclass
class TranslationBatch:
    items: list[pysrt.SubRipItem]


class GeminiTranslator:
    def __init__(self) -> None:
        settings = get_settings()
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)
        self.batch_size = settings.gemini_batch_size

    def translate(self, subtitles: pysrt.SubRipFile) -> pysrt.SubRipFile:
        translated = pysrt.SubRipFile()
        items = list(subtitles)
        for offset in range(0, len(items), self.batch_size):
            batch = TranslationBatch(items=items[offset : offset + self.batch_size])
            translated.extend(self._translate_batch(batch))
        translated.clean_indexes()
        return translated

    def _translate_batch(self, batch: TranslationBatch) -> list[pysrt.SubRipItem]:
        retries = [1, 2, 4]
        last_error: Exception | None = None
        for delay in retries:
            try:
                mapping = self._call_model(batch.items)
                return [
                    pysrt.SubRipItem(
                        index=item.index,
                        start=item.start,
                        end=item.end,
                        text=mapping[item.index],
                    )
                    for item in batch.items
                ]
            except Exception as exc:
                last_error = exc
                time.sleep(delay)
        raise TranslationError(f"Dich Gemini that bai sau nhieu lan thu lai: {last_error}") from last_error

    def _call_model(self, items: list[pysrt.SubRipItem]) -> dict[int, str]:
        lines = [f"{item.index}|||{item.text.replace(chr(10), ' / ')}|||" for item in items]
        prompt = PROMPT_RULES + "\n\n" + "\n".join(lines)
        response = self.model.generate_content(prompt)
        text = (response.text or "").strip().strip("`")
        mapping = self._parse_response(text, items)
        if len(mapping) != len(items):
            raise TranslationError("Gemini tra ve sai so dong subtitle.")
        return mapping

    @staticmethod
    def _parse_response(text: str, items: list[pysrt.SubRipItem]) -> dict[int, str]:
        mapping: dict[int, str] = {}
        expected_indexes = {item.index for item in items}
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split("|||")
            if len(parts) < 2:
                continue
            try:
                index = int(parts[0].strip())
            except ValueError as exc:
                raise TranslationError("Gemini tra ve index khong hop le.") from exc
            content = parts[1].strip()
            if not content:
                raise TranslationError("Gemini tra ve noi dung dich rong.")
            mapping[index] = content.replace(" / ", "\n")
        missing = expected_indexes - set(mapping)
        if missing:
            raise TranslationError(f"Gemini thieu subtitle trong batch: {sorted(missing)}")
        return mapping
