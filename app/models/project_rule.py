from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class ProjectRule(SQLModel, table=True):
    """项目规则表模型。"""

    __tablename__ = "project_rule"

    id: int | None = Field(default=None, primary_key=True)
    project_id: int
    level_id: int
    sub_desc: str | None = Field(default=None, max_length=128)
    rule_content: list[dict[str, str]] | str = Field(sa_column=Column(JSON))
    rule_note: str | None = Field(default=None, max_length=255)
    status: int = Field(default=1)
