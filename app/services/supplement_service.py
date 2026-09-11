from datetime import date, datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.image_segments import validate_image_segments
from app.core.storage import (
    build_proof_record_image_path,
    convert_proof_record_image_to_webp,
    save_proof_record_image,
)
from app.models.proof_record import ProofRecord
from app.models.season import Season
from app.models.season_supplement_eligibility import SupplementEligibilityStatus
from app.repositories.project_repository import project_repository
from app.repositories.season_user_repository import season_user_repository
from app.repositories.supplement_repository import supplement_repository
from app.services.proof_service import proof_service
from app.services.user_write_guard import ensure_user_write_allowed


class SupplementService:
    async def upload_eligible_record(
        self,
        proof_record_id: int,
        season_id: int,
        project_id: int,
        project_upload_config_id: int,
        record_type: str | None,
        proof_date: date,
        note: str,
        image: UploadFile,
        user_id: str,
        session: AsyncSession,
        image_segments: str | None = None,
    ) -> dict[str, str]:
        """原位补交一条当前用户在结算赛季仍具备资格的凭证。"""
        # 补交仍属于客户写入，需服从新激活赛季开始后的统一保护期。
        try:
            await ensure_user_write_allowed(session=session)
        except Exception:
            await session.rollback()
            raise

        normalized_record_type = proof_service.normalize_record_type(record_type)
        normalized_note = proof_service.normalize_note(note)
        proof_service.ensure_supported_image_media_type(image)

        eligible_record = await supplement_repository.get_user_eligible_record(
            session=session,
            user_id=user_id,
            proof_record_id=proof_record_id,
        )
        if eligible_record is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="当前凭证没有可用的补传资格",
            )
        _, proof_record, season, _ = eligible_record
        self._ensure_request_matches_record(
            proof_record=proof_record,
            season=season,
            season_id=season_id,
            project_id=project_id,
            proof_date=proof_date,
        )
        proof_service.validate_proof_date(season=season, proof_date=proof_date)

        upload_config = await project_repository.get_enabled_upload_config_by_id(
            session=session,
            project_id=project_id,
            project_upload_config_id=project_upload_config_id,
        )
        if upload_config is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前项目不支持该上传配置",
            )
        if (
            normalized_record_type is not None
            and normalized_record_type != upload_config.record_type
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="project_upload_config_id 与 record_type 不匹配",
            )

        image_bytes = await image.read()
        if not image_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="上传图片不能为空",
            )
        try:
            webp_image_bytes = await run_in_threadpool(
                convert_proof_record_image_to_webp,
                image_bytes,
            )
            normalized_image_segments = await run_in_threadpool(
                validate_image_segments, image_segments, webp_image_bytes,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        # 与普通上传一致，先校验最终图片定位，再创建目录及落盘。
        uploaded_at = datetime.now()
        image_path = build_proof_record_image_path(
            season_id=season_id,
            user_id=user_id,
            project_id=project_id,
            filename=image.filename or "proof",
            timestamp=uploaded_at,
        )
        old_image_path: Path | None = None
        saved_new_image = False
        try:
            # 再次加锁读取资格；并发覆盖按锁顺序串行，避免图片和凭证字段交叉写入。
            locked_record = await supplement_repository.get_user_eligible_record(
                session=session,
                user_id=user_id,
                proof_record_id=proof_record_id,
                for_update=True,
            )
            if locked_record is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="当前凭证没有可用的补传资格",
                )
            eligibility, locked_proof_record, locked_season, _ = locked_record
            self._ensure_request_matches_record(
                proof_record=locked_proof_record,
                season=locked_season,
                season_id=season_id,
                project_id=project_id,
                proof_date=proof_date,
            )

            locked_season_user = await season_user_repository.lock_by_id(
                session=session,
                season_user_id=eligibility.season_user_id,
            )
            if locked_season_user is None or locked_season_user.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="当前凭证没有可用的补传资格",
                )
            locked_project = await season_user_repository.lock_active_project(
                session=session,
                season_user_id=eligibility.season_user_id,
                project_id=project_id,
            )
            if locked_project is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="用户未锁定该项目",
                )

            save_proof_record_image(path=image_path, content=webp_image_bytes)
            saved_new_image = True
            old_image_path = await proof_service.replace_existing_proof_record(
                session=session,
                proof_record=locked_proof_record,
                project_upload_config_id=project_upload_config_id,
                image_url=image_path.name,
                image_segments=normalized_image_segments,
                note=normalized_note,
                proof_date=proof_date,
                uploaded_at=uploaded_at,
                season_id=season_id,
                project_lock=locked_project,
            )
            # 终审通过前资格始终可重复补传；每次新版本都回到待补交初审，
            # 旧的模型或终审结果会被凭证版本与状态校验丢弃。
            eligibility.status = (
                SupplementEligibilityStatus.PENDING_PRELIMINARY_REVIEW
            )
            await session.flush()
            await session.commit()
        except HTTPException:
            await session.rollback()
            if saved_new_image:
                proof_service.remove_file_if_exists(image_path)
            raise
        except Exception:
            await session.rollback()
            if saved_new_image:
                proof_service.remove_file_if_exists(image_path)
            raise

        if old_image_path is not None:
            proof_service.remove_file_if_exists(old_image_path)

        return {
            "created_at": uploaded_at.isoformat(timespec="seconds"),
            "proof_date": proof_date.isoformat(),
        }

    async def list_user_eligible_records(
        self,
        user_id: str,
        session: AsyncSession,
    ) -> list[dict[str, int | str]]:
        """返回当前用户在结算中赛季可以补传的凭证记录。"""
        eligible_records = await supplement_repository.list_user_eligible_records(
            session=session,
            user_id=user_id,
        )
        return [
            {
                "seasonId": season.id or 0,
                "seasonUserId": eligibility.season_user_id,
                "proofRecordId": proof_record.id or 0,
                **proof_service.build_proof_record_list_item(
                    proof_record=proof_record,
                    season=season,
                    project=project,
                    include_note=True,
                ),
            }
            for eligibility, proof_record, season, project in eligible_records
        ]

    def _ensure_request_matches_record(
        self,
        proof_record: ProofRecord,
        season: Season,
        season_id: int,
        project_id: int,
        proof_date: date,
    ) -> None:
        """补交只能覆盖资格绑定的原记录，不能借资格改写其他日期或项目。"""
        if (
            season.id != season_id
            or proof_record.project_id != project_id
            or proof_record.proof_date != proof_date
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="补传信息与原凭证不一致",
            )


supplement_service = SupplementService()
