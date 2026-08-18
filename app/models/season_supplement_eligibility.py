from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT, TINYINT
from sqlmodel import Field, SQLModel


class SeasonSupplementEligibility(SQLModel, table=True):
    """结算中赛季按凭证记录开放的补传资格。"""

    __tablename__ = "season_supplement_eligibility"
    __table_args__ = (
        UniqueConstraint(
            "proof_record_id",
            name="uk_season_supplement_proof_record",
        ),
        Index(
            "idx_season_supplement_user_status",
            "season_user_id",
            "status",
            "id",
        ),
        CheckConstraint(
            "status IN (0, 1)",
            name="chk_season_supplement_status",
        ),
        {
            "mysql_engine": "InnoDB",
            "mysql_default_charset": "utf8mb4",
            "mysql_comment": "赛季补传资格表",
        },
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            BIGINT(unsigned=True),
            primary_key=True,
            autoincrement=True,
            comment="赛季补传资格记录ID",
        ),
    )
    season_user_id: int = Field(
        sa_column=Column(
            BIGINT(unsigned=True),
            ForeignKey(
                "season_user.id",
                name="fk_season_supplement_season_user",
            ),
            nullable=False,
            comment="赛季用户记录ID",
        )
    )
    proof_record_id: int = Field(
        sa_column=Column(
            BIGINT(unsigned=True),
            ForeignKey(
                "proof_record.id",
                name="fk_season_supplement_proof_record",
            ),
            nullable=False,
            comment="允许补传的凭证记录ID",
        )
    )
    status: int = Field(
        default=1,
        sa_column=Column(
            TINYINT(unsigned=True),
            nullable=False,
            server_default=text("1"),
            comment="资格状态：1可补传，0已关闭",
        ),
    )
