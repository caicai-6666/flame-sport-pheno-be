from sqlalchemy import (
    JSON,
    Column,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT, TINYINT
from sqlmodel import Field, SQLModel


class ProjectRule(SQLModel, table=True):
    """项目规则表模型。"""

    __tablename__ = "project_rule"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "level_id",
            name="uk_project_rule_project_level",
        ),
        Index("idx_project_rule_project_id", "project_id"),
        Index("idx_project_rule_level_id", "level_id"),
        Index("idx_project_rule_status", "status"),
        {
            "mysql_engine": "InnoDB",
            "mysql_default_charset": "utf8mb4",
            "mysql_comment": "项目规则表",
        },
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            BIGINT(unsigned=True),
            primary_key=True,
            autoincrement=True,
            comment="项目规则ID",
        ),
    )
    project_id: int = Field(
        sa_column=Column(
            BIGINT(unsigned=True),
            ForeignKey("project.id", name="fk_project_rule_project"),
            nullable=False,
            comment="项目ID",
        )
    )
    level_id: int = Field(
        sa_column=Column(
            BIGINT(unsigned=True),
            ForeignKey("project_level.id", name="fk_project_rule_level"),
            nullable=False,
            comment="项目等级ID",
        )
    )
    sub_desc: str | None = Field(
        default=None,
        sa_column=Column(String(128), nullable=True, comment="挑战副描述"),
    )
    rule_content: list[dict[str, str]] | str = Field(
        sa_column=Column(
            JSON,
            nullable=False,
            comment="规则指标内容，JSON数组",
        )
    )
    rule_note: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True, comment="规则备注说明"),
    )
    status: int = Field(
        default=1,
        sa_column=Column(
            TINYINT(unsigned=True),
            nullable=False,
            server_default=text("1"),
            comment="状态：1启用，0停用",
        ),
    )
