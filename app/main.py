from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.auth_cache import (
    start_auth_cache_cleanup_task,
    stop_auth_cache_cleanup_task,
)
from app.core.config import settings
from app.core.dingtalk import (
    start_dingtalk_access_token_refresh_task,
    stop_dingtalk_access_token_refresh_task,
)
from app.core.database import init_db
from app.core.leaderboard_scheduler import (
    start_leaderboard_refresh_task,
    stop_leaderboard_refresh_task,
)
from app.core.notification_scheduler import (
    start_notification_delivery_task,
    stop_notification_delivery_task,
)
from app.core.preliminary_review_scheduler import (
    start_preliminary_review_task,
    stop_preliminary_review_task,
)
from app.core.storage import ensure_asset_directories
from app.routers import (
    admin,
    auth,
    health,
    image,
    leaderboard,
    project,
    proof,
    season,
    shop,
    supplement,
    suggestion,
    user,
)

API_PREFIX = "/flame/api"


@asynccontextmanager
async def lifespan(application: FastAPI):
    """应用生命周期：启动时初始化目录和后台任务，关闭时清理后台任务。"""
    # Compose 的全新 MySQL 卷没有预建表，先完成建表再启动会访问业务表的后台任务。
    await init_db()
    ensure_asset_directories()
    start_auth_cache_cleanup_task()
    # 开发模式不会调用钉钉，避免本地联调产生无意义的 token 刷新请求。
    if settings.APP_MODE == "production":
        start_dingtalk_access_token_refresh_task()
        start_notification_delivery_task()
    start_leaderboard_refresh_task()
    start_preliminary_review_task()
    try:
        yield
    finally:
        await stop_preliminary_review_task()
        await stop_leaderboard_refresh_task()
        if settings.APP_MODE == "production":
            await stop_notification_delivery_task()
            await stop_dingtalk_access_token_refresh_task()
        await stop_auth_cache_cleanup_task()


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        lifespan=lifespan,
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=f"{API_PREFIX}/redoc",
        openapi_url=f"{API_PREFIX}/openapi.json",
        swagger_ui_oauth2_redirect_url=f"{API_PREFIX}/docs/oauth2-redirect",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(admin.router, prefix=API_PREFIX)
    application.include_router(auth.router, prefix=API_PREFIX)
    application.include_router(health.router, prefix=API_PREFIX)
    application.include_router(image.router, prefix=API_PREFIX)
    application.include_router(leaderboard.router, prefix=API_PREFIX)
    application.include_router(project.router, prefix=API_PREFIX)
    application.include_router(proof.router, prefix=API_PREFIX)
    application.include_router(season.router, prefix=API_PREFIX)
    application.include_router(shop.router, prefix=API_PREFIX)
    application.include_router(supplement.router, prefix=API_PREFIX)
    application.include_router(suggestion.router, prefix=API_PREFIX)
    application.include_router(user.router, prefix=API_PREFIX)
    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=21000, reload=True)
