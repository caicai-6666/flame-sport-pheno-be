from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user_id
from app.services.season_service import season_service

router = APIRouter(prefix="/season", tags=["season"])


@router.get("")
async def check_season_router():
    """赛季子路由存活校验。"""
    return {"code": 200}


@router.get("/current")
async def get_current_season(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """获取当前激活赛季信息。"""
    return await season_service.get_current_season(session=session)


@router.get("/participate_check")
async def check_season_participation(
    season_id: int = Query(..., ge=1),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """检查当前用户是否已正式参与指定赛季，并返回项目挑战等级 ID。"""
    return await season_service.check_season_participation(
        season_id=season_id,
        user_id=user_id,
        session=session,
    )
