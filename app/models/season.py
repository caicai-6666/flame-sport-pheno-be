from datetime import date

from sqlmodel import Field, SQLModel


class Season(SQLModel, table=True):
    """赛季表模型。"""

    __tablename__ = "season"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=64)
    start_date: date
    end_date: date
    required_project_count: int = Field(default=3)
    status: int = Field(default=0)
