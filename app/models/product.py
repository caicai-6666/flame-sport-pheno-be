from sqlalchemy import Column, Index, String, text
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, TINYINT
from sqlmodel import Field, SQLModel


class Product(SQLModel, table=True):
    """商品表模型。"""

    __tablename__ = "product"
    __table_args__ = (
        Index("idx_product_status", "status"),
        Index("idx_product_points_required", "points_required"),
        {
            "mysql_engine": "InnoDB",
            "mysql_default_charset": "utf8mb4",
            "mysql_comment": "商品表",
        },
    )

    # 与 point_record.product_id 保持相同的无符号大整数类型，确保外键可创建。
    id: int | None = Field(
        default=None,
        sa_column=Column(
            BIGINT(unsigned=True),
            primary_key=True,
            autoincrement=True,
            comment="商品ID",
        ),
    )
    name: str = Field(
        sa_column=Column(String(128), nullable=False, comment="商品名称")
    )
    description: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True, comment="商品说明"),
    )
    points_required: int = Field(
        sa_column=Column(
            INTEGER(unsigned=True),
            nullable=False,
            comment="兑换所需积分",
        )
    )
    image_url: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True, comment="商品图片地址"),
    )
    status: int = Field(
        default=1,
        sa_column=Column(
            TINYINT(unsigned=True),
            nullable=False,
            server_default=text("1"),
            comment="状态：1上架，0下架",
        ),
    )
