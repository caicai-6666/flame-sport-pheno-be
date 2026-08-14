from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT, TINYINT
from sqlmodel import Field, SQLModel


class SuggestionProcessingStage(StrEnum):
    """管理端处理用户建议时可使用的阶段。"""

    PENDING = "pending"
    REJECTED = "rejected"
    OPTIMIZED = "optimized"


class UserSuggestion(SQLModel, table=True):
    """用户提交的建议记录。"""

    __tablename__ = "user_suggestion"
    __table_args__ = (
        Index("idx_user_suggestion_user_created", "user_id", "created_at"),
        Index("idx_user_suggestion_status_created", "status", "created_at"),
        Index(
            "idx_user_suggestion_processing_stage_created",
            "processing_stage",
            "created_at",
        ),
        CheckConstraint(
            "processing_stage IN ('pending', 'rejected', 'optimized')",
            name="chk_user_suggestion_processing_stage",
        ),
        {
            "mysql_engine": "InnoDB",
            "mysql_default_charset": "utf8mb4",
            "mysql_comment": "用户建议表",
        },
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            BIGINT(unsigned=True),
            primary_key=True,
            autoincrement=True,
            comment="用户建议唯一标识",
        ),
    )
    user_id: str = Field(
        sa_column=Column(
            # 外键字符串列必须与已部署 user.id 的字符集和排序规则完全一致。
            String(64, collation="utf8mb4_0900_ai_ci"),
            ForeignKey("user.id", name="fk_user_suggestion_user"),
            nullable=False,
            comment="提交建议的用户ID，关联user表主键",
        )
    )
    content: str = Field(
        sa_column=Column(Text, nullable=False, comment="用户填写的建议内容")
    )
    status: int = Field(
        default=1,
        sa_column=Column(
            TINYINT(unsigned=True),
            nullable=False,
            server_default=text("1"),
            comment="记录状态：1可见，0隐藏",
        ),
    )
    processing_stage: str = Field(
        default=SuggestionProcessingStage.PENDING.value,
        sa_column=Column(
            String(32),
            nullable=False,
            server_default=text("'pending'"),
            comment="处理阶段：pending待处理，rejected拒绝，optimized已优化",
        ),
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(
            DateTime,
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
            comment="用户提交建议的时间",
        ),
    )
