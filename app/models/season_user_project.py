from sqlmodel import Field, SQLModel


class SeasonUserProject(SQLModel, table=True):
    """赛季用户项目表模型。"""

    __tablename__ = "season_user_project"

    id: int | None = Field(default=None, primary_key=True)
    season_user_id: int
    project_id: int
    status: int = Field(default=1)
