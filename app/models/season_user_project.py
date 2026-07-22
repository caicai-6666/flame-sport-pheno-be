from decimal import Decimal

from sqlalchemy import CheckConstraint, Column, Numeric, text
from sqlmodel import Field, SQLModel


class SeasonUserProject(SQLModel, table=True):
    """赛季用户项目表模型。"""

    __tablename__ = "season_user_project"
    __table_args__ = (
        CheckConstraint(
            "completion_progress >= 0 AND completion_progress <= 1",
            name="chk_season_user_project_completion_progress",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    season_user_id: int
    project_id: int
    completion_progress: Decimal = Field(
        default=Decimal("0.0000"),
        ge=Decimal("0"),
        le=Decimal("1"),
        sa_column=Column(
            Numeric(5, 4),
            nullable=False,
            server_default=text("0.0000"),
        ),
    )
    status: int = Field(default=1)
