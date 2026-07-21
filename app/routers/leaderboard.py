from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user_id
from app.services.leaderboard_service import leaderboard_service

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("")
async def check_leaderboard_router():
    """排行榜子路由存活校验。"""
    return {"code": 200}


@router.get("/info")
async def list_leaderboard_info(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """获取当前赛季排行榜用户名称和打卡次数。"""
    return await leaderboard_service.list_leaderboard_info(
        user_id=user_id,
        session=session,
    )
