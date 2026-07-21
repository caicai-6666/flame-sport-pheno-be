from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.project import Project
from app.models.proof_record import ProofRecord
from app.models.season import Season
from app.models.season_user import SeasonUser


class ProofRecordRepository:
    async def get_today_record(
        self,
        session: AsyncSession,
        season_user_id: int,
        project_id: int,
        project_upload_config_id: int,
        day_start: datetime,
        next_day_start: datetime,
    ) -> ProofRecord | None:
        """查询用户当天同项目同上传配置的有效凭证记录。"""
        result = await session.execute(
            select(ProofRecord)
            .where(ProofRecord.season_user_id == season_user_id)
            .where(ProofRecord.project_id == project_id)
            .where(ProofRecord.project_upload_config_id == project_upload_config_id)
            .where(ProofRecord.status == 1)
            .where(ProofRecord.created_at >= day_start)
            .where(ProofRecord.created_at < next_day_start)
            .order_by(ProofRecord.created_at.desc(), ProofRecord.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        session: AsyncSession,
        season_user_id: int,
        project_id: int,
        project_upload_config_id: int,
        image_url: str,
        note: str | None,
        created_at: datetime,
    ) -> ProofRecord:
        """创建凭证记录。"""
        proof_record = ProofRecord(
            season_user_id=season_user_id,
            project_id=project_id,
            project_upload_config_id=project_upload_config_id,
            image_url=image_url,
            note=note,
            review_status="pending",
            review_comment=None,
            status=1,
            created_at=created_at,
        )
        session.add(proof_record)
        await session.flush()
        return proof_record

    async def list_user_history(
        self,
        session: AsyncSession,
        user_id: str,
        excluded_season_id: int,
    ) -> list[tuple[ProofRecord, Season, Project]]:
        """查询用户过往赛季有效历史凭证，并附带赛季和项目信息。"""
        result = await session.execute(
            select(ProofRecord, Season, Project)
            .join(SeasonUser, SeasonUser.id == ProofRecord.season_user_id)
            .join(Season, Season.id == SeasonUser.season_id)
            .join(Project, Project.id == ProofRecord.project_id)
            .where(SeasonUser.user_id == user_id)
            .where(SeasonUser.season_id != excluded_season_id)
            .where(ProofRecord.status == 1)
            .order_by(ProofRecord.created_at.desc(), ProofRecord.id.desc())
        )
        return list(result.all())

    async def list_user_current(
        self,
        session: AsyncSession,
        user_id: str,
        current_season_id: int,
    ) -> list[tuple[ProofRecord, Season, Project]]:
        """查询用户当前赛季有效凭证，并附带赛季和项目信息。"""
        result = await session.execute(
            select(ProofRecord, Season, Project)
            .join(SeasonUser, SeasonUser.id == ProofRecord.season_user_id)
            .join(Season, Season.id == SeasonUser.season_id)
            .join(Project, Project.id == ProofRecord.project_id)
            .where(SeasonUser.user_id == user_id)
            .where(SeasonUser.season_id == current_season_id)
            .where(ProofRecord.status == 1)
            .order_by(ProofRecord.created_at.desc(), ProofRecord.id.desc())
        )
        return list(result.all())


proof_record_repository = ProofRecordRepository()
