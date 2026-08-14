from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, TINYINT
from sqlmodel import Field, SQLModel


class SeasonUser(SQLModel, table=True):
    """赛季用户表模型。"""

    __tablename__ = "season_user"
    __table_args__ = (
        UniqueConstraint("season_id", "user_id", name="uk_season_user"),
        Index("idx_season_user_season_id", "season_id"),
        Index("idx_season_user_user_id", "user_id"),
        Index("idx_season_user_level_id", "level_id"),
        Index("idx_season_user_participated_at", "participated_at"),
        Index("idx_season_user_status", "status"),
        {
            "mysql_engine": "InnoDB",
            "mysql_default_charset": "utf8mb4",
            "mysql_comment": "赛季用户表",
        },
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            BIGINT(unsigned=True),
            primary_key=True,
            autoincrement=True,
            comment="赛季用户记录ID",
        ),
    )
    season_id: int = Field(
        sa_column=Column(
            BIGINT(unsigned=True),
            ForeignKey("season.id", name="fk_season_user_season"),
            nullable=False,
            comment="赛季ID",
        )
    )
    user_id: str = Field(
        sa_column=Column(
            String(64),
            ForeignKey("user.id", name="fk_season_user_user"),
            nullable=False,
            comment="用户ID",
        )
    )
    level_id: int | None = Field(
        default=None,
        sa_column=Column(
            BIGINT(unsigned=True),
            ForeignKey("project_level.id", name="fk_season_user_level"),
            nullable=True,
            comment="项目等级ID",
        ),
    )
    participated_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime,
            nullable=True,
            comment="正式报名时间（首次锁定挑战等级时写入）",
        ),
    )
    final_points: int | None = Field(
        default=None,
        sa_column=Column(
            INTEGER(unsigned=True),
            nullable=True,
            comment="赛季最终获得积分，NULL表示尚未结算",
        ),
    )
    status: int = Field(
        default=0,
        sa_column=Column(
            TINYINT(unsigned=True),
            nullable=False,
            server_default=text("0"),
            comment="已锁定项目数量",
        ),
    )
