from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, TINYINT
from sqlmodel import Field, SQLModel


class GiftDistributionStatus(StrEnum):
    """商品兑换礼品的发放状态。"""

    PENDING = "pending"
    DISTRIBUTED = "distributed"


class PointRecord(SQLModel, table=True):
    """积分变动记录表模型。"""

    __tablename__ = "point_record"
    __table_args__ = (
        Index("idx_point_record_user_created_at", "user_id", "created_at"),
        Index("idx_point_record_product_id", "product_id"),
        Index(
            "idx_point_record_gift_distribution",
            "change_type",
            "gift_distribution_status",
            "created_at",
        ),
        CheckConstraint(
            "gift_distribution_status IN ('pending', 'distributed')",
            name="chk_point_record_gift_distribution_status",
        ),
        CheckConstraint(
            "gift_distribution_status <> 'distributed' "
            "OR (change_type = 'exchange' AND product_id IS NOT NULL)",
            name="chk_point_record_distributed_exchange",
        ),
        {
            "mysql_engine": "InnoDB",
            "mysql_default_charset": "utf8mb4",
            "mysql_comment": "积分变动记录表",
        },
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            BIGINT(unsigned=True),
            primary_key=True,
            autoincrement=True,
            comment="积分变动记录ID",
        ),
    )
    user_id: str = Field(
        sa_column=Column(
            String(64),
            ForeignKey("user.id", name="fk_point_record_user"),
            nullable=False,
            comment="用户ID",
        )
    )
    product_id: int | None = Field(
        default=None,
        sa_column=Column(
            BIGINT(unsigned=True),
            ForeignKey("product.id", name="fk_point_record_product"),
            nullable=True,
            comment="商品ID，仅商品兑换时有值",
        ),
    )
    change_type: str = Field(
        sa_column=Column(
            String(32),
            nullable=False,
            comment=(
                "积分变动类型：season_reward赛季奖励，exchange商品兑换，"
                "manual_adjust后台调整"
            ),
        )
    )
    change_points: int = Field(
        sa_column=Column(
            INTEGER,
            nullable=False,
            comment="积分变动值，正数增加，负数扣减",
        )
    )
    points_after: int = Field(
        sa_column=Column(
            INTEGER(unsigned=True),
            nullable=False,
            comment="变动后的积分余额",
        )
    )
    description: str | None = Field(
        default=None,
        sa_column=Column(
            String(255),
            nullable=True,
            comment="积分变动描述",
        ),
    )
    status: int = Field(
        default=1,
        sa_column=Column(
            TINYINT(unsigned=True),
            nullable=False,
            server_default=text("1"),
            comment="状态：1有效，0作废",
        ),
    )
    gift_distribution_status: str = Field(
        default=GiftDistributionStatus.PENDING.value,
        sa_column=Column(
            String(16),
            nullable=False,
            server_default=text("'pending'"),
            comment="礼品发放状态：pending待发放，distributed已发放",
        ),
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(
            DateTime,
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
            comment="积分变动时间",
        ),
    )
