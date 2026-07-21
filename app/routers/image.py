from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user_id
from app.services.image_service import image_service

router = APIRouter(prefix="/image", tags=["image"])


@router.get("")
async def check_image_router():
    """图片子路由存活校验。"""
    return {"code": 200}


@router.get("/avatar")
async def get_avatar(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """校验 Authorization 后，返回当前用户可访问的头像图片。"""
    image_path = await image_service.get_avatar_image_path(
        user_id=user_id,
        session=session,
    )
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="头像文件不存在")

    return FileResponse(
        path=image_path,
        media_type="image/jpeg",
        filename=image_path.name,
    )


@router.get("/product")
async def get_product_image(
    filename: str = Query(..., min_length=1),
    user_id: str = Depends(get_current_user_id),
):
    """校验 Authorization 后，返回指定商品图片。"""
    image_path = image_service.get_product_image_path(filename=filename)
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="商品图片文件不存在")

    return FileResponse(
        path=image_path,
        media_type="image/jpeg",
        filename=image_path.name,
    )
