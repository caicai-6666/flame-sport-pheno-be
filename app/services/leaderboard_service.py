from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.runtime_env import LeaderboardRuntime
from app.repositories.leaderboard_repository import leaderboard_repository
from app.repositories.season_repository import season_repository


class LeaderboardService:
    async def refresh_current_season_snapshot(
        self,
        session: AsyncSession,
    ) -> dict[str, str] | None:
        """刷新当前赛季排行榜快照；无激活赛季时跳过。"""
        season = await season_repository.get_current(session=session)
        if season is None or season.id is None:
            # 冷启动或赛季切换空窗期没有可刷新的快照，不应导致后台任务报错。
            return None

        # 定时任务间隔可配置，因此统计截止到本次刷新时刻，便于短间隔刷新及时反映新凭证。
        cutoff_at = datetime.now()
        await leaderboard_repository.replace_current_season_snapshot(
            session=session,
            season_id=season.id,
            required_project_count=season.required_project_count,
            cutoff_at=cutoff_at,
        )
        await session.commit()

        calculated_at = datetime.now()
        LeaderboardRuntime.set_calculated_at(calculated_at)
        return {
            "calculated_at": calculated_at.isoformat(timespec="seconds"),
            "cutoff_at": cutoff_at.isoformat(timespec="seconds"),
        }

    async def list_leaderboard_info(
        self,
        user_id: str,
        session: AsyncSession,
    ) -> list[dict[str, bool | int | str]]:
        """获取当前赛季排行榜基础信息。"""
        season = await season_repository.get_current(session=session)
        if season is None or season.id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="当前没有激活的赛季",
            )
        leaderboard_entries = await leaderboard_repository.list_current_season_snapshot(
            session=session,
            season_id=season.id,
        )
        return [
            {
                "name": name,
                "department_name": department_name,
                "project_rule_level_id": level_id or 0,
                "checkin_count": checkin_count,
                # 标记当前登录用户所在行，方便前端高亮展示。
                "is_current_user": entry_user_id == user_id,
            }
            for (
                entry_user_id,
                name,
                department_name,
                level_id,
                checkin_count,
            ) in leaderboard_entries
        ]


leaderboard_service = LeaderboardService()
