from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.auth_cache import (
    start_auth_cache_cleanup_task,
    stop_auth_cache_cleanup_task,
)
from app.core.config import settings
from app.core.storage import ensure_asset_directories
from app.routers import auth, health, image, project, season


@asynccontextmanager
async def lifespan(application: FastAPI):
    """应用生命周期：启动时初始化目录和后台任务，关闭时清理后台任务。"""
    ensure_asset_directories()
    start_auth_cache_cleanup_task()
    try:
        yield
    finally:
        await stop_auth_cache_cleanup_task()


def create_app() -> FastAPI:
    application = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(auth.router)
    application.include_router(health.router)
    application.include_router(image.router)
    application.include_router(project.router)
    application.include_router(season.router)
    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="192.168.11.202", port=8000, reload=True)
