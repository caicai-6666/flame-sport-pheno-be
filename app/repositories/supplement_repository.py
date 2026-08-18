from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.project import Project
from app.models.proof_record import ProofRecord
from app.models.season import Season, SeasonStatus
from app.models.season_supplement_eligibility import SeasonSupplementEligibility
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
        """按凭证 ID 查询当前用户仍开放的结算赛季补传资格。"""
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
            .where(SeasonSupplementEligibility.status == 1)
            .where(ProofRecord.status == 1)
            .where(Project.status == 1)
        )
        if for_update:
            # 提交事务内锁定资格与原凭证，避免同一资格被并发消费两次。
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
        """查询当前用户在结算中赛季仍开放补传资格的有效凭证。"""
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
            .where(SeasonSupplementEligibility.status == 1)
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


supplement_repository = SupplementRepository()
