from sqlalchemy import Column, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, TINYINT
from sqlmodel import Field, SQLModel


# 上传配置的 record_type 同时表达可供不同项目复用的月度审核阶段。
MONTH_START_RECORD_TYPE = "月初记录"
MONTH_END_RECORD_TYPE = "月末记录"


class ProjectUploadConfig(SQLModel, table=True):
    """项目上传配置表模型。"""

    __tablename__ = "project_upload_config"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "record_type",
            name="uk_project_upload_config_project_record_type",
        ),
        Index("idx_project_upload_config_project_id", "project_id"),
        Index("idx_project_upload_config_status", "status"),
        Index("idx_project_upload_config_sort_order", "sort_order"),
        {
            "mysql_engine": "InnoDB",
            "mysql_default_charset": "utf8mb4",
            "mysql_comment": "项目上传配置表",
        },
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            BIGINT(unsigned=True),
            primary_key=True,
            autoincrement=True,
            comment="项目上传配置ID",
        ),
    )
    project_id: int = Field(
        sa_column=Column(
            BIGINT(unsigned=True),
            ForeignKey("project.id", name="fk_project_upload_config_project"),
            nullable=False,
            comment="项目ID",
        )
    )
    record_type: str = Field(
        sa_column=Column(
            String(64),
            nullable=False,
            comment="凭证类型展示名称",
        )
    )
    upload_hint: str = Field(
        sa_column=Column(
            String(255),
            nullable=False,
            comment="上传图片下方的凭证类型提示",
        )
    )
    note_example: str | None = Field(
        default=None,
        sa_column=Column(
            String(255),
            nullable=True,
            comment="备注输入框填写示例",
        ),
    )
    sort_order: int = Field(
        default=0,
        sa_column=Column(
            INTEGER(unsigned=True),
            nullable=False,
            server_default=text("0"),
            comment="展示排序，数值越小越靠前",
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
