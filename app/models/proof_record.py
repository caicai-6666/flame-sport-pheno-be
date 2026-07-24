from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Column, DateTime, Numeric, text
from sqlmodel import Field, SQLModel


class ProofReviewStatus(StrEnum):
    """凭证审核状态：赛季内初审，赛季结束后统一终审。"""

    PENDING = "pending"
    PRELIMINARY_APPROVED = "preliminary_approved"
    PRELIMINARY_REJECTED = "preliminary_rejected"
    APPROVED = "approved"
    REJECTED = "rejected"


# 终审发生在赛季结束后，不改变凭证已通过初审这一排行榜事实。
LEADERBOARD_ELIGIBLE_REVIEW_STATUSES = (
    ProofReviewStatus.PRELIMINARY_APPROVED,
    ProofReviewStatus.APPROVED,
    ProofReviewStatus.REJECTED,
)


class ProofRecord(SQLModel, table=True):
    """凭证记录表模型。"""

    __tablename__ = "proof_record"

    id: int | None = Field(default=None, primary_key=True)
    season_user_id: int
    project_id: int
    project_upload_config_id: int
    image_url: str = Field(max_length=500)
    note: str | None = Field(default=None, max_length=255)
    review_status: str = Field(
        default=ProofReviewStatus.PENDING.value,
        max_length=32,
    )
    review_comment: str | None = Field(default=None, max_length=500)
    # 保存本条凭证实际推进的进度，重传时才能精确撤销旧版本的贡献。
    preliminary_progress_delta: Decimal = Field(
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
    created_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(
            DateTime,
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )
