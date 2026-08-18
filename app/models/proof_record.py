from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT, TINYINT
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
        Index("idx_proof_record_season_user_id", "season_user_id"),
        Index("idx_proof_record_project_id", "project_id"),
        Index(
            "idx_proof_record_project_upload_config_id",
            "project_upload_config_id",
        ),
        Index("idx_proof_record_review_status", "review_status"),
        Index("idx_proof_record_status", "status"),
        Index(
            "idx_proof_record_season_project_proof_date_status",
            "season_user_id",
            "project_id",
            "proof_date",
            "status",
        ),
        Index("idx_proof_record_created_at", "created_at"),
        CheckConstraint(
            "progress_delta >= 0 AND progress_delta <= 1",
            name="chk_proof_record_progress_delta",
        ),
        CheckConstraint(
            "increase >= 0 AND increase <= progress_delta",
            name="chk_proof_record_increase",
        ),
        {
            "mysql_engine": "InnoDB",
            "mysql_default_charset": "utf8mb4",
            "mysql_comment": "凭证记录表",
        },
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            BIGINT(unsigned=True),
            primary_key=True,
            autoincrement=True,
            comment="凭证记录ID",
        ),
    )
    season_user_id: int = Field(
        sa_column=Column(
            BIGINT(unsigned=True),
            ForeignKey("season_user.id", name="fk_proof_record_season_user"),
            nullable=False,
            comment="赛季用户记录ID",
        )
    )
    project_id: int = Field(
        sa_column=Column(
            BIGINT(unsigned=True),
            ForeignKey("project.id", name="fk_proof_record_project"),
            nullable=False,
            comment="项目ID",
        )
    )
    project_upload_config_id: int = Field(
        sa_column=Column(
            BIGINT(unsigned=True),
            ForeignKey(
                "project_upload_config.id",
                name="fk_proof_record_project_upload_config",
            ),
            nullable=False,
            comment="项目上传配置ID",
        )
    )
    image_url: str = Field(
        sa_column=Column(String(500), nullable=False, comment="上传图片路径")
    )
    note: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True, comment="用户备注"),
    )
    # 运动实际发生日期；与 created_at（实际提交时间）分开保存。
    proof_date: date = Field(
        sa_column=Column(
            Date,
            nullable=False,
            comment="凭证对应的实际运动日期",
        )
    )
    review_status: str = Field(
        default=ProofReviewStatus.PENDING.value,
        sa_column=Column(
            String(32),
            nullable=False,
            server_default=text("'pending'"),
            comment=(
                "审核状态：pending待初审，preliminary_approved初审通过，"
                "preliminary_rejected初审失败，approved终审通过，"
                "rejected终审失败"
            ),
        ),
    )
    review_comment: str | None = Field(
        default=None,
        sa_column=Column(
            String(500),
            nullable=True,
            comment="初审或终审的审核说明，终审时可覆盖初审意见",
        ),
    )
    # 保留模型给出的原始增量，进度封顶后仍可供后续终审回补使用。
    progress_delta: Decimal = Field(
        default=Decimal("0.0000"),
        ge=Decimal("0"),
        le=Decimal("1"),
        sa_column=Column(
            Numeric(5, 4),
            nullable=False,
            server_default=text("0.0000"),
            comment="大模型初审给出的原始项目进度增量",
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
            comment="当前凭证实际分配到项目进度条的贡献",
        ),
    )
    status: int = Field(
        default=1,
        sa_column=Column(
            TINYINT(unsigned=True),
            nullable=False,
            server_default=text("1"),
            comment="状态：1正常，0无效/删除",
        ),
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(
            DateTime,
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
            comment="上传时间",
        ),
    )
