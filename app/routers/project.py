from fastapi import APIRouter, Body, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user_id
from app.services.project_service import project_service

router = APIRouter(prefix="/project", tags=["project"])


@router.get("")
async def check_project_router():
    """项目子路由存活校验。"""
    return {"code": 200}


@router.get("/list")
async def list_visible_projects(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """获取所有可见项目列表。"""
    return await project_service.list_visible_projects(session=session)


@router.get("/rules")
async def list_project_rules(
    project_id: int = Query(..., ge=1),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """根据项目 ID 获取该项目的挑战规则列表。"""
    return await project_service.list_project_rules(
        project_id=project_id,
        session=session,
    )


@router.get("/upload_config")
async def list_project_upload_configs(
    project_id: int = Query(..., ge=1),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """根据项目 ID 获取该项目的上传凭证配置列表。"""
    return await project_service.list_project_upload_configs(
        project_id=project_id,
        session=session,
    )


@router.post("/upload_proof")
async def upload_project_proof(
    season_id: int = Form(..., ge=1),
    project_id: int = Form(..., ge=1),
    project_upload_config_id: int = Form(..., ge=1),
    record_type: str | None = Form(default=None),
    note: str | None = Form(default=None),
    image: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """上传当前用户指定赛季和项目下的运动凭证。"""
    return await project_service.upload_project_proof(
        season_id=season_id,
        project_id=project_id,
        project_upload_config_id=project_upload_config_id,
        record_type=record_type,
        note=note,
        image=image,
        user_id=user_id,
        session=session,
    )


@router.get("/lock_check")
async def check_locked_projects(
    season_id: int = Query(..., ge=1),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """根据赛季 ID 获取当前用户已锁定且有效的项目 ID 列表。"""
    return await project_service.list_locked_project_ids(
        season_id=season_id,
        user_id=user_id,
        session=session,
    )


@router.post("/lock")
async def lock_project(
    season_id: int = Body(..., ge=1),
    project_id: int = Body(..., ge=1),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """锁定当前用户在当前赛季下的项目。"""
    return await project_service.lock_project(
        season_id=season_id,
        project_id=project_id,
        user_id=user_id,
        session=session,
    )


@router.post("/lock_level")
async def lock_project_level(
    season_id: int = Body(..., ge=1),
    project_rule_level_id: int = Body(..., ge=1),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """锁定当前用户在当前赛季下的挑战等级。"""
    return await project_service.lock_project_level(
        season_id=season_id,
        project_rule_level_id=project_rule_level_id,
        user_id=user_id,
        session=session,
    )
