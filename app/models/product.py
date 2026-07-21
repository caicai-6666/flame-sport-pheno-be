from sqlmodel import Field, SQLModel


class Product(SQLModel, table=True):
    """商品表模型。"""

    __tablename__ = "product"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=128)
    description: str | None = Field(default=None, max_length=255)
    points_required: int
    image_url: str | None = Field(default=None, max_length=255)
    status: int = Field(default=1)
