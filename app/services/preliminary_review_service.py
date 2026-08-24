"""当前赛季凭证的 DeepSeek 文本初审编排。"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException, status
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
from app.models.season import SeasonStatus
from app.models.season_user import SeasonUser
from app.models.season_user_project import SeasonUserProject
from app.models.user import User
from app.models.project import Project
from app.repositories.notification_repository import notification_repository
from app.repositories.proof_record_repository import proof_record_repository
from app.repositories.season_user_repository import season_user_repository
from app.services.leaderboard_service import leaderboard_service
from app.services.project_progress_service import project_progress_service


logger = logging.getLogger(__name__)
PRELIMINARY_REJECTION_NOTIFICATION_TITLE = "运动凭证初审结果"
MISSING_REVIEW_COMMENT = "未填写"


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


def build_preliminary_rejection_notification_fields(
    project: Project,
    proof_record: ProofRecord,
    review_comment: str,
) -> list[dict[str, str]]:
    """构造初审失败通知的稳定展示快照，保持消息字段顺序固定。"""
    return [
        {"key": "审核结果", "value": "未通过"},
        {"key": "运动项目", "value": project.name},
        {"key": "凭证日期", "value": proof_record.proof_date.isoformat()},
        {
            "key": "审核意见",
            "value": review_comment or MISSING_REVIEW_COMMENT,
        },
    ]


class PreliminaryReviewService:
    async def review_pending_by_id(
        self,
        session: AsyncSession,
        proof_record_id: int,
    ) -> dict[str, float | int | str]:
        """立即初审非未开始赛季的一条待审凭证，跳过定时等待。"""
        record_with_season = (
            await proof_record_repository.get_active_record_with_season(
                session=session,
                proof_record_id=proof_record_id,
            )
        )
        if record_with_season is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="凭证不存在或已失效",
            )

        proof_record, season = record_with_season
        if season.status == SeasonStatus.NOT_STARTED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="凭证所属赛季尚未开始，不允许初审",
            )
        if proof_record.review_status != ProofReviewStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="凭证当前状态不是待初审",
            )

        pending_row = (
            await proof_record_repository.get_pending_record_for_preliminary_review(
                session=session,
                proof_record_id=proof_record_id,
            )
        )
        if pending_row is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="凭证缺少可用的初审规则或参与信息",
            )

        # 查询完成后释放只读事务，避免等待外部模型时长期占用数据库连接。
        await session.commit()
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
        except DeepSeekPreliminaryReviewError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc
        except Exception:
            await session.rollback()
            raise

        if not applied:
            # 模型调用期间发生重传或其他审核时，条件更新会拒绝覆盖新状态。
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="凭证内容或审核状态已变化，请刷新后重试",
            )

        await session.refresh(proof_record)
        response = {
            "proof_record_id": proof_record_id,
            "review_status": proof_record.review_status,
            "review_comment": proof_record.review_comment or "",
            "progress_delta": float(proof_record.progress_delta),
            "increase": float(proof_record.increase),
        }

        if season.status == SeasonStatus.ACTIVE:
            try:
                # 激活赛季的审核结果应尽快反映到排行榜；刷新失败不回滚已提交的审核。
                await leaderboard_service.refresh_current_season_snapshot(
                    session=session,
                )
            except Exception:
                await session.rollback()
                logger.exception(
                    "leaderboard refresh failed after immediate preliminary review: "
                    "proof_record_id=%s",
                    proof_record_id,
                )

        return response

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
        proof_record, season_user, _, project, _, upload_config = pending_row
        if proof_record.id is None or season_user.id is None:
            raise RuntimeError("待初审凭证缺少主键关联")

        project_lock: SeasonUserProject | None = None
        normalized_progress_delta = Decimal("0.0000")
        if review_result.review_status == ProofReviewStatus.PRELIMINARY_APPROVED:
            normalized_progress_delta = project_progress_service.normalize_progress_delta(
                record_type=upload_config.record_type,
                progress_delta=review_result.progress_delta,
            )
            # 同一赛季项目的通过结果必须串行写入：这样多实例同时初审时，后一条
            # 通过凭证仍会可靠地替换同运动日期旧记录，而不会把进度重复累计。
            project_lock = await season_user_repository.lock_active_project(
                session=session,
                season_user_id=season_user.id,
                project_id=proof_record.project_id,
            )
            if project_lock is None:
                raise RuntimeError("初审凭证关联的赛季项目不存在或已失效")

        # 条件更新同时校验创建时间和 note，用户重传后不会被旧模型结果覆盖。
        updated = await proof_record_repository.update_preliminary_result_if_pending(
            session=session,
            proof_record_id=proof_record.id,
            expected_created_at=proof_record.created_at,
            expected_note=proof_record.note,
            review_status=review_result.review_status,
            review_comment=review_result.review_comment,
            progress_delta=normalized_progress_delta,
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
            if project_lock is None:
                raise RuntimeError("初审凭证缺少项目锁")
            replaced_records = (
                await proof_record_repository.list_same_proof_date_preliminary_approved_records(
                    session=session,
                    season_user_id=season_user.id,
                    project_id=proof_record.project_id,
                    proof_date=proof_record.proof_date,
                    excluded_proof_record_id=proof_record.id,
                )
            )
            if replaced_records:
                # 同项目同运动日期只保留最新版本；旧版本释放的实际贡献优先回补给
                # 更早上传且因封顶未完全分配进度的有效凭证。
                replaced_record_ids = [
                    old_proof_record.id
                    for old_proof_record in replaced_records
                    if old_proof_record.id is not None
                ]
                released_increase = sum(
                    (
                        old_proof_record.increase
                        for old_proof_record in replaced_records
                    ),
                    Decimal("0.0000"),
                )
                await proof_record_repository.deactivate_records(
                    session=session,
                    proof_record_ids=replaced_record_ids,
                )
                await project_progress_service.release_and_redistribute(
                    session=session,
                    project_lock=project_lock,
                    season_user_id=season_user.id,
                    project_id=proof_record.project_id,
                    released_increase=released_increase,
                    excluded_proof_record_ids=[
                        *replaced_record_ids,
                        proof_record.id,
                    ],
                )
            # 重传会先释放旧版本贡献，必须以释放后的实际剩余空间判断舍入尾差。
            normalized_progress_delta = (
                project_progress_service.align_progress_delta_with_completion(
                    project_lock=project_lock,
                    progress_delta=normalized_progress_delta,
                )
            )
            applied_increase = project_progress_service.allocate_progress(
                project_lock=project_lock,
                progress_delta=normalized_progress_delta,
            )
            await session.flush()
            stored_increase = (
                await proof_record_repository.set_increase_if_preliminary_approved(
                    session=session,
                    proof_record_id=proof_record.id,
                    expected_created_at=proof_record.created_at,
                    expected_note=proof_record.note,
                    increase=applied_increase,
                    progress_delta=normalized_progress_delta,
                )
            )
            if not stored_increase:
                raise RuntimeError("初审凭证实际进度贡献写入失败")

        if review_result.review_status == ProofReviewStatus.PRELIMINARY_REJECTED:
            # 通知与初审结论原子提交；过期结果被条件更新丢弃时不会产生通知。
            await notification_repository.create_pending(
                session=session,
                user_id=season_user.user_id,
                message_title=PRELIMINARY_REJECTION_NOTIFICATION_TITLE,
                message_fields=build_preliminary_rejection_notification_fields(
                    project=project,
                    proof_record=proof_record,
                    review_comment=review_result.review_comment,
                ),
            )

        await session.commit()
        return True

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
