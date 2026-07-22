"""每日 DeepSeek 初审任务。"""

import asyncio
import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.runtime_env import CurrentSeasonRuntime
from app.services.leaderboard_service import leaderboard_service
from app.services.preliminary_review_service import preliminary_review_service


logger = logging.getLogger(__name__)
_review_task: asyncio.Task[None] | None = None


def _parse_daily_time(value: str) -> time:
    """解析 HH:MM 格式，避免错误配置造成紧密循环。"""
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            "LLM_PRELIMINARY_REVIEW_DAILY_TIME 必须是 HH:MM 格式",
        ) from exc


def _get_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.LLM_PRELIMINARY_REVIEW_TIMEZONE)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            "LLM_PRELIMINARY_REVIEW_TIMEZONE 不是有效 IANA 时区",
        ) from exc


def _next_run_at(now: datetime, scheduled_time: time) -> datetime:
    """计算严格晚于当前时刻的下一次本地执行时间。"""
    scheduled_at = datetime.combine(now.date(), scheduled_time, tzinfo=now.tzinfo)
    if scheduled_at <= now:
        scheduled_at += timedelta(days=1)
    return scheduled_at


async def _review_once() -> None:
    season_id = CurrentSeasonRuntime.season_id
    if season_id is None:
        # 任务仅信任当前进程全局赛季 ID，不回扫数据库或过往赛季。
        logger.warning("preliminary review skipped: current season runtime is empty")
        return

    timezone = _get_timezone()
    local_now = datetime.now(timezone)
    # 数据库 DATETIME 保存本地时间；审核当天上传的凭证留到下一次任务处理。
    cutoff_at = datetime.combine(local_now.date(), time.min)
    async with async_session_factory() as session:
        summary = await preliminary_review_service.review_pending_current_season(
            session=session,
            season_id=season_id,
            cutoff_at=cutoff_at,
        )
        if summary.updated_count:
            # 初审通过后立即刷新快照，避免等到下一次独立排行榜任务才对用户可见。
            await leaderboard_service.refresh_current_season_snapshot(session=session)

    logger.info(
        "preliminary review finished: season_id=%s found=%s updated=%s failed=%s",
        season_id,
        summary.found_count,
        summary.updated_count,
        summary.failed_count,
    )


async def _review_once_safely() -> None:
    try:
        await _review_once()
    except Exception:
        logger.exception("daily preliminary review failed")


async def _review_loop() -> None:
    timezone = _get_timezone()
    scheduled_time = _parse_daily_time(settings.LLM_PRELIMINARY_REVIEW_DAILY_TIME)
    while True:
        now = datetime.now(timezone)
        next_run_at = _next_run_at(now=now, scheduled_time=scheduled_time)
        await asyncio.sleep((next_run_at - now).total_seconds())
        await _review_once_safely()


def start_preliminary_review_task() -> None:
    """按配置启动每日初审，不在应用启动时立即补跑。"""
    global _review_task
    if not settings.LLM_PRELIMINARY_REVIEW_ENABLED:
        return
    if _review_task is not None and not _review_task.done():
        return
    try:
        _get_timezone()
        _parse_daily_time(settings.LLM_PRELIMINARY_REVIEW_DAILY_TIME)
    except ValueError:
        logger.exception("daily preliminary review task is disabled by invalid config")
        return
    _review_task = asyncio.create_task(_review_loop())


async def stop_preliminary_review_task() -> None:
    """停止每日初审任务。"""
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
