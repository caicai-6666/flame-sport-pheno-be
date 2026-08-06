from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user_id
from app.services.proof_service import proof_service

router = APIRouter(prefix="/proof", tags=["proof"])


@router.get("")
async def check_proof_router():
    """凭证子路由存活校验。"""
    return {"code": 200}


@router.get("/config")
async def list_project_upload_configs(
    response: Response,
    project_id: int = Query(..., ge=1),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """根据项目 ID 获取该项目的上传凭证配置列表。"""
    # 上传配置不包含用户私有数据，允许浏览器短期缓存，减少弹窗重复打开时的请求。
    response.headers["Cache-Control"] = "private, max-age=300"
    return await proof_service.list_project_upload_configs(
        project_id=project_id,
        session=session,
    )


@router.get("/history")
async def list_proof_history(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """获取当前用户历史凭证列表。"""
    return await proof_service.list_user_proof_history(
        user_id=user_id,
        session=session,
    )


@router.get("/current")
async def list_current_proofs(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """获取当前用户当前赛季凭证列表。"""
    return await proof_service.list_user_current_proofs(
        user_id=user_id,
        session=session,
    )


@router.post("/upload")
async def upload_project_proof(
    season_id: int = Form(..., ge=1),
    project_id: int = Form(..., ge=1),
    project_upload_config_id: int = Form(..., ge=1),
    record_type: str | None = Form(default=None),
    proof_date: date = Form(...),
    note: str = Form(...),
    image: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """上传当前用户指定赛季和项目下的运动凭证。"""
    return await proof_service.upload_project_proof(
        season_id=season_id,
        project_id=project_id,
        project_upload_config_id=project_upload_config_id,
        record_type=record_type,
        proof_date=proof_date,
        note=note,
        image=image,
        user_id=user_id,
        session=session,
    )
