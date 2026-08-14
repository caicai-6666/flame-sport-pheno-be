from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.season import Season, SeasonStatus


class SeasonRepository:
    async def get_by_id(self, session: AsyncSession, season_id: int) -> Season | None:
        """根据赛季 ID 查询赛季。"""
        result = await session.execute(
            select(Season).where(Season.id == season_id)
        )
        return result.scalar_one_or_none()

    async def get_current(self, session: AsyncSession) -> Season | None:
        """查询当前激活的赛季。"""
        result = await session.execute(
            select(Season)
            .where(Season.status == SeasonStatus.ACTIVE)
            .order_by(Season.start_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


season_repository = SeasonRepository()
