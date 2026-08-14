from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.media_type import resolve_image_media_type
from app.services.image_service import image_service


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("")
async def check_admin_router():
    """管理端内部接口存活校验。"""
    return {"code": 200, "service": "admin"}


@router.get("/avator")
async def get_admin_avatar(
    avatar_url: str = Query(...),
):
    """根据用户头像地址返回管理端可读取的头像文件。"""
    image_path = image_service.get_avatar_image_path_by_url(
        avatar_url=avatar_url,
    )
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="头像文件不存在")

    return FileResponse(
        path=image_path,
        media_type=resolve_image_media_type(image_path),
        filename=image_path.name,
        # 管理页面可能展示多个用户头像，避免浏览器持久缓存管理数据。
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/project_icon")
async def get_admin_project_icon(
    icon_url: str = Query(...),
):
    """根据项目图标地址返回管理端可读取的图片文件。"""
    image_path = image_service.get_project_icon_image_path(filename=icon_url)
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="项目图标文件不存在")

    return FileResponse(
        path=image_path,
        media_type=resolve_image_media_type(image_path),
        filename=image_path.name,
        headers={"Cache-Control": "private, no-store"},
    )


@router.post("/project_icon", status_code=201)
async def store_admin_project_icon(
    icon_url: str = Form(..., min_length=1, max_length=255),
    image: UploadFile = File(...),
):
    """将管理端上传的项目图标统一转换为 WebP 后保存。"""
    return await image_service.store_project_icon_image(
        icon_url=icon_url,
        image=image,
    )


@router.get("/product")
async def get_admin_product_image(
    image_url: str = Query(...),
):
    """根据奖品图片地址返回管理端可读取的图片文件。"""
    image_path = image_service.get_product_image_path(filename=image_url)
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="奖品图片文件不存在")

    return FileResponse(
        path=image_path,
        media_type=resolve_image_media_type(image_path),
        filename=image_path.name,
        headers={"Cache-Control": "private, no-store"},
    )


@router.post("/product/replace")
async def replace_admin_product_image(
    old_image_url: str | None = Form(default=None, max_length=255),
    new_image_url: str = Form(..., min_length=1, max_length=255),
    image: UploadFile = File(...),
):
    """存储新奖品图片，并用新地址取代旧地址。"""
    return await image_service.replace_product_image(
        old_image_url=old_image_url,
        new_image_url=new_image_url,
        image=image,
    )


@router.get("/proof_record/{proof_record_id}")
async def get_admin_proof_record_image(
    proof_record_id: int,
    session: AsyncSession = Depends(get_session),
):
    """根据凭证记录定位所属赛季并返回图片，不校验用户归属。"""
    image_path = await image_service.get_admin_proof_record_image_path(
        proof_record_id=proof_record_id,
        session=session,
    )
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="凭证图片文件不存在")

    return FileResponse(
        path=image_path,
        media_type=resolve_image_media_type(image_path),
        filename=image_path.name,
        headers={"Cache-Control": "private, no-store"},
    )
