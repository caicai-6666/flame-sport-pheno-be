from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user_id
from app.services.suggestion_service import suggestion_service

router = APIRouter(prefix="/suggestion", tags=["suggestion"])


@router.post("/remark", status_code=status.HTTP_201_CREATED)
async def create_suggestion_remark(
    remark: str = Body(..., embed=True, min_length=1),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """提交当前用户的建议。"""
    return await suggestion_service.create_remark(
        user_id=user_id,
        remark=remark,
        session=session,
    )
