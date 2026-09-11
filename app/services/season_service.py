from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.storage import ensure_proof_record_season_directory
from app.models.season import SeasonStatus
from app.repositories.season_repository import season_repository
from app.repositories.season_user_repository import season_user_repository
from app.services.user_write_guard import (
    BUSINESS_TIMEZONE,
    get_user_write_window,
    is_user_write_frozen,
)


class SeasonService:
    async def get_current_season(
        self,
        session: AsyncSession,
    ) -> dict[str, bool | int | str]:
        """获取当前激活赛季信息。"""
        season = await season_repository.get_current(session=session)
        if season is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="当前没有激活的赛季",
            )

        current_time = datetime.now(BUSINESS_TIMEZONE)
        write_freeze_starts_at, write_available_at = get_user_write_window(
            start_date=season.start_date,
            edit_window_hours=settings.ACTIVE_SEASON_CONFIG_EDIT_WINDOW_HOURS,
        )

        # 当前赛季确认后提前准备凭证目录，避免首次上传因目录缺失失败。
        ensure_proof_record_season_directory(season.id or 0)
        return {
            "season_id": season.id or 0,
            "name": season.name,
            "start_date": season.start_date.isoformat(),
            "end_date": season.end_date.isoformat(),
            "required_project_count": season.required_project_count,
            # 浏览器使用服务端时间轴展示只读状态；真正的写入权限仍由事务内守卫校验。
            "server_time": current_time.isoformat(),
            "user_write_frozen": is_user_write_frozen(
                start_date=season.start_date,
                edit_window_hours=settings.ACTIVE_SEASON_CONFIG_EDIT_WINDOW_HOURS,
                current_time=current_time,
            ),
            "user_write_freeze_starts_at": write_freeze_starts_at.isoformat(),
            "user_write_available_at": write_available_at.isoformat(),
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
        if season is None or season.status != SeasonStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="赛季不存在或未激活",
            )

        season_user = await season_user_repository.get_by_season_id_and_user_id(
            session=session,
            season_id=season_id,
            user_id=user_id,
        )
        if season_user is not None and season_user.level_id is not None:
            return {"project_rule_level_id": season_user.level_id}

        self.ensure_participation_period_allowed(season.start_date)

        if season_user is None or season_user.level_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="用户尚未正式参与该赛季",
            )

    def ensure_participation_period_allowed(self, start_date: date) -> None:
        """校验当前日期是否仍处于允许参与赛季的时间范围内。"""
        today = datetime.now(BUSINESS_TIMEZONE).date()
        # 已被后台提前激活、但尚未到开始日的赛季允许用户抢先参与。
        if start_date > today:
            return

        days_since_start = (today - start_date).days
        # 开始日计入报名窗口；日期差达到 N 时即截止，与配置保护期统一使用上海时区。
        if days_since_start >= settings.SEASON_PARTICIPATION_ALLOWED_DAYS:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="已超过赛季报名时间",
            )


season_service = SeasonService()
