import html
import re
from pathlib import Path

import pysrt


HTML_TAG_RE = re.compile(r"<[^>]+>")


def load_srt(path: Path, fallback_encodings: tuple[str, ...] = ("utf-8", "utf-8-sig", "gbk", "gb2312")) -> pysrt.SubRipFile:
    for encoding in fallback_encodings:
        try:
            return pysrt.open(str(path), encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("srt", b"", 0, 1, f"Khong doc duoc file subtitle: {path}")


def clean_text(text: str) -> str:
    cleaned = html.unescape(text)
    cleaned = HTML_TAG_RE.sub("", cleaned)
    cleaned = cleaned.replace("\\N", "\n")
    return cleaned.strip()


def normalize_subtitles(subs: pysrt.SubRipFile, max_chars: int = 40) -> pysrt.SubRipFile:
    normalized = pysrt.SubRipFile()
    for item in subs:
        item.text = clean_text(item.text)
        if not item.text:
            continue
        if len(item.text) > max_chars and "\n" not in item.text:
            midpoint = len(item.text) // 2
            item.text = item.text[:midpoint].strip() + "\n" + item.text[midpoint:].strip()
        if normalized and item.duration.ordinal < 500:
            normalized[-1].text = f"{normalized[-1].text}\n{item.text}".strip()
            normalized[-1].end = item.end
            continue
        normalized.append(item)
    return normalized


def save_srt(subs: pysrt.SubRipFile, path: Path) -> None:
    subs.clean_indexes()
    subs.save(str(path), encoding="utf-8")
