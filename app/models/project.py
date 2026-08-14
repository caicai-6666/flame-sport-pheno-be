from sqlalchemy import Column, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, TINYINT
from sqlmodel import Field, SQLModel


class Project(SQLModel, table=True):
    """项目表模型。"""

    __tablename__ = "project"
    __table_args__ = (
        UniqueConstraint("name", name="uk_project_name"),
        Index("idx_project_status", "status"),
        {
            "mysql_engine": "InnoDB",
            "mysql_default_charset": "utf8mb4",
            "mysql_comment": "项目表",
        },
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            BIGINT(unsigned=True),
            primary_key=True,
            autoincrement=True,
            comment="项目ID",
        ),
    )
    name: str = Field(
        sa_column=Column(String(64), nullable=False, comment="项目名称")
    )
    description: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True, comment="项目说明"),
    )
    icon_url: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True, comment="项目图标地址"),
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
