"""定时筛查待审凭证的 DeepSeek 初审任务。"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.core.database import async_session_factory
from app.repositories.season_repository import season_repository
from app.services.leaderboard_service import leaderboard_service
from app.services.preliminary_review_service import (
    scheduled_preliminary_review_service,
)


logger = logging.getLogger(__name__)
_review_task: asyncio.Task[None] | None = None
SHANGHAI_TIMEZONE = ZoneInfo("Asia/Shanghai")
STOP_BEFORE_SEASON_END = timedelta(minutes=5)


@dataclass
class ReviewBatchGate:
    """进程内等待计数；只统计非空扫描，不跨轮累加重复凭证数量。"""

    season_id: int | None = None
    underfilled_scans: int = 0

    def reset(self) -> None:
        self.season_id = None
        self.underfilled_scans = 0

    def should_review(self, season_id: int, count: int, minimum: int) -> bool:
        if season_id != self.season_id:
            self.reset()
            self.season_id = season_id
        if count == 0:
            self.underfilled_scans = 0
            return False
        if count >= minimum:
            self.underfilled_scans = 0
            return True
        self.underfilled_scans += 1
        if self.underfilled_scans >= 3:
            self.underfilled_scans = 0
            return True
        return False


_batch_gate = ReviewBatchGate()


def _validate_scheduler_config() -> None:
    """校验间隔与最小等待时间，避免错误配置导致紧密调用模型。"""
    if settings.LLM_PRELIMINARY_REVIEW_INTERVAL_SECONDS <= 0:
        raise ValueError("LLM_PRELIMINARY_REVIEW_INTERVAL_SECONDS 必须大于 0")
    for name in ("LLM_PRELIMINARY_REVIEW_MIN_BATCH_SIZE", "LLM_PRELIMINARY_REVIEW_CONCURRENCY"):
        if getattr(settings, name) <= 0:
            raise ValueError(f"{name} 必须大于 0")
    if settings.LLM_PRELIMINARY_REVIEW_MIN_AGE_SECONDS < 0:
        raise ValueError("LLM_PRELIMINARY_REVIEW_MIN_AGE_SECONDS 不能小于 0")


def _build_cutoff_at(now: datetime) -> datetime:
    """计算本轮可审核的最晚上传时间。"""
    return now - timedelta(seconds=settings.LLM_PRELIMINARY_REVIEW_MIN_AGE_SECONDS)


def _build_review_stop_at(season_end_date) -> datetime:
    """按上海时区口径在赛季结束次日零点前 5 分钟停止定时初审。"""
    return datetime.combine(
        season_end_date + timedelta(days=1),
        time.min,
    ) - STOP_BEFORE_SEASON_END


async def _review_once() -> None:
    # 数据库 DATETIME 保存本地时间。最小等待时间留给用户重传，避免刚上传就被模型审核。
    now = datetime.now(SHANGHAI_TIMEZONE).replace(tzinfo=None)
    cutoff_at = _build_cutoff_at(now)
    async with async_session_factory() as session:
        season = await season_repository.get_current(session=session)
        if season is None or season.id is None:
            _batch_gate.reset()
            logger.info("preliminary review skipped: no active season")
            return
        if now >= _build_review_stop_at(season.end_date):
            _batch_gate.reset()
            logger.info(
                "preliminary review skipped: active season is within final 5 minutes "
                "season_id=%s",
                season.id,
            )
            return

        season_id = season.id
        groups = await scheduled_preliminary_review_service.list_pending_groups(
            session=session, season_id=season_id, cutoff_at=cutoff_at,
        )
        count = sum(map(len, groups))
        if not _batch_gate.should_review(
            season_id, count, settings.LLM_PRELIMINARY_REVIEW_MIN_BATCH_SIZE,
        ):
            logger.info(
                "preliminary review waiting: season_id=%s found=%s minimum=%s underfilled_scans=%s",
                season_id, count, settings.LLM_PRELIMINARY_REVIEW_MIN_BATCH_SIZE,
                _batch_gate.underfilled_scans,
            )
            return
        summary = await scheduled_preliminary_review_service.review_pending_active_season(
            groups=groups, season_id=season_id, cutoff_at=cutoff_at,
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
        _batch_gate.reset()
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
    _batch_gate.reset()
    _review_task = asyncio.create_task(_review_loop())


async def stop_preliminary_review_task() -> None:
    """停止定时初审任务。"""
    global _review_task
    _batch_gate.reset()
    if _review_task is None:
        return
    _review_task.cancel()
    try:
        await _review_task
    except asyncio.CancelledError:
        pass
    finally:
        _review_task = None
