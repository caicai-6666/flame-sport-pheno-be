from sqlalchemy import Column
from sqlalchemy.dialects.mysql import BIGINT
from sqlmodel import Field, SQLModel


class Product(SQLModel, table=True):
    """商品表模型。"""

    __tablename__ = "product"

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
    name: str = Field(max_length=128)
    description: str | None = Field(default=None, max_length=255)
    points_required: int
    image_url: str | None = Field(default=None, max_length=255)
    status: int = Field(default=1)
