from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.project import Project
from app.models.project_upload_config import ProjectUploadConfig
from app.models.proof_record import ProofRecord, ProofReviewStatus
from app.models.season import Season, SeasonStatus
from app.models.season_supplement_eligibility import (
    SeasonSupplementEligibility,
    SupplementEligibilityStatus,
)
from app.models.season_user import SeasonUser


class SupplementRepository:
    async def get_user_eligible_record(
        self,
        session: AsyncSession,
        user_id: str,
        proof_record_id: int,
        *,
        for_update: bool = False,
    ) -> tuple[
        SeasonSupplementEligibility,
        ProofRecord,
        Season,
        Project,
    ] | None:
        """按凭证 ID 查询当前用户尚未终审通过的结算赛季补传资格。"""
        statement = (
            select(
                SeasonSupplementEligibility,
                ProofRecord,
                Season,
                Project,
            )
            .join(
                SeasonUser,
                SeasonUser.id == SeasonSupplementEligibility.season_user_id,
            )
            .join(Season, Season.id == SeasonUser.season_id)
            .join(
                ProofRecord,
                and_(
                    ProofRecord.id
                    == SeasonSupplementEligibility.proof_record_id,
                    ProofRecord.season_user_id
                    == SeasonSupplementEligibility.season_user_id,
                ),
            )
            .join(Project, Project.id == ProofRecord.project_id)
            .where(SeasonUser.user_id == user_id)
            .where(Season.status == SeasonStatus.SETTLING)
            .where(SeasonSupplementEligibility.proof_record_id == proof_record_id)
            .where(
                SeasonSupplementEligibility.status
                != SupplementEligibilityStatus.CLOSED
            )
            .where(ProofRecord.status == 1)
            .where(Project.status == 1)
        )
        if for_update:
            # 串行化同一资格的覆盖提交，确保最后成功提交的版本完整落库。
            statement = statement.with_for_update()
        result = await session.execute(statement)
        return result.one_or_none()

    async def list_user_eligible_records(
        self,
        session: AsyncSession,
        user_id: str,
    ) -> list[
        tuple[
            SeasonSupplementEligibility,
            ProofRecord,
            Season,
            Project,
        ]
    ]:
        """查询当前用户在结算中赛季尚未关闭的补传资格。"""
        result = await session.execute(
            select(
                SeasonSupplementEligibility,
                ProofRecord,
                Season,
                Project,
            )
            .join(
                SeasonUser,
                SeasonUser.id == SeasonSupplementEligibility.season_user_id,
            )
            .join(Season, Season.id == SeasonUser.season_id)
            .join(
                ProofRecord,
                and_(
                    ProofRecord.id
                    == SeasonSupplementEligibility.proof_record_id,
                    ProofRecord.season_user_id
                    == SeasonSupplementEligibility.season_user_id,
                ),
            )
            .join(Project, Project.id == ProofRecord.project_id)
            .where(SeasonUser.user_id == user_id)
            .where(Season.status == SeasonStatus.SETTLING)
            .where(
                SeasonSupplementEligibility.status
                != SupplementEligibilityStatus.CLOSED
            )
            .where(ProofRecord.status == 1)
            .where(Project.status == 1)
            .order_by(
                Season.start_date.desc(),
                ProofRecord.proof_date.desc(),
                ProofRecord.created_at.desc(),
                ProofRecord.id.desc(),
            )
        )
        return list(result.all())

    async def get_pending_preliminary_review_record(
        self,
        session: AsyncSession,
        proof_record_id: int,
    ) -> tuple[
        SeasonSupplementEligibility,
        ProofRecord,
        SeasonUser,
        Season,
        Project,
        ProjectUploadConfig,
    ] | None:
        """读取已补交且携带固化上下文的结算凭证，供专用初审入口使用。"""
        result = await session.execute(
            select(
                SeasonSupplementEligibility,
                ProofRecord,
                SeasonUser,
                Season,
                Project,
                ProjectUploadConfig,
            )
            .join(
                SeasonUser,
                SeasonUser.id == SeasonSupplementEligibility.season_user_id,
            )
            .join(Season, Season.id == SeasonUser.season_id)
            .join(
                ProofRecord,
                and_(
                    ProofRecord.id
                    == SeasonSupplementEligibility.proof_record_id,
                    ProofRecord.season_user_id
                    == SeasonSupplementEligibility.season_user_id,
                ),
            )
            .join(Project, Project.id == ProofRecord.project_id)
            .join(
                ProjectUploadConfig,
                ProjectUploadConfig.id == ProofRecord.project_upload_config_id,
            )
            .where(SeasonSupplementEligibility.proof_record_id == proof_record_id)
            .where(
                SeasonSupplementEligibility.status
                == SupplementEligibilityStatus.PENDING_PRELIMINARY_REVIEW
            )
            .where(Season.status == SeasonStatus.SETTLING)
            .where(ProofRecord.status == 1)
            .where(ProofRecord.review_status == ProofReviewStatus.PENDING.value)
            .where(Project.status == 1)
        )
        return result.one_or_none()


supplement_repository = SupplementRepository()
