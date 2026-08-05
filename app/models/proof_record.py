from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import CheckConstraint, Column, DateTime, Numeric, text
from sqlmodel import Field, SQLModel


class ProofReviewStatus(StrEnum):
    """凭证审核状态：赛季内模型初审，以及管理员持续终审。"""

    PENDING = "pending"
    PRELIMINARY_APPROVED = "preliminary_approved"
    PRELIMINARY_REJECTED = "preliminary_rejected"
    APPROVED = "approved"
    REJECTED = "rejected"


# 管理员终审失败后，该凭证不再参与排行榜统计。
LEADERBOARD_ELIGIBLE_REVIEW_STATUSES = (
    ProofReviewStatus.PRELIMINARY_APPROVED,
    ProofReviewStatus.APPROVED,
)


class ProofRecord(SQLModel, table=True):
    """凭证记录表模型。"""

    __tablename__ = "proof_record"
    __table_args__ = (
        CheckConstraint(
            "progress_delta >= 0 AND progress_delta <= 1",
            name="chk_proof_record_progress_delta",
        ),
        CheckConstraint(
            "increase >= 0 AND increase <= progress_delta",
            name="chk_proof_record_increase",
        ),
    )

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
    # 保留模型给出的原始增量，进度封顶后仍可供后续终审回补使用。
    progress_delta: Decimal = Field(
        default=Decimal("0.0000"),
        ge=Decimal("0"),
        le=Decimal("1"),
        sa_column=Column(
            Numeric(5, 4),
            nullable=False,
            server_default=text("0.0000"),
        ),
    )
    # 当前实际分配到项目进度条的贡献，可能小于模型原始增量。
    increase: Decimal = Field(
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
