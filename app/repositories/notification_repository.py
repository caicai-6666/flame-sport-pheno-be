from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationStatus


class NotificationRepository:
    async def create_pending(
        self,
        session: AsyncSession,
        user_id: str,
        message_title: str,
        message_fields: list[dict[str, str]],
    ) -> Notification:
        """在当前业务事务中创建待发送通知，交由后续投递任务处理。"""
        notification = Notification(
            user_id=user_id,
            message_title=message_title,
            message_fields=message_fields,
            notification_status=NotificationStatus.PENDING.value,
        )
        session.add(notification)
        await session.flush()
        return notification

    async def list_accepted(
        self,
        session: AsyncSession,
        limit: int,
    ) -> list[Notification]:
        """按受理时间读取仍需向钉钉查询最终结果的通知。"""
        if limit <= 0:
            return []
        result = await session.execute(
            select(Notification)
            .where(
                Notification.notification_status
                == NotificationStatus.ACCEPTED.value
            )
            .order_by(
                Notification.notification_updated_at.asc(),
                Notification.id.asc(),
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def claim_sendable(
        self,
        session: AsyncSession,
        *,
        retry_before: datetime,
        processing_before: datetime,
        claimed_at: datetime,
        limit: int,
    ) -> list[Notification]:
        """优先领取新通知，再领取到期失败项和进程中断遗留项。"""
        if limit <= 0:
            return []

        claimed: list[Notification] = []
        claim_rules = (
            (NotificationStatus.PENDING.value, None),
            (NotificationStatus.FAILED.value, retry_before),
            (NotificationStatus.PROCESSING.value, processing_before),
        )
        for status, updated_before in claim_rules:
            remaining = limit - len(claimed)
            if remaining <= 0:
                break
            claimed.extend(
                await self._claim_by_status(
                    session=session,
                    status=status,
                    updated_before=updated_before,
                    claimed_at=claimed_at,
                    limit=remaining,
                )
            )
        await session.flush()
        return claimed

    async def mark_accepted_if_processing(
        self,
        session: AsyncSession,
        *,
        notification_id: int,
        task_id: int,
        updated_at: datetime,
    ) -> bool:
        """仅允许当前发送者把 processing 通知登记为钉钉已受理。"""
        result = await session.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.notification_status
                == NotificationStatus.PROCESSING.value,
            )
            .values(
                task_id=task_id,
                notification_status=NotificationStatus.ACCEPTED.value,
                notification_updated_at=updated_at,
            )
        )
        return bool(result.rowcount)

    async def mark_delivered_if_accepted(
        self,
        session: AsyncSession,
        *,
        notification_id: int,
        updated_at: datetime,
    ) -> bool:
        """已读和未读均归并为 delivered，之后不再轮询该通知。"""
        result = await session.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.notification_status
                == NotificationStatus.ACCEPTED.value,
            )
            .values(
                notification_status=NotificationStatus.DELIVERED.value,
                notification_updated_at=updated_at,
            )
        )
        return bool(result.rowcount)

    async def mark_failed_if_current(
        self,
        session: AsyncSession,
        *,
        notification_id: int,
        expected_status: NotificationStatus,
        updated_at: datetime,
    ) -> bool:
        """只覆盖调用方仍持有的状态，避免旧结果回写并发新任务。"""
        result = await session.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.notification_status == expected_status.value,
            )
            .values(
                notification_status=NotificationStatus.FAILED.value,
                notification_updated_at=updated_at,
            )
        )
        return bool(result.rowcount)

    async def _claim_by_status(
        self,
        session: AsyncSession,
        *,
        status: str,
        updated_before: datetime | None,
        claimed_at: datetime,
        limit: int,
    ) -> list[Notification]:
        """使用跳过锁定行的方式领取一类任务，兼容未来多实例消费。"""
        statement = select(Notification).where(
            Notification.notification_status == status
        )
        if updated_before is not None:
            statement = statement.where(
                Notification.notification_updated_at <= updated_before
            )
        result = await session.execute(
            statement.order_by(
                Notification.notification_updated_at.asc(),
                Notification.id.asc(),
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        notifications = list(result.scalars().all())
        for notification in notifications:
            # 重试会产生新的钉钉任务，旧 task_id 不能继续代表当前发送尝试。
            notification.task_id = None
            notification.notification_status = NotificationStatus.PROCESSING.value
            notification.notification_updated_at = claimed_at
        return notifications


notification_repository = NotificationRepository()
