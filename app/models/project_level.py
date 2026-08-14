from sqlalchemy import Column, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, TINYINT
from sqlmodel import Field, SQLModel


class ProjectLevel(SQLModel, table=True):
    """项目等级表模型。"""

    __tablename__ = "project_level"
    __table_args__ = (
        UniqueConstraint("name", name="uk_project_level_name"),
        Index("idx_project_level_status", "status"),
        Index("idx_project_level_sort_order", "reward"),
        {
            "mysql_engine": "InnoDB",
            "mysql_default_charset": "utf8mb4",
            "mysql_comment": "项目等级表",
        },
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            BIGINT(unsigned=True),
            primary_key=True,
            autoincrement=True,
            comment="项目等级ID",
        ),
    )
    name: str = Field(
        sa_column=Column(String(32), nullable=False, comment="等级名称")
    )
    reward: int = Field(
        default=0,
        sa_column=Column(
            INTEGER(unsigned=True),
            nullable=False,
            server_default=text("0"),
            comment="挑战成功后奖励积分",
        ),
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
