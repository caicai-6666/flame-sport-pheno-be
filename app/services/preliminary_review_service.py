"""当前赛季凭证的 DeepSeek 文本初审编排。"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deepseek_preliminary_review import (
    DeepSeekPreliminaryReviewError,
    PreliminaryReviewRequest,
    PreliminaryReviewResult,
    deepseek_preliminary_review_client,
)
from app.models.project_rule import ProjectRule
from app.models.project_upload_config import (
    MONTH_END_RECORD_TYPE,
    MONTH_START_RECORD_TYPE,
    ProjectUploadConfig,
)
from app.models.proof_record import ProofRecord, ProofReviewStatus
from app.models.season_user import SeasonUser
from app.models.season_user_project import SeasonUserProject
from app.models.user import User
from app.models.project import Project
from app.repositories.proof_record_repository import proof_record_repository
from app.repositories.season_user_repository import season_user_repository


logger = logging.getLogger(__name__)
PROGRESS_PRECISION = Decimal("0.0001")


@dataclass
class PreliminaryReviewSummary:
    """单次批量初审结果，仅用于日志与后续运维观测。"""

    found_count: int = 0
    updated_count: int = 0
    failed_count: int = 0


PendingReviewRow = tuple[
    ProofRecord,
    SeasonUser,
    User,
    Project,
    ProjectRule,
    ProjectUploadConfig,
]


class PreliminaryReviewService:
    async def review_pending_current_season(
        self,
        session: AsyncSession,
        season_id: int,
        cutoff_at: datetime,
    ) -> PreliminaryReviewSummary:
        """审核指定当前赛季在审核日之前仍待审的所有有效凭证。"""
        pending_rows = (
            await proof_record_repository.list_pending_current_season_for_preliminary_review(
                session=session,
                season_id=season_id,
                cutoff_at=cutoff_at,
            )
        )
        # 查询完成即结束事务，不能在调用外部模型期间占用数据库连接或行锁。
        # async_session_factory 使用 expire_on_commit=False；不能使用 rollback，后者会使
        # 已取出的 ORM 对象失效，后续访问属性会在异步上下文触发 MissingGreenlet。
        await session.commit()

        summary = PreliminaryReviewSummary(found_count=len(pending_rows))
        for pending_row in pending_rows:
            proof_record = pending_row[0]
            proof_record_id = proof_record.id
            try:
                review_result = await self._evaluate_row(
                    session=session,
                    pending_row=pending_row,
                )
                applied = await self._persist_result(
                    session=session,
                    pending_row=pending_row,
                    review_result=review_result,
                )
                if applied:
                    summary.updated_count += 1
            except Exception:
                await session.rollback()
                summary.failed_count += 1
                logger.exception(
                    "preliminary review failed: proof_record_id=%s",
                    proof_record_id,
                )
        return summary

    async def _evaluate_row(
        self,
        session: AsyncSession,
        pending_row: PendingReviewRow,
    ) -> PreliminaryReviewResult:
        proof_record, season_user, user, project, rule, upload_config = pending_row
        rule_content = self._parse_rule_content(rule=rule)

        if upload_config.record_type == MONTH_START_RECORD_TYPE and user.height_cm is None:
            return self._build_rejected_result("未填写身高，无法计算BMI。")

        initial_review_comment: str | None = None
        if upload_config.record_type == MONTH_END_RECORD_TYPE:
            initial_review_comment = (
                await proof_record_repository.find_month_start_review_comment(
                    session=session,
                    season_user_id=season_user.id or 0,
                    project_id=proof_record.project_id,
                )
            )
            if not initial_review_comment:
                return self._build_rejected_result("缺少月初记录，无法结算减重结果。")

        request = PreliminaryReviewRequest(
            project_name=project.name,
            record_type=upload_config.record_type,
            rule_content=rule_content,
            rule_note=rule.rule_note or "",
            note=proof_record.note or "",
            # 月末评论已包含 BMI 和目标减重值，无须再次发送身高。
            height_cm=(
                user.height_cm
                if upload_config.record_type == MONTH_START_RECORD_TYPE
                else None
            ),
            initial_review_comment=initial_review_comment,
        )
        # 月末基线查询结束后再访问模型，避免外部等待时占用数据库事务；提交只读事务
        # 可保留当前批次的 ORM 快照，rollback 会让其属性过期。
        await session.commit()
        return await deepseek_preliminary_review_client.evaluate(request=request)

    async def _persist_result(
        self,
        session: AsyncSession,
        pending_row: PendingReviewRow,
        review_result: PreliminaryReviewResult,
    ) -> bool:
        proof_record, season_user, _, _, _, upload_config = pending_row
        if proof_record.id is None or season_user.id is None:
            raise RuntimeError("待初审凭证缺少主键关联")

        # 条件更新同时校验创建时间和 note，用户重传后不会被旧模型结果覆盖。
        updated = await proof_record_repository.update_preliminary_result_if_pending(
            session=session,
            proof_record_id=proof_record.id,
            expected_created_at=proof_record.created_at,
            expected_note=proof_record.note,
            review_status=review_result.review_status,
            review_comment=review_result.review_comment,
        )
        if not updated:
            proof_record_id = proof_record.id
            await session.rollback()
            logger.info(
                "preliminary review discarded after proof retransmission: "
                "proof_record_id=%s",
                proof_record_id,
            )
            return False

        if review_result.review_status == ProofReviewStatus.PRELIMINARY_APPROVED:
            await self._apply_project_progress(
                session=session,
                season_user_id=season_user.id,
                project_id=proof_record.project_id,
                record_type=upload_config.record_type,
                progress_delta=review_result.progress_delta,
            )

        await session.commit()
        return True

    async def _apply_project_progress(
        self,
        session: AsyncSession,
        season_user_id: int,
        project_id: int,
        record_type: str,
        progress_delta: Decimal,
    ) -> None:
        project_lock = await season_user_repository.lock_active_project(
            session=session,
            season_user_id=season_user_id,
            project_id=project_id,
        )
        if project_lock is None:
            raise RuntimeError("初审凭证关联的赛季项目不存在或已失效")

        if record_type == MONTH_START_RECORD_TYPE:
            # 月初只建立 BMI 基线，绝不推进减重项目进度。
            return
        if record_type == MONTH_END_RECORD_TYPE:
            # 月末达标代表本赛季减重挑战完成，不按增量叠加。
            project_lock.completion_progress = Decimal("1.0000")
            await session.flush()
            return

        project_lock.completion_progress = min(
            Decimal("1.0000"),
            (
                project_lock.completion_progress + progress_delta
            ).quantize(PROGRESS_PRECISION, rounding=ROUND_HALF_UP),
        )
        await session.flush()

    def _parse_rule_content(self, rule: ProjectRule) -> list[dict[str, str]]:
        """兼容 MySQL JSON 和历史字符串值，确保模型收到唯一规则的标准结构。"""
        raw_rule_content = rule.rule_content
        if isinstance(raw_rule_content, str):
            try:
                raw_rule_content = json.loads(raw_rule_content)
            except json.JSONDecodeError as exc:
                raise DeepSeekPreliminaryReviewError("项目规则 JSON 非法") from exc
        if not isinstance(raw_rule_content, list):
            raise DeepSeekPreliminaryReviewError("项目规则必须是指标数组")

        parsed_rule_content: list[dict[str, str]] = []
        for item in raw_rule_content:
            if not isinstance(item, dict):
                raise DeepSeekPreliminaryReviewError("项目规则指标格式非法")
            label = item.get("label")
            value = item.get("value")
            if not isinstance(label, str) or not isinstance(value, str):
                raise DeepSeekPreliminaryReviewError("项目规则指标缺少文本 label 或 value")
            parsed_rule_content.append({"label": label, "value": value})
        return parsed_rule_content

    def _build_rejected_result(self, review_comment: str) -> PreliminaryReviewResult:
        return PreliminaryReviewResult(
            review_comment=review_comment,
            review_status=ProofReviewStatus.PRELIMINARY_REJECTED,
            progress_delta=Decimal("0"),
        )


preliminary_review_service = PreliminaryReviewService()
