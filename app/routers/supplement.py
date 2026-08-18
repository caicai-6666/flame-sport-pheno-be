from datetime import date

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user_id
from app.services.supplement_service import supplement_service


router = APIRouter(prefix="/supplement", tags=["supplement"])


@router.post("/upload")
async def upload_supplement_proof(
    proof_record_id: int = Form(..., ge=1),
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
    """补交当前用户在结算中赛季获得资格的原凭证。"""
    return await supplement_service.upload_eligible_record(
        proof_record_id=proof_record_id,
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


@router.get("/records")
async def list_user_supplement_records(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """查询当前用户在结算中赛季可以补传的凭证记录。"""
    return await supplement_service.list_user_eligible_records(
        user_id=user_id,
        session=session,
    )
