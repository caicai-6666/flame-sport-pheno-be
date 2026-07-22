from datetime import datetime

from sqlalchemy import and_, case, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.project import Project
from app.models.project_rule import ProjectRule
from app.models.project_upload_config import (
    MONTH_END_RECORD_TYPE,
    MONTH_START_RECORD_TYPE,
    ProjectUploadConfig,
)
from app.models.proof_record import ProofRecord, ProofReviewStatus
from app.models.season import Season
from app.models.season_user import SeasonUser
from app.models.user import User


class ProofRecordRepository:
    async def list_pending_current_season_for_preliminary_review(
        self,
        session: AsyncSession,
        season_id: int,
        cutoff_at: datetime,
    ) -> list[
        tuple[
            ProofRecord,
            SeasonUser,
            User,
            Project,
            ProjectRule,
            ProjectUploadConfig,
        ]
    ]:
        """查询当前赛季截止审核日之前的待初审凭证及其唯一规则。"""
        result = await session.execute(
            select(
                ProofRecord,
                SeasonUser,
                User,
                Project,
                ProjectRule,
                ProjectUploadConfig,
            )
            .join(SeasonUser, SeasonUser.id == ProofRecord.season_user_id)
            .join(User, User.id == SeasonUser.user_id)
            .join(Project, Project.id == ProofRecord.project_id)
            .join(
                ProjectRule,
                and_(
                    ProjectRule.project_id == ProofRecord.project_id,
                    ProjectRule.level_id == SeasonUser.level_id,
                    ProjectRule.status == 1,
                ),
            )
            .join(
                ProjectUploadConfig,
                ProjectUploadConfig.id == ProofRecord.project_upload_config_id,
            )
            .where(SeasonUser.season_id == season_id)
            .where(SeasonUser.level_id.is_not(None))
            .where(ProofRecord.status == 1)
            .where(ProofRecord.review_status == ProofReviewStatus.PENDING.value)
            .where(ProofRecord.created_at < cutoff_at)
            # 同项目同等级同凭证类型连续请求，最大化复用模型的固定规则前缀；
            # 月初基线必须先处理，保证同批月末记录可读取其审核摘要。
            .order_by(
                Project.id.asc(),
                SeasonUser.level_id.asc(),
                case(
                    (ProjectUploadConfig.record_type == MONTH_START_RECORD_TYPE, 0),
                    (ProjectUploadConfig.record_type == MONTH_END_RECORD_TYPE, 1),
                    else_=2,
                ).asc(),
                ProjectUploadConfig.record_type.asc(),
                ProofRecord.created_at.asc(),
                ProofRecord.id.asc(),
            )
        )
        return list(result.all())

    async def find_month_start_review_comment(
        self,
        session: AsyncSession,
        season_user_id: int,
        project_id: int,
    ) -> str | None:
        """获取同一赛季项目最早通过的月初审核摘要，作为月末结算基线。"""
        result = await session.execute(
            select(ProofRecord.review_comment)
            .join(
                ProjectUploadConfig,
                ProjectUploadConfig.id == ProofRecord.project_upload_config_id,
            )
            .where(ProofRecord.season_user_id == season_user_id)
            .where(ProofRecord.project_id == project_id)
            .where(ProofRecord.status == 1)
            .where(
                ProofRecord.review_status
                == ProofReviewStatus.PRELIMINARY_APPROVED.value
            )
            .where(ProjectUploadConfig.record_type == MONTH_START_RECORD_TYPE)
            .where(ProofRecord.review_comment.is_not(None))
            .order_by(ProofRecord.created_at.asc(), ProofRecord.id.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_preliminary_result_if_pending(
        self,
        session: AsyncSession,
        proof_record_id: int,
        expected_created_at: datetime,
        expected_note: str | None,
        review_status: ProofReviewStatus,
        review_comment: str,
    ) -> bool:
        """仅在用户未重传同一凭证时写回初审结果，避免覆盖新提交内容。"""
        statement = (
            update(ProofRecord)
            .where(ProofRecord.id == proof_record_id)
            .where(ProofRecord.status == 1)
            .where(ProofRecord.review_status == ProofReviewStatus.PENDING.value)
            .where(ProofRecord.created_at == expected_created_at)
            .where(ProofRecord.note == expected_note)
            .values(
                review_status=review_status.value,
                review_comment=review_comment,
            )
        )
        result = await session.execute(statement)
        return bool(result.rowcount)

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
            review_status=ProofReviewStatus.PENDING.value,
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
