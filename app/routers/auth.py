from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("")
async def check_auth_router():
    """鉴权子路由存活校验。"""
    return {"code": 200}


@router.post("/login")
async def login(
    auth_code: str = Body(..., embed=True),
    session: AsyncSession = Depends(get_session),
):
    """根据 auth_code 解析用户，验证用户存在后写入认证缓存。"""
    auth_code = await auth_service.login_with_auth_code(
        auth_code=auth_code,
        session=session,
    )

    return {"auth_code": auth_code}
