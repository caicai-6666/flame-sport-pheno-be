from decimal import Decimal

from sqlalchemy import Column, ForeignKey, Index, Numeric, String, text
from sqlalchemy.dialects.mysql import TINYINT
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """用户表模型。"""

    __tablename__ = "user"
    __table_args__ = (
        Index("idx_user_department_id", "department_id"),
        Index("idx_user_status", "status"),
        {
            "mysql_engine": "InnoDB",
            "mysql_default_charset": "utf8mb4",
            "mysql_comment": "用户表",
        },
    )

    id: str = Field(
        sa_column=Column(
            String(64),
            primary_key=True,
            nullable=False,
            comment="用户ID",
        )
    )
    name: str = Field(
        sa_column=Column(String(64), nullable=False, comment="用户名称")
    )
    department_id: str = Field(
        sa_column=Column(
            String(64),
            ForeignKey("department.id", name="fk_user_department"),
            nullable=False,
            comment="所属部门ID",
        )
    )
    avatar_url: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True, comment="头像地址"),
    )
    height_cm: Decimal | None = Field(
        default=None,
        sa_column=Column(
            Numeric(5, 2),
            nullable=True,
            comment="用户身高，单位厘米，用于BMI计算",
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
