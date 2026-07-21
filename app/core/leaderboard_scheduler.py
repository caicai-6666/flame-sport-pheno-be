import asyncio
import logging

from app.core.config import settings
from app.core.database import async_session_factory
from app.services.leaderboard_service import leaderboard_service


logger = logging.getLogger(__name__)
_refresh_task: asyncio.Task[None] | None = None


async def _refresh_once() -> None:
    """执行一次排行榜快照刷新。"""
    async with async_session_factory() as session:
        await leaderboard_service.refresh_current_season_snapshot(session=session)


async def _refresh_once_safely() -> None:
    """安全执行排行榜刷新，失败时记录日志并保持后台循环存活。"""
    try:
        await _refresh_once()
    except Exception:
        logger.exception("leaderboard snapshot refresh failed")


async def _refresh_loop() -> None:
    """按环境变量配置的间隔刷新排行榜快照。"""
    if settings.LEADERBOARD_REFRESH_ON_STARTUP:
        await _refresh_once_safely()

    refresh_interval_seconds = max(
        settings.LEADERBOARD_REFRESH_INTERVAL_SECONDS,
        1,
    )
    while True:
        await asyncio.sleep(refresh_interval_seconds)
        await _refresh_once_safely()


def start_leaderboard_refresh_task() -> None:
    """启动排行榜快照刷新后台任务。"""
    global _refresh_task
    if not settings.LEADERBOARD_REFRESH_ENABLED:
        return
    if _refresh_task is None or _refresh_task.done():
        _refresh_task = asyncio.create_task(_refresh_loop())


async def stop_leaderboard_refresh_task() -> None:
    """停止排行榜快照刷新后台任务。"""
    global _refresh_task
    if _refresh_task is None:
        return

    _refresh_task.cancel()
    try:
        await _refresh_task
    except asyncio.CancelledError:
        pass
    finally:
        _refresh_task = None
