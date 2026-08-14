"""定时筛查待审凭证的 DeepSeek 初审任务。"""

import asyncio
import logging
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.database import async_session_factory
from app.repositories.season_repository import season_repository
from app.services.leaderboard_service import leaderboard_service
from app.services.preliminary_review_service import preliminary_review_service


logger = logging.getLogger(__name__)
_review_task: asyncio.Task[None] | None = None


def _validate_scheduler_config() -> None:
    """校验间隔与最小等待时间，避免错误配置导致紧密调用模型。"""
    if settings.LLM_PRELIMINARY_REVIEW_INTERVAL_SECONDS <= 0:
        raise ValueError("LLM_PRELIMINARY_REVIEW_INTERVAL_SECONDS 必须大于 0")
    if settings.LLM_PRELIMINARY_REVIEW_MIN_AGE_SECONDS < 0:
        raise ValueError("LLM_PRELIMINARY_REVIEW_MIN_AGE_SECONDS 不能小于 0")


def _build_cutoff_at(now: datetime) -> datetime:
    """计算本轮可审核的最晚上传时间。"""
    return now - timedelta(seconds=settings.LLM_PRELIMINARY_REVIEW_MIN_AGE_SECONDS)


async def _review_once() -> None:
    # 数据库 DATETIME 保存本地时间。最小等待时间留给用户重传，避免刚上传就被模型审核。
    cutoff_at = _build_cutoff_at(datetime.now())
    async with async_session_factory() as session:
        season = await season_repository.get_current(session=session)
        if season is None or season.id is None:
            logger.info("preliminary review skipped: no active season")
            return

        summary = await preliminary_review_service.review_pending_current_season(
            session=session,
            season_id=season.id,
            cutoff_at=cutoff_at,
        )
        if summary.updated_count:
            # 初审通过后立即刷新快照，避免等到下一次独立排行榜任务才对用户可见。
            await leaderboard_service.refresh_current_season_snapshot(session=session)

    logger.info(
        "preliminary review finished: season_id=%s found=%s updated=%s failed=%s",
        season.id,
        summary.found_count,
        summary.updated_count,
        summary.failed_count,
    )


async def _review_once_safely() -> None:
    try:
        await _review_once()
    except Exception:
        logger.exception("scheduled preliminary review failed")


async def _review_loop() -> None:
    interval_seconds = settings.LLM_PRELIMINARY_REVIEW_INTERVAL_SECONDS
    while True:
        await asyncio.sleep(interval_seconds)
        await _review_once_safely()


def start_preliminary_review_task() -> None:
    """按配置启动定时初审，不在应用启动时立即补跑。"""
    global _review_task
    if not settings.LLM_PRELIMINARY_REVIEW_ENABLED:
        return
    if _review_task is not None and not _review_task.done():
        return
    try:
        _validate_scheduler_config()
    except ValueError:
        logger.exception("scheduled preliminary review task is disabled by invalid config")
        return
    _review_task = asyncio.create_task(_review_loop())


async def stop_preliminary_review_task() -> None:
    """停止定时初审任务。"""
    global _review_task
    if _review_task is None:
        return
    _review_task.cancel()
    try:
        await _review_task
    except asyncio.CancelledError:
        pass
    finally:
        _review_task = None
