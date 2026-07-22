from sqlmodel import Field, SQLModel


class ProjectLevel(SQLModel, table=True):
    """项目等级表模型。"""

    __tablename__ = "project_level"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=32)
    reward: int = Field(default=0)
    status: int = Field(default=1)
