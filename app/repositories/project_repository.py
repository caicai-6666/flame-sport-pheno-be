from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.project import Project
from app.models.project_level import ProjectLevel
from app.models.project_rule import ProjectRule
from app.models.project_upload_config import ProjectUploadConfig


class ProjectRepository:
    async def get_visible_by_id(
        self,
        session: AsyncSession,
        project_id: int,
    ) -> Project | None:
        """根据项目 ID 查询可见项目。"""
        result = await session.execute(
            select(Project)
            .where(Project.id == project_id)
            .where(Project.status == 1)
        )
        return result.scalar_one_or_none()

    async def list_visible(self, session: AsyncSession) -> list[Project]:
        """查询所有可见项目。"""
        result = await session.execute(
            select(Project)
            .where(Project.status == 1)
            .order_by(Project.id)
        )
        return list(result.scalars().all())

    async def get_visible_level_by_id(
        self,
        session: AsyncSession,
        project_rule_level_id: int,
    ) -> ProjectLevel | None:
        """根据挑战等级 ID 查询启用的挑战等级。"""
        result = await session.execute(
            select(ProjectLevel)
            .where(ProjectLevel.id == project_rule_level_id)
            .where(ProjectLevel.status == 1)
        )
        return result.scalar_one_or_none()

    async def list_visible_rules_by_project_id(
        self,
        session: AsyncSession,
        project_id: int,
    ) -> list[tuple[ProjectRule, ProjectLevel]]:
        """根据项目 ID 查询启用的项目规则和对应挑战等级。"""
        result = await session.execute(
            select(ProjectRule, ProjectLevel)
            .join(ProjectLevel, ProjectLevel.id == ProjectRule.level_id)
            .where(ProjectRule.project_id == project_id)
            .where(ProjectRule.status == 1)
            .where(ProjectLevel.status == 1)
        )
        return list(result.all())

    async def list_enabled_upload_configs_by_project_id(
        self,
        session: AsyncSession,
        project_id: int,
    ) -> list[ProjectUploadConfig]:
        """根据项目 ID 查询启用的上传凭证配置，并按展示顺序排序。"""
        result = await session.execute(
            select(ProjectUploadConfig)
            .where(ProjectUploadConfig.project_id == project_id)
            .where(ProjectUploadConfig.status == 1)
            .order_by(
                ProjectUploadConfig.sort_order.asc(),
                ProjectUploadConfig.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def get_enabled_upload_config(
        self,
        session: AsyncSession,
        project_id: int,
        record_type: str,
    ) -> ProjectUploadConfig | None:
        """查询项目下指定启用凭证类型配置。"""
        result = await session.execute(
            select(ProjectUploadConfig)
            .where(ProjectUploadConfig.project_id == project_id)
            .where(ProjectUploadConfig.record_type == record_type)
            .where(ProjectUploadConfig.status == 1)
        )
        return result.scalar_one_or_none()

    async def get_enabled_upload_config_by_id(
        self,
        session: AsyncSession,
        project_id: int,
        project_upload_config_id: int,
    ) -> ProjectUploadConfig | None:
        """根据上传配置 ID 查询当前项目下启用的上传配置。"""
        result = await session.execute(
            select(ProjectUploadConfig)
            .where(ProjectUploadConfig.id == project_upload_config_id)
            .where(ProjectUploadConfig.project_id == project_id)
            .where(ProjectUploadConfig.status == 1)
        )
        return result.scalar_one_or_none()


project_repository = ProjectRepository()
