#!/usr/bin/env python3
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.utils.preflight import runtime_status  # noqa: E402


def main() -> int:
    status = runtime_status()
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0 if status["ready_for_douyin"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
