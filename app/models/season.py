from datetime import date
from enum import IntEnum

from sqlalchemy import Column, Date, Index, String, text
from sqlalchemy.dialects.mysql import BIGINT, TINYINT
from sqlmodel import Field, SQLModel


class SeasonStatus(IntEnum):
    """赛季生命周期状态。"""

    NOT_STARTED = 0
    ACTIVE = 1
    SETTLING = 2
    ENDED = 3


class Season(SQLModel, table=True):
    """赛季表模型。"""

    __tablename__ = "season"
    __table_args__ = (
        Index("idx_season_status", "status"),
        Index("idx_season_date", "start_date", "end_date"),
        {
            "mysql_engine": "InnoDB",
            "mysql_default_charset": "utf8mb4",
            "mysql_comment": "赛季表",
        },
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            BIGINT(unsigned=True),
            primary_key=True,
            autoincrement=True,
            comment="赛季ID",
        ),
    )
    name: str = Field(
        sa_column=Column(String(64), nullable=False, comment="赛季名称")
    )
    start_date: date = Field(
        sa_column=Column(Date, nullable=False, comment="赛季开始日期")
    )
    end_date: date = Field(
        sa_column=Column(Date, nullable=False, comment="赛季结束日期")
    )
    required_project_count: int = Field(
        default=3,
        sa_column=Column(
            TINYINT(unsigned=True),
            nullable=False,
            server_default=text("3"),
            comment="当前赛季要求选择的项目数量",
        ),
    )
    status: int = Field(
        default=SeasonStatus.NOT_STARTED,
        sa_column=Column(
            TINYINT(unsigned=True),
            nullable=False,
            server_default=text("0"),
            comment="状态：0未开始，1进行中，2结算中，3已结束",
        ),
    )
