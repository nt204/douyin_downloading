from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import get_settings
from backend.routers.health import router as health_router
from backend.routers.jobs import router as jobs_router


settings = get_settings()
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="Douyin Translator", version=settings.app_version)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(jobs_router)
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/")
def index():
    return FileResponse(frontend_dir / "index.html")
