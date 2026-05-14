from fastapi import APIRouter

from backend.config import get_settings
from backend.utils.preflight import runtime_status


router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str | bool]:
    settings = get_settings()
    return {"ok": True, "version": settings.app_version}


@router.get("/health/runtime")
def health_runtime() -> dict[str, object]:
    return runtime_status()
