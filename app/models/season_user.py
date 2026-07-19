from sqlmodel import Field, SQLModel


class SeasonUser(SQLModel, table=True):
    """赛季用户表模型。"""

    __tablename__ = "season_user"

    id: int | None = Field(default=None, primary_key=True)
    season_id: int
    user_id: str = Field(max_length=64)
    level_id: int | None = None
    final_points: int | None = None
    status: int = Field(default=0)
