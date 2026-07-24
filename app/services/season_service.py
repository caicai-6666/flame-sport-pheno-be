from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.runtime_env import CurrentSeasonRuntime
from app.core.storage import ensure_proof_record_season_directory
from app.repositories.season_repository import season_repository
from app.repositories.season_user_repository import season_user_repository


class SeasonService:
    async def get_current_season(self, session: AsyncSession) -> dict[str, int | str]:
        """获取当前激活赛季信息。"""
        season = await season_repository.get_current(session=session)
        if season is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="当前没有激活的赛季",
            )

        # 当前赛季确认后提前准备凭证目录，避免首次上传因目录缺失失败。
        ensure_proof_record_season_directory(season.id or 0)
        await self._load_current_season_runtime_if_needed(
            season_id=season.id or 0,
            required_project_count=season.required_project_count,
        )
        return {
            "season_id": season.id or 0,
            "name": season.name,
            "start_date": season.start_date.isoformat(),
            "end_date": season.end_date.isoformat(),
            "required_project_count": CurrentSeasonRuntime.required_project_count or 0,
        }

    async def check_season_participation(
        self,
        season_id: int,
        user_id: str,
        session: AsyncSession,
    ) -> dict[str, int]:
        """检查用户是否已正式参与指定赛季，并返回已锁定的项目挑战等级 ID。"""
        season = await season_repository.get_by_id(
            session=session,
            season_id=season_id,
        )
        if season is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="赛季不存在",
            )

        season_user = await season_user_repository.get_by_season_id_and_user_id(
            session=session,
            season_id=season_id,
            user_id=user_id,
        )
        if season_user is not None and season_user.level_id is not None:
            return {"project_rule_level_id": season_user.level_id}

        self._ensure_participation_period_allowed(season.start_date)

        if season_user is None or season_user.level_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="用户尚未正式参与该赛季",
            )

    def _ensure_participation_period_allowed(self, start_date: date) -> None:
        """校验当前日期是否仍处于允许参与赛季的时间范围内。"""
        today = date.today()
        # 已被后台提前激活、但尚未到开始日的赛季允许用户抢先参与。
        if start_date > today:
            return

        days_since_start = (today - start_date).days
        if days_since_start > settings.SEASON_PARTICIPATION_ALLOWED_DAYS:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="已超过赛季报名时间",
            )

    async def _load_current_season_runtime_if_needed(
        self,
        season_id: int,
        required_project_count: int,
    ) -> None:
        """当前赛季运行时缓存未初始化时，写入当前激活赛季配置。"""
        if CurrentSeasonRuntime.is_initialized():
            return

        CurrentSeasonRuntime.set(
            season_id=season_id,
            required_project_count=required_project_count,
        )


season_service = SeasonService()
