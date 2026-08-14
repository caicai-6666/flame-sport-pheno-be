from sqlalchemy import Column, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, INTEGER
from sqlmodel import Field, SQLModel


class LeaderboardSnapshot(SQLModel, table=True):
    """排行榜快照表模型。"""

    __tablename__ = "leaderboard_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "season_user_id",
            name="uk_leaderboard_snapshot_season_user",
        ),
        Index("idx_leaderboard_snapshot_checkin_count", "checkin_count"),
        {
            "mysql_engine": "InnoDB",
            "mysql_default_charset": "utf8mb4",
            "mysql_comment": "排行榜快照表",
        },
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            BIGINT(unsigned=True),
            primary_key=True,
            autoincrement=True,
            comment="排行榜快照记录ID",
        ),
    )
    season_user_id: int = Field(
        sa_column=Column(
            BIGINT(unsigned=True),
            ForeignKey(
                "season_user.id",
                name="fk_leaderboard_snapshot_season_user",
            ),
            nullable=False,
            comment="赛季用户记录ID",
        )
    )
    checkin_count: int = Field(
        default=0,
        sa_column=Column(
            INTEGER(unsigned=True),
            nullable=False,
            server_default=text("0"),
            comment="当前赛季累计打卡次数",
        ),
    )
