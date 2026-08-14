from sqlalchemy import Column, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import TINYINT
from sqlmodel import Field, SQLModel


class Department(SQLModel, table=True):
    """部门表模型。"""

    __tablename__ = "department"
    __table_args__ = (
        UniqueConstraint("name", name="uk_department_name"),
        {
            "mysql_engine": "InnoDB",
            "mysql_default_charset": "utf8mb4",
            "mysql_comment": "部门表",
        },
    )

    id: str = Field(
        sa_column=Column(
            String(64),
            primary_key=True,
            nullable=False,
            comment="部门ID",
        )
    )
    name: str = Field(
        sa_column=Column(
            String(64),
            nullable=False,
            comment="部门名称",
        )
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
