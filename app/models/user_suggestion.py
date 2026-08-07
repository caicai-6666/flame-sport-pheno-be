from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.mysql import BIGINT, TINYINT
from sqlmodel import Field, SQLModel


class UserSuggestion(SQLModel, table=True):
    """用户提交的建议记录。"""

    __tablename__ = "user_suggestion"
    __table_args__ = (
        Index("idx_user_suggestion_user_created", "user_id", "created_at"),
        Index("idx_user_suggestion_visible_created", "is_visible", "created_at"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True),
    )
    user_id: str = Field(
        sa_column=Column(
            # 外键字符串列必须与已部署 user.id 的字符集和排序规则完全一致。
            String(64, collation="utf8mb4_0900_ai_ci"),
            ForeignKey("user.id", name="fk_user_suggestion_user"),
            nullable=False,
        )
    )
    content: str = Field(sa_column=Column(Text, nullable=False))
    is_visible: int = Field(
        default=1,
        sa_column=Column(
            TINYINT(unsigned=True),
            nullable=False,
            server_default=text("1"),
        ),
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(
            DateTime,
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )
