from datetime import datetime

from sqlalchemy import Column, DateTime, text
from sqlmodel import Field, SQLModel


class ProofRecord(SQLModel, table=True):
    """凭证记录表模型。"""

    __tablename__ = "proof_record"

    id: int | None = Field(default=None, primary_key=True)
    season_user_id: int
    project_id: int
    project_upload_config_id: int
    image_url: str = Field(max_length=500)
    note: str | None = Field(default=None, max_length=255)
    review_status: str = Field(default="pending", max_length=32)
    review_comment: str | None = Field(default=None, max_length=500)
    status: int = Field(default=1)
    created_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(
            DateTime,
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )
