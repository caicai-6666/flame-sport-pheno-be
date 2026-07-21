from sqlmodel import Field, SQLModel


class LeaderboardSnapshot(SQLModel, table=True):
    """排行榜快照表模型。"""

    __tablename__ = "leaderboard_snapshot"

    id: int | None = Field(default=None, primary_key=True)
    season_user_id: int
    checkin_count: int = Field(default=0)
