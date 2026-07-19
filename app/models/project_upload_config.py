from sqlmodel import Field, SQLModel


class ProjectUploadConfig(SQLModel, table=True):
    """项目上传配置表模型。"""

    __tablename__ = "project_upload_config"

    id: int | None = Field(default=None, primary_key=True)
    project_id: int
    record_type: str = Field(max_length=64)
    upload_hint: str = Field(max_length=255)
    note_example: str | None = Field(default=None, max_length=255)
    sort_order: int = Field(default=0)
    status: int = Field(default=1)
