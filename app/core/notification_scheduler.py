"""定时发送钉钉 Markdown 工作通知并同步投递状态。"""

import asyncio
import logging

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.dingtalk import dingtalk_client
from app.services.notification_delivery_service import (
    notification_delivery_service,
)


logger = logging.getLogger(__name__)
_notification_task: asyncio.Task[None] | None = None


async def _deliver_once() -> None:
    """使用独立会话执行一轮发送和结果查询。"""
    async with async_session_factory() as session:
        summary = await notification_delivery_service.process_once(
            session=session,
            check_interval_seconds=(
                settings.DINGTALK_NOTIFICATION_CHECK_INTERVAL_SECONDS
            ),
        )
    logger.info(
        "dingtalk notification cycle finished: checked=%s delivered=%s "
        "sent=%s failed=%s deferred=%s",
        summary.checked_count,
        summary.delivered_count,
        summary.sent_count,
        summary.failed_count,
        summary.deferred_count,
    )


async def _deliver_once_safely() -> None:
    """隔离单轮异常，数据库或钉钉故障不会终止后台循环。"""
    try:
        await _deliver_once()
    except Exception:
        logger.exception("scheduled dingtalk notification delivery failed")


async def _notification_loop() -> None:
    """启动后立即补发积压通知，之后按配置间隔持续检查。"""
    interval_seconds = settings.DINGTALK_NOTIFICATION_CHECK_INTERVAL_SECONDS
    while True:
        await _deliver_once_safely()
        await asyncio.sleep(interval_seconds)


def start_notification_delivery_task() -> None:
    """配置完整且间隔有效时启动工作通知定时任务。"""
    global _notification_task
    if settings.DINGTALK_NOTIFICATION_CHECK_INTERVAL_SECONDS <= 0:
        logger.error(
            "dingtalk notification task disabled: check interval must be positive"
        )
        return
    if not dingtalk_client.is_notification_configured():
        logger.info(
            "dingtalk notification task disabled: credentials or agent id missing"
        )
        return
    if _notification_task is None or _notification_task.done():
        _notification_task = asyncio.create_task(_notification_loop())


async def stop_notification_delivery_task() -> None:
    """停止通知循环；HTTP 连接池仍由钉钉客户端生命周期统一关闭。"""
    global _notification_task
    if _notification_task is None:
        return
    _notification_task.cancel()
    try:
        await _notification_task
    except asyncio.CancelledError:
        pass
    finally:
        _notification_task = None
