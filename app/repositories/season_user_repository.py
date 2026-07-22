from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func
from sqlmodel import select

from app.models.season_user import SeasonUser
from app.models.season_user_project import SeasonUserProject


class SeasonUserRepository:
    async def get_by_season_id_and_user_id(
        self,
        session: AsyncSession,
        season_id: int,
        user_id: str,
    ) -> SeasonUser | None:
        """根据赛季 ID 和用户 ID 查询赛季用户记录。"""
        result = await session.execute(
            select(SeasonUser)
            .where(SeasonUser.season_id == season_id)
            .where(SeasonUser.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def lock_by_id(
        self,
        session: AsyncSession,
        season_user_id: int,
    ) -> SeasonUser | None:
        """通过行锁锁定赛季用户记录，避免并发写入同一用户赛季数据。"""
        result = await session.execute(
            select(SeasonUser)
            .where(SeasonUser.id == season_user_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        session: AsyncSession,
        season_id: int,
        user_id: str,
    ) -> SeasonUser:
        """创建赛季用户记录。"""
        season_user = SeasonUser(
            season_id=season_id,
            user_id=user_id,
            status=0,
        )
        session.add(season_user)
        await session.flush()
        return season_user

    async def get_project_lock(
        self,
        session: AsyncSession,
        season_user_id: int,
        project_id: int,
    ) -> SeasonUserProject | None:
        """查询指定赛季用户项目锁定记录。"""
        result = await session.execute(
            select(SeasonUserProject)
            .where(SeasonUserProject.season_user_id == season_user_id)
            .where(SeasonUserProject.project_id == project_id)
        )
        return result.scalar_one_or_none()

    async def lock_active_project(
        self,
        session: AsyncSession,
        season_user_id: int,
        project_id: int,
    ) -> SeasonUserProject | None:
        """锁定有效赛季项目，供初审结果和完成进度在同一事务内写入。"""
        result = await session.execute(
            select(SeasonUserProject)
            .where(SeasonUserProject.season_user_id == season_user_id)
            .where(SeasonUserProject.project_id == project_id)
            .where(SeasonUserProject.status == 1)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def create_project_lock(
        self,
        session: AsyncSession,
        season_user_id: int,
        project_id: int,
    ) -> SeasonUserProject:
        """创建赛季用户项目锁定记录。"""
        season_user_project = SeasonUserProject(
            season_user_id=season_user_id,
            project_id=project_id,
            completion_progress=Decimal("0.0000"),
            status=1,
        )
        session.add(season_user_project)
        await session.flush()
        return season_user_project

    async def list_locked_project_ids(
        self,
        session: AsyncSession,
        season_user_id: int,
    ) -> list[int]:
        """查询赛季用户已锁定且有效的项目 ID。"""
        result = await session.execute(
            select(SeasonUserProject.project_id)
            .where(SeasonUserProject.season_user_id == season_user_id)
            .where(SeasonUserProject.status == 1)
            .order_by(SeasonUserProject.id)
        )
        return list(result.scalars().all())

    async def list_locked_projects_with_progress(
        self,
        session: AsyncSession,
        season_user_id: int,
    ) -> list[SeasonUserProject]:
        """查询赛季用户已锁定项目及其当前完成进度。"""
        result = await session.execute(
            select(SeasonUserProject)
            .where(SeasonUserProject.season_user_id == season_user_id)
            .where(SeasonUserProject.status == 1)
            .order_by(SeasonUserProject.id)
        )
        return list(result.scalars().all())

    async def count_locked_projects(
        self,
        session: AsyncSession,
        season_user_id: int,
    ) -> int:
        """统计赛季用户有效锁定项目数量。"""
        result = await session.execute(
            select(func.count())
            .select_from(SeasonUserProject)
            .where(SeasonUserProject.season_user_id == season_user_id)
            .where(SeasonUserProject.status == 1)
        )
        return int(result.scalar_one())


season_user_repository = SeasonUserRepository()
