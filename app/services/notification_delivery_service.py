import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dingtalk import (
    DingTalkClient,
    DingTalkError,
    dingtalk_client,
)
from app.models.notification import Notification, NotificationStatus
from app.repositories.notification_repository import (
    NotificationRepository,
    notification_repository,
)


logger = logging.getLogger(__name__)
NOTIFICATION_BATCH_SIZE = 20
DINGTALK_MESSAGE_MAX_BYTES = 2048
DINGTALK_RESULT_QUERY_WINDOW_SECONDS = 24 * 60 * 60
MISSING_FIELD_VALUE = "未填写"
MARKDOWN_SPECIAL_PATTERN = re.compile(r"([\\`*_{}\[\]()#+\-.!|>])")


class NotificationMessageFormatError(ValueError):
    """通知标题或消息字段不符合持久化契约。"""


@dataclass(frozen=True)
class NotificationDeliverySummary:
    """单轮通知发送和状态同步结果。"""

    checked_count: int = 0
    delivered_count: int = 0
    sent_count: int = 0
    failed_count: int = 0
    deferred_count: int = 0


def _normalize_inline_text(value: str) -> str:
    """将数据库展示快照规范为单行，避免业务值改变 Markdown 结构。"""
    normalized = " ".join(value.split())
    return normalized or MISSING_FIELD_VALUE


def _escape_markdown(value: str) -> str:
    """转义 Markdown 和 HTML 边界字符，业务字段只作为纯文本展示。"""
    html_escaped = (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return MARKDOWN_SPECIAL_PATTERN.sub(r"\\\1", html_escaped)


def _message_payload_size(title: str, text: str) -> int:
    """按真实钉钉 msg JSON 计算 UTF-8 字节数，而不是按 Python 字符数估算。"""
    message = {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": text},
    }
    return len(
        json.dumps(
            message,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _truncate_markdown_text(title: str, text: str) -> str:
    """在保留标题和前序高优先级字段的前提下截断超长正文。"""
    if _message_payload_size(title, text) <= DINGTALK_MESSAGE_MAX_BYTES:
        return text

    suffix = "\n\n…"
    lower = 0
    upper = len(text)
    while lower < upper:
        midpoint = (lower + upper + 1) // 2
        candidate = text[:midpoint].rstrip("\\ \n") + suffix
        if _message_payload_size(title, candidate) <= DINGTALK_MESSAGE_MAX_BYTES:
            lower = midpoint
        else:
            upper = midpoint - 1
    return text[:lower].rstrip("\\ \n") + suffix


def build_notification_markdown(
    message_title: str,
    message_fields: list[dict[str, str]],
) -> tuple[str, str]:
    """把所有业务通知的有序键值快照转换为同一 Markdown 模板。"""
    if not isinstance(message_title, str) or not message_title.strip():
        raise NotificationMessageFormatError("通知标题不能为空")
    if not isinstance(message_fields, list):
        raise NotificationMessageFormatError("通知消息字段必须是数组")

    title = _normalize_inline_text(message_title)
    lines = [f"### {_escape_markdown(title)}"]
    for field in message_fields:
        if not isinstance(field, dict):
            raise NotificationMessageFormatError("通知消息字段必须是对象")
        key = field.get("key")
        value = field.get("value")
        if not isinstance(key, str) or not key.strip():
            raise NotificationMessageFormatError("通知消息字段名称不能为空")
        if not isinstance(value, str):
            raise NotificationMessageFormatError("通知消息字段值必须是字符串")
        normalized_key = _normalize_inline_text(key)
        normalized_value = _normalize_inline_text(value)
        lines.extend(
            (
                "",
                f"**{_escape_markdown(normalized_key)}：** "
                f"{_escape_markdown(normalized_value)}",
            )
        )

    text = _truncate_markdown_text(title, "\n".join(lines))
    if _message_payload_size(title, text) > DINGTALK_MESSAGE_MAX_BYTES:
        raise NotificationMessageFormatError("通知标题过长，无法生成钉钉消息")
    return title, text


class NotificationDeliveryService:
    """编排通知领取、钉钉发送、结果轮询和失败重试。"""

    def __init__(
        self,
        *,
        client: DingTalkClient = dingtalk_client,
        repository: NotificationRepository = notification_repository,
    ) -> None:
        self._client = client
        self._repository = repository

    async def process_once(
        self,
        session: AsyncSession,
        *,
        check_interval_seconds: int,
        now: datetime | None = None,
    ) -> NotificationDeliverySummary:
        """执行一轮状态查询和发送，所有网络调用均位于数据库事务之外。"""
        if check_interval_seconds <= 0:
            raise ValueError("钉钉通知检查间隔必须大于 0")
        current_time = now or datetime.now()

        status_summary = await self._synchronize_accepted(
            session=session,
            updated_at=current_time,
        )
        send_summary = await self._send_waiting(
            session=session,
            current_time=current_time,
            check_interval_seconds=check_interval_seconds,
        )
        return NotificationDeliverySummary(
            checked_count=status_summary.checked_count,
            delivered_count=status_summary.delivered_count,
            sent_count=send_summary.sent_count,
            failed_count=(
                status_summary.failed_count + send_summary.failed_count
            ),
            deferred_count=status_summary.deferred_count,
        )

    async def _synchronize_accepted(
        self,
        *,
        session: AsyncSession,
        updated_at: datetime,
    ) -> NotificationDeliverySummary:
        """只轮询 accepted；delivered 和 read 均作为终态永久跳过。"""
        notifications = await self._repository.list_accepted(
            session=session,
            limit=NOTIFICATION_BATCH_SIZE,
        )
        # SELECT 开启的隐式事务必须在访问外部服务前结束。
        await session.commit()

        delivered_count = 0
        failed_count = 0
        deferred_count = 0
        for notification in notifications:
            result = await self._resolve_accepted_notification(
                session=session,
                notification=notification,
                updated_at=updated_at,
            )
            if result == NotificationStatus.DELIVERED:
                delivered_count += 1
            elif result == NotificationStatus.FAILED:
                failed_count += 1
            else:
                deferred_count += 1
        return NotificationDeliverySummary(
            checked_count=len(notifications),
            delivered_count=delivered_count,
            failed_count=failed_count,
            deferred_count=deferred_count,
        )

    async def _resolve_accepted_notification(
        self,
        *,
        session: AsyncSession,
        notification: Notification,
        updated_at: datetime,
    ) -> NotificationStatus | None:
        """查询单条钉钉任务；查询暂时失败时保留 accepted，避免重复发送。"""
        if notification.id is None:
            return None
        if notification.task_id is None:
            await self._mark_failed(
                session=session,
                notification_id=notification.id,
                expected_status=NotificationStatus.ACCEPTED,
                updated_at=updated_at,
            )
            return NotificationStatus.FAILED

        try:
            progress = await self._client.get_work_notification_progress(
                notification.task_id
            )
            if not progress.is_complete:
                if self._accepted_result_expired(notification, updated_at):
                    await self._mark_failed(
                        session=session,
                        notification_id=notification.id,
                        expected_status=NotificationStatus.ACCEPTED,
                        updated_at=updated_at,
                    )
                    return NotificationStatus.FAILED
                return None
            result = await self._client.get_work_notification_result(
                notification.task_id
            )
        except DingTalkError as exc:
            logger.warning(
                "dingtalk notification status deferred: notification_id=%s "
                "type=%s http_status=%s error_code=%s",
                notification.id,
                type(exc).__name__,
                getattr(exc, "http_status", None),
                getattr(exc, "error_code", None),
            )
            # 官方结果查询窗口只有 24 小时，过期后只能重新发送以恢复可追踪状态。
            if self._accepted_result_expired(notification, updated_at):
                await self._mark_failed(
                    session=session,
                    notification_id=notification.id,
                    expected_status=NotificationStatus.ACCEPTED,
                    updated_at=updated_at,
                )
                return NotificationStatus.FAILED
            return None

        if notification.user_id in result.delivered_user_ids:
            updated = await self._repository.mark_delivered_if_accepted(
                session=session,
                notification_id=notification.id,
                updated_at=updated_at,
            )
            await session.commit()
            return NotificationStatus.DELIVERED if updated else None

        # 任务完成却没有目标用户的成功记录时按失败处理，交给下一轮重新发送。
        await self._mark_failed(
            session=session,
            notification_id=notification.id,
            expected_status=NotificationStatus.ACCEPTED,
            updated_at=updated_at,
        )
        return NotificationStatus.FAILED

    def _accepted_result_expired(
        self,
        notification: Notification,
        current_time: datetime,
    ) -> bool:
        """超过钉钉 24 小时查询窗口后重新发送，避免永久停留 accepted。"""
        return notification.notification_updated_at <= (
            current_time
            - timedelta(seconds=DINGTALK_RESULT_QUERY_WINDOW_SECONDS)
        )

    async def _send_waiting(
        self,
        *,
        session: AsyncSession,
        current_time: datetime,
        check_interval_seconds: int,
    ) -> NotificationDeliverySummary:
        """领取 pending、到期 failed 和超时 processing，并逐条提交钉钉。"""
        retry_before = current_time - timedelta(
            seconds=check_interval_seconds
        )
        processing_timeout_seconds = max(
            check_interval_seconds * 2,
            int(
                settings.DINGTALK_HTTP_TIMEOUT_SECONDS
                * (NOTIFICATION_BATCH_SIZE + 1)
            )
            + 5,
        )
        processing_before = current_time - timedelta(
            seconds=processing_timeout_seconds
        )
        notifications = await self._repository.claim_sendable(
            session=session,
            retry_before=retry_before,
            processing_before=processing_before,
            claimed_at=current_time,
            limit=NOTIFICATION_BATCH_SIZE,
        )
        # processing 先持久化，进程中断后可按更新时间安全回收。
        await session.commit()

        sent_count = 0
        failed_count = 0
        for notification in notifications:
            sent = await self._send_notification(
                session=session,
                notification=notification,
                updated_at=current_time,
            )
            if sent:
                sent_count += 1
            else:
                failed_count += 1
        return NotificationDeliverySummary(
            sent_count=sent_count,
            failed_count=failed_count,
        )

    async def _send_notification(
        self,
        *,
        session: AsyncSession,
        notification: Notification,
        updated_at: datetime,
    ) -> bool:
        """发送单条通用 Markdown 通知，失败记录等待下一检查周期重试。"""
        if notification.id is None:
            return False
        try:
            title, text = build_notification_markdown(
                message_title=notification.message_title,
                message_fields=notification.message_fields,
            )
            task_id = await self._client.send_markdown_work_notification(
                user_id=notification.user_id,
                title=title,
                text=text,
            )
        except (DingTalkError, NotificationMessageFormatError) as exc:
            await self._mark_failed(
                session=session,
                notification_id=notification.id,
                expected_status=NotificationStatus.PROCESSING,
                updated_at=updated_at,
            )
            logger.warning(
                "dingtalk notification send failed: notification_id=%s "
                "type=%s http_status=%s error_code=%s",
                notification.id,
                type(exc).__name__,
                getattr(exc, "http_status", None),
                getattr(exc, "error_code", None),
            )
            return False

        updated = await self._repository.mark_accepted_if_processing(
            session=session,
            notification_id=notification.id,
            task_id=task_id,
            updated_at=updated_at,
        )
        await session.commit()
        return updated

    async def _mark_failed(
        self,
        *,
        session: AsyncSession,
        notification_id: int,
        expected_status: NotificationStatus,
        updated_at: datetime,
    ) -> None:
        """失败状态独立提交，使后续轮次能够按更新时间控制重试节奏。"""
        await self._repository.mark_failed_if_current(
            session=session,
            notification_id=notification_id,
            expected_status=expected_status,
            updated_at=updated_at,
        )
        await session.commit()


notification_delivery_service = NotificationDeliveryService()
