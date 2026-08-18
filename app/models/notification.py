from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, JSON, String, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlmodel import Field, SQLModel


class NotificationStatus(StrEnum):
    """通知投递状态。"""

    PENDING = "pending"
    PROCESSING = "processing"
    ACCEPTED = "accepted"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class Notification(SQLModel, table=True):
    """用户通知表模型。"""

    __tablename__ = "notification"
    __table_args__ = (
        Index(
            "idx_notification_consume",
            "notification_status",
            "notification_updated_at",
            "id",
        ),
        Index("idx_notification_user_id", "user_id"),
        CheckConstraint(
            "notification_status IN ("
            "'pending', 'processing', 'accepted', 'delivered', 'read', 'failed'"
            ")",
            name="chk_notification_delivery_status",
        ),
        CheckConstraint(
            "JSON_TYPE(message_fields) = 'ARRAY'",
            name="chk_notification_message_fields",
        ),
        {
            "mysql_engine": "InnoDB",
            "mysql_default_charset": "utf8mb4",
            "mysql_comment": "用户通知表",
        },
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            BIGINT(unsigned=True),
            primary_key=True,
            autoincrement=True,
            comment="通知记录ID",
        ),
    )
    task_id: int | None = Field(
        default=None,
        sa_column=Column(
            BIGINT(unsigned=True),
            nullable=True,
            comment="钉钉异步工作通知任务ID",
        ),
    )
    user_id: str = Field(
        sa_column=Column(
            String(64),
            ForeignKey("user.id", name="fk_notification_user"),
            nullable=False,
            comment="接收通知的用户ID",
        )
    )
    message_title: str = Field(
        sa_column=Column(
            String(100),
            nullable=False,
            comment="Markdown工作通知标题",
        )
    )
    message_fields: list[dict[str, str]] = Field(
        sa_column=Column(
            JSON,
            nullable=False,
            comment="按展示顺序保存的消息键值列表",
        )
    )
    notification_status: str = Field(
        default=NotificationStatus.PENDING.value,
        sa_column=Column(
            String(32),
            nullable=False,
            server_default=text("'pending'"),
            comment=(
                "通知状态：pending待发送，processing发送中，accepted已受理，"
                "delivered已送达，read已读，failed失败"
            ),
        ),
    )
    notification_updated_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(
            DATETIME(fsp=6),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP(6)"),
            comment="通知状态最后更新时间",
        ),
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(
            DATETIME(fsp=6),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP(6)"),
            comment="通知创建时间",
        ),
    )
