from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Numeric,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT, TINYINT
from sqlmodel import Field, SQLModel


class SeasonUserProject(SQLModel, table=True):
    """赛季用户项目表模型。"""

    __tablename__ = "season_user_project"
    __table_args__ = (
        UniqueConstraint(
            "season_user_id",
            "project_id",
            name="uk_season_user_project",
        ),
        Index("idx_season_user_project_season_user_id", "season_user_id"),
        Index("idx_season_user_project_project_id", "project_id"),
        Index("idx_season_user_project_status", "status"),
        CheckConstraint(
            "completion_progress >= 0 AND completion_progress <= 1",
            name="chk_season_user_project_completion_progress",
        ),
        {
            "mysql_engine": "InnoDB",
            "mysql_default_charset": "utf8mb4",
            "mysql_comment": "赛季用户项目表",
        },
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            BIGINT(unsigned=True),
            primary_key=True,
            autoincrement=True,
            comment="赛季用户项目记录ID",
        ),
    )
    season_user_id: int = Field(
        sa_column=Column(
            BIGINT(unsigned=True),
            ForeignKey(
                "season_user.id",
                name="fk_season_user_project_season_user",
            ),
            nullable=False,
            comment="赛季用户记录ID",
        )
    )
    project_id: int = Field(
        sa_column=Column(
            BIGINT(unsigned=True),
            ForeignKey("project.id", name="fk_season_user_project_project"),
            nullable=False,
            comment="项目ID",
        )
    )
    completion_progress: Decimal = Field(
        default=Decimal("0.0000"),
        ge=Decimal("0"),
        le=Decimal("1"),
        sa_column=Column(
            Numeric(5, 4),
            nullable=False,
            server_default=text("0.0000"),
            comment="本赛季项目完成进度，取值0.0000～1.0000",
        ),
    )
    status: int = Field(
        default=1,
        sa_column=Column(
            TINYINT(unsigned=True),
            nullable=False,
            server_default=text("1"),
            comment="状态：1已锁定，0无效/取消",
        ),
    )
