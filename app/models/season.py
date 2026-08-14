from datetime import date
from enum import IntEnum

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

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=64)
    start_date: date
    end_date: date
    required_project_count: int = Field(default=3)
    status: int = Field(default=0)
