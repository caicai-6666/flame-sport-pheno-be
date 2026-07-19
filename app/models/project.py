from sqlmodel import Field, SQLModel


class Project(SQLModel, table=True):
    """项目表模型。"""

    __tablename__ = "project"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=64)
    description: str | None = Field(default=None, max_length=255)
    icon_url: str | None = Field(default=None, max_length=255)
    status: int = Field(default=1)
