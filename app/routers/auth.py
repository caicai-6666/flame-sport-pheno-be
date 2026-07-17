from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.services.auth_service import auth_service

router = APIRouter(tags=["auth"])


@router.post("/login")
async def login(
    access_token: str = Body(..., embed=True),
    session: AsyncSession = Depends(get_session),
):
    """根据 access_token 解析用户，验证用户存在后写入认证缓存。"""
    _ = await auth_service.login_with_access_token(
        access_token=access_token,
        session=session,
    )

    return {"access_token": access_token}
