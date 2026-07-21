from sqlmodel import Field, SQLModel


class Department(SQLModel, table=True):
    """部门表模型。"""

    __tablename__ = "department"

    id: str = Field(primary_key=True, max_length=64)
    name: str = Field(max_length=64)
    status: int = Field(default=1)
