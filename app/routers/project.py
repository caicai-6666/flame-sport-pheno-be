from fastapi import APIRouter, Body, Depends, Query
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


@router.get("/progress")
async def list_locked_project_progress(
    season_id: int = Query(..., ge=1),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """查询当前用户已锁定项目的赛季完成进度。"""
    return await project_service.list_locked_project_progress(
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
