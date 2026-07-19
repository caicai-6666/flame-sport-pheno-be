from decimal import Decimal

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """用户表模型。"""

    __tablename__ = "user"

    id: str = Field(primary_key=True, max_length=64)
    name: str = Field(max_length=64)
    department_id: str = Field(max_length=64)
    avatar_url: str | None = Field(default=None, max_length=255)
    height_cm: Decimal | None = Field(
        default=None,
        max_digits=5,
        decimal_places=2,
    )
    status: int = Field(default=1)
