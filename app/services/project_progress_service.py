"""赛季项目进度的分配、释放与回补。"""

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.project_upload_config import (
    MONTH_END_RECORD_TYPE,
    MONTH_START_RECORD_TYPE,
)
from app.models.season_user_project import SeasonUserProject
from app.repositories.proof_record_repository import proof_record_repository


PROGRESS_PRECISION = Decimal("0.0001")
MIN_PROGRESS = Decimal("0.0000")
MAX_PROGRESS = Decimal("1.0000")


class ProjectProgressService:
    def normalize_progress_delta(
        self,
        record_type: str,
        progress_delta: Decimal,
    ) -> Decimal:
        """按项目特殊规则规范化初审原始增量。"""
        if record_type == MONTH_START_RECORD_TYPE:
            # 月初记录只建立 BMI 基线，不产生项目进度。
            return MIN_PROGRESS
        if record_type == MONTH_END_RECORD_TYPE:
            # 月末达标即完成减重项目，不依赖模型返回的小数值。
            return MAX_PROGRESS
        return min(
            MAX_PROGRESS,
            max(
                MIN_PROGRESS,
                progress_delta.quantize(
                    PROGRESS_PRECISION,
                    rounding=ROUND_HALF_UP,
                ),
            ),
        )

    def allocate_progress(
        self,
        project_lock: SeasonUserProject,
        progress_delta: Decimal,
    ) -> Decimal:
        """从项目剩余空间中分配本条凭证的实际贡献。"""
        remaining = max(
            MIN_PROGRESS,
            (MAX_PROGRESS - project_lock.completion_progress).quantize(
                PROGRESS_PRECISION,
                rounding=ROUND_HALF_UP,
            ),
        )
        increase = min(progress_delta, remaining)
        project_lock.completion_progress = (
            project_lock.completion_progress + increase
        ).quantize(PROGRESS_PRECISION, rounding=ROUND_HALF_UP)
        return increase

    def align_progress_delta_with_completion(
        self,
        project_lock: SeasonUserProject,
        progress_delta: Decimal,
    ) -> Decimal:
        """修正分数拆分的舍入尾差，确保完成进度可精确达到 1。"""
        if progress_delta <= MIN_PROGRESS:
            return progress_delta

        prospective_progress = (
            project_lock.completion_progress + progress_delta
        ).quantize(PROGRESS_PRECISION, rounding=ROUND_HALF_UP)
        remaining = (MAX_PROGRESS - prospective_progress).quantize(
            PROGRESS_PRECISION,
            rounding=ROUND_HALF_UP,
        )
        if (
            MIN_PROGRESS < remaining
            <= settings.PROGRESS_COMPLETION_SNAP_THRESHOLD
        ):
            # 例如三次 1/3 被量化为 0.3333 时，最后一次补足 0.0001，
            # 使项目总进度与各凭证的实际贡献始终可逆。
            return (progress_delta + remaining).quantize(
                PROGRESS_PRECISION,
                rounding=ROUND_HALF_UP,
            )
        return progress_delta

    async def release_and_redistribute(
        self,
        session: AsyncSession,
        project_lock: SeasonUserProject,
        season_user_id: int,
        project_id: int,
        released_increase: Decimal,
        excluded_proof_record_ids: list[int] | None = None,
    ) -> None:
        """释放旧贡献，并按上传顺序回补给尚未完全分配的有效凭证。"""
        released_increase = max(
            MIN_PROGRESS,
            released_increase.quantize(
                PROGRESS_PRECISION,
                rounding=ROUND_HALF_UP,
            ),
        )
        if released_increase == MIN_PROGRESS:
            return

        actual_released = min(
            project_lock.completion_progress,
            released_increase,
        )
        project_lock.completion_progress = (
            project_lock.completion_progress - actual_released
        ).quantize(PROGRESS_PRECISION, rounding=ROUND_HALF_UP)
        remaining_gap = actual_released

        candidates = await proof_record_repository.list_progress_refill_candidates(
            session=session,
            season_user_id=season_user_id,
            project_id=project_id,
            excluded_proof_record_ids=excluded_proof_record_ids,
        )
        for candidate in candidates:
            available = (candidate.progress_delta - candidate.increase).quantize(
                PROGRESS_PRECISION,
                rounding=ROUND_HALF_UP,
            )
            allocated = min(available, remaining_gap)
            candidate.increase = (candidate.increase + allocated).quantize(
                PROGRESS_PRECISION,
                rounding=ROUND_HALF_UP,
            )
            project_lock.completion_progress = (
                project_lock.completion_progress + allocated
            ).quantize(PROGRESS_PRECISION, rounding=ROUND_HALF_UP)
            remaining_gap = (remaining_gap - allocated).quantize(
                PROGRESS_PRECISION,
                rounding=ROUND_HALF_UP,
            )
            if remaining_gap == MIN_PROGRESS:
                break

        await session.flush()


project_progress_service = ProjectProgressService()
