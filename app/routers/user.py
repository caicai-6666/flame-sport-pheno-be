from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user_id
from app.services.user_service import user_service

router = APIRouter(prefix="/user", tags=["user"])


@router.get("")
async def check_user_router():
    """用户子路由存活校验。"""
    return {"code": 200}


@router.post("/profile")
async def update_user_profile(
    height_cm: float = Body(..., embed=True),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """设置当前用户资料，目前只支持身高。"""
    return await user_service.update_profile(
        user_id=user_id,
        height_cm=height_cm,
        session=session,
    )
