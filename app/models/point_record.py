from datetime import datetime

from sqlalchemy import Column, DateTime, text
from sqlmodel import Field, SQLModel


class PointRecord(SQLModel, table=True):
    """积分变动记录表模型。"""

    __tablename__ = "point_record"

    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(max_length=64)
    product_id: int | None = None
    change_type: str = Field(max_length=32)
    change_points: int
    points_after: int
    description: str | None = Field(default=None, max_length=255)
    status: int = Field(default=1)
    created_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(
            DateTime,
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )
