from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from time import monotonic

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.storage import (
    build_proof_record_image_path,
    convert_proof_record_image_to_webp,
    save_proof_record_image,
)
from app.models.project import Project
from app.models.project_upload_config import ProjectUploadConfig
from app.models.proof_record import ProofRecord, ProofReviewStatus
from app.models.season import Season, SeasonStatus
from app.models.season_user_project import SeasonUserProject
from app.repositories.project_repository import project_repository
from app.repositories.proof_record_repository import proof_record_repository
from app.repositories.season_repository import season_repository
from app.repositories.season_user_repository import season_user_repository
from app.services.project_progress_service import project_progress_service
from app.services.user_write_guard import ensure_user_write_allowed


UPLOAD_CONFIG_CACHE_TTL_SECONDS = 300


class ProofService:
    def __init__(self) -> None:
        self._upload_config_cache: dict[
            int,
            tuple[float, list[dict[str, int | str]]],
        ] = {}

    async def list_project_upload_configs(
        self,
        project_id: int,
        session: AsyncSession,
    ) -> dict[str, list[dict[str, int | str]]]:
        """查询指定项目启用的上传凭证配置，返回顺序按 sort_order 升序排列。"""
        cached_upload_configs = self._get_cached_upload_configs(project_id)
        if cached_upload_configs is not None:
            return {"uploadConfigs": cached_upload_configs}

        upload_configs = await project_repository.list_enabled_upload_configs_by_project_id(
            session=session,
            project_id=project_id,
        )
        upload_config_items = [
            self._build_upload_config_item(upload_config)
            for upload_config in upload_configs
        ]
        self._set_cached_upload_configs(
            project_id=project_id,
            upload_config_items=upload_config_items,
        )
        return {
            "uploadConfigs": upload_config_items,
        }

    def clear_upload_config_cache(self, project_id: int | None = None) -> None:
        """清理上传配置缓存，供后续后台管理修改配置后复用。"""
        if project_id is None:
            self._upload_config_cache.clear()
            return

        self._upload_config_cache.pop(project_id, None)

    async def upload_project_proof(
        self,
        season_id: int,
        project_id: int,
        project_upload_config_id: int,
        record_type: str | None,
        proof_date: date,
        note: str,
        image: UploadFile,
        user_id: str,
        session: AsyncSession,
    ) -> dict[str, str]:
        """上传或更新当前用户指定运动日期的项目凭证。"""
        # 必须先判断保护期，避免拒绝请求仍创建赛季目录或处理上传图片。
        try:
            await ensure_user_write_allowed(session=session)
        except Exception:
            await session.rollback()
            raise
        normalized_record_type = self.normalize_record_type(record_type)
        normalized_note = self.normalize_note(note)
        self.ensure_supported_image_media_type(image)

        season = await season_repository.get_by_id(
            session=session,
            season_id=season_id,
        )
        if season is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="赛季不存在",
            )
        if season.status != SeasonStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="赛季未激活，无法上传凭证",
            )
        self.validate_proof_date(season=season, proof_date=proof_date)

        season_user = await season_user_repository.get_by_season_id_and_user_id(
            session=session,
            season_id=season_id,
            user_id=user_id,
        )
        if season_user is None or season_user.id is None or season_user.level_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="用户尚未正式参与该赛季",
            )

        project_lock = await season_user_repository.get_project_lock(
            session=session,
            season_user_id=season_user.id,
            project_id=project_id,
        )
        if project_lock is None or project_lock.status != 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="用户未锁定该项目",
            )

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

        uploaded_at = datetime.now()
        image_path = build_proof_record_image_path(
            season_id=season_id,
            user_id=user_id,
            project_id=project_id,
            filename=image.filename or "proof",
            timestamp=uploaded_at,
        )
        image_url = self._build_proof_record_image_url(image_path)
        image_bytes = await image.read()
        if not image_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="上传图片不能为空",
            )
        try:
            # Pillow 编码属于 CPU 密集操作，在线程池完成，避免阻塞其他异步请求。
            webp_image_bytes = await run_in_threadpool(
                convert_proof_record_image_to_webp,
                image_bytes,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        old_image_path: Path | None = None
        saved_new_image = False
        try:
            # 锁定赛季用户行，避免并发上传时同时写入同项目同运动日期的凭证。
            locked_season_user = await season_user_repository.lock_by_id(
                session=session,
                season_user_id=season_user.id,
            )
            if locked_season_user is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="用户尚未正式参与该赛季",
                )
            locked_project = await season_user_repository.lock_active_project(
                session=session,
                season_user_id=season_user.id,
                project_id=project_id,
            )
            if locked_project is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="用户未锁定该项目",
                )

            # 保存文件后写数据库；如果数据库失败，会删除本次新文件避免残留。
            save_proof_record_image(path=image_path, content=webp_image_bytes)
            saved_new_image = True
            old_image_path = await self._create_or_update_proof_record_for_date(
                session=session,
                season_user_id=season_user.id,
                project_id=project_id,
                project_upload_config_id=project_upload_config_id,
                image_url=image_url,
                note=normalized_note,
                proof_date=proof_date,
                uploaded_at=uploaded_at,
                season_id=season_id,
                project_lock=locked_project,
            )
            await session.commit()
        except HTTPException:
            await session.rollback()
            if saved_new_image:
                self.remove_file_if_exists(image_path)
            raise
        except Exception:
            await session.rollback()
            if saved_new_image:
                self.remove_file_if_exists(image_path)
            raise

        if old_image_path is not None:
            self.remove_file_if_exists(old_image_path)

        return {
            "created_at": uploaded_at.isoformat(timespec="seconds"),
            "proof_date": proof_date.isoformat(),
        }

    async def list_user_proof_history(
        self,
        user_id: str,
        session: AsyncSession,
    ) -> list[dict[str, str]]:
        """查询当前用户过往赛季历史凭证列表。"""
        history_records = await proof_record_repository.list_user_history(
            session=session,
            user_id=user_id,
        )
        return [
            self.build_proof_record_list_item(
                proof_record=proof_record,
                season=season,
                project=project,
            )
            for proof_record, season, project in history_records
        ]

    async def list_user_current_proofs(
        self,
        user_id: str,
        session: AsyncSession,
    ) -> list[dict[str, str]]:
        """查询当前用户当前赛季凭证列表。"""
        current_season = await season_repository.get_current(session=session)
        if current_season is None or current_season.id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="当前没有激活的赛季",
            )
        current_records = await proof_record_repository.list_user_current(
            session=session,
            user_id=user_id,
            current_season_id=current_season.id,
        )
        return [
            self.build_proof_record_list_item(
                proof_record=proof_record,
                season=season,
                project=project,
                include_note=True,
            )
            for proof_record, season, project in current_records
        ]

    def build_proof_record_list_item(
        self,
        proof_record: ProofRecord,
        season: Season,
        project: Project,
        include_note: bool = False,
    ) -> dict[str, str]:
        """构造当前、历史和补传列表共用的凭证展示字段。"""
        item = {
            "seasonName": season.name,
            "projectName": project.name,
            "reviewStatus": proof_record.review_status,
            "reviewComment": proof_record.review_comment or "",
            "imageName": self._build_display_proof_image_name(
                proof_record.image_url,
            ),
            "imageUrl": self._build_proof_record_image_url_for_response(
                proof_record.id,
            ),
            "proofDate": proof_record.proof_date.isoformat(),
            "createdAt": proof_record.created_at.isoformat(timespec="seconds"),
        }
        if include_note:
            # 当前与补传页面需要回显用户原备注，历史列表保持原有响应契约。
            item["note"] = proof_record.note or ""
        return item

    async def _create_or_update_proof_record_for_date(
        self,
        session: AsyncSession,
        season_user_id: int,
        project_id: int,
        project_upload_config_id: int,
        image_url: str,
        note: str | None,
        proof_date: date,
        uploaded_at: datetime,
        season_id: int,
        project_lock: SeasonUserProject,
    ) -> Path | None:
        """创建或更新同项目同运动日期的唯一有效凭证记录。"""
        proof_record = await proof_record_repository.get_active_record_by_proof_date(
            session=session,
            season_user_id=season_user_id,
            project_id=project_id,
            proof_date=proof_date,
        )
        if proof_record is None:
            await proof_record_repository.create(
                session=session,
                season_user_id=season_user_id,
                project_id=project_id,
                project_upload_config_id=project_upload_config_id,
                image_url=image_url,
                note=note,
                proof_date=proof_date,
                created_at=uploaded_at,
            )
            return None

        return await self.replace_existing_proof_record(
            session=session,
            proof_record=proof_record,
            project_upload_config_id=project_upload_config_id,
            image_url=image_url,
            note=note,
            proof_date=proof_date,
            uploaded_at=uploaded_at,
            season_id=season_id,
            project_lock=project_lock,
        )

    async def replace_existing_proof_record(
        self,
        session: AsyncSession,
        proof_record: ProofRecord,
        project_upload_config_id: int,
        image_url: str,
        note: str | None,
        proof_date: date,
        uploaded_at: datetime,
        season_id: int,
        project_lock: SeasonUserProject,
    ) -> Path | None:
        """用新提交内容原位覆盖凭证，并释放旧版本已经占用的项目进度。"""
        old_image_path = self.resolve_existing_proof_image_path(
            old_image_url=proof_record.image_url,
            new_image_url=image_url,
            season_id=season_id,
        )
        # 重传必须先释放旧记录的实际贡献；终审通过记录也不能遗留旧进度。
        released_increase = proof_record.increase
        proof_record.project_upload_config_id = project_upload_config_id
        proof_record.image_url = image_url
        proof_record.note = note
        proof_record.review_status = ProofReviewStatus.PENDING.value
        proof_record.review_comment = None
        proof_record.progress_delta = Decimal("0.0000")
        proof_record.increase = Decimal("0.0000")
        proof_record.proof_date = proof_date
        proof_record.created_at = uploaded_at
        await session.flush()
        await project_progress_service.release_and_redistribute(
            session=session,
            project_lock=project_lock,
            season_user_id=proof_record.season_user_id,
            project_id=proof_record.project_id,
            released_increase=released_increase,
            excluded_proof_record_ids=[proof_record.id] if proof_record.id else None,
        )
        return old_image_path

    def validate_proof_date(self, season: Season, proof_date: date) -> None:
        """服务端校验用户选择的运动日期，避免绕过前端日期控件。"""
        if proof_date > datetime.now().date():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="凭证日期不能晚于今天",
            )
        if proof_date < season.start_date or proof_date > season.end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="凭证日期必须在赛季期间内",
            )

    def _build_upload_config_item(
        self,
        upload_config: ProjectUploadConfig,
    ) -> dict[str, int | str]:
        """构建前端上传凭证配置项。"""
        return {
            "id": upload_config.id or 0,
            "recordType": upload_config.record_type,
            "uploadHint": upload_config.upload_hint,
            "noteExample": upload_config.note_example or "",
        }

    def _get_cached_upload_configs(
        self,
        project_id: int,
    ) -> list[dict[str, int | str]] | None:
        """读取项目上传配置缓存；缓存过期后交回数据库重新加载。"""
        cached_upload_configs = self._upload_config_cache.get(project_id)
        if cached_upload_configs is None:
            return None

        expires_at, upload_config_items = cached_upload_configs
        if expires_at <= monotonic():
            self._upload_config_cache.pop(project_id, None)
            return None

        # 返回副本，避免调用方意外修改进程内缓存内容。
        return [dict(upload_config_item) for upload_config_item in upload_config_items]

    def _set_cached_upload_configs(
        self,
        project_id: int,
        upload_config_items: list[dict[str, int | str]],
    ) -> None:
        """缓存低频变更的上传配置，减少上传窗口重复打开时的数据库查询。"""
        self._upload_config_cache[project_id] = (
            monotonic() + UPLOAD_CONFIG_CACHE_TTL_SECONDS,
            [dict(upload_config_item) for upload_config_item in upload_config_items],
        )

    def normalize_record_type(self, record_type: str | None) -> str | None:
        """规范化可选凭证类型，仅用于兼容旧前端字段并做一致性校验。"""
        if record_type is None:
            return None

        normalized_record_type = record_type.strip()
        if not normalized_record_type:
            return None
        if len(normalized_record_type) > 64:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="record_type 长度不能超过 64",
            )
        return normalized_record_type

    def normalize_note(self, note: str) -> str:
        """规范化并确保用户提供可供初审解析的运动指标说明。"""
        normalized_note = note.strip()
        if not normalized_note:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="note 不能为空，请填写本次运动指标",
            )

        if len(normalized_note) > 255:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="note 长度不能超过 255",
            )
        return normalized_note

    def ensure_supported_image_media_type(self, image: UploadFile) -> None:
        """校验上传媒体类型；有效内容随后统一重编码为 WebP。"""
        if image.content_type not in {
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/webp",
        }:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="凭证图片仅支持 JPEG、PNG 或 WebP",
            )

    def _build_proof_record_image_url(self, image_path: Path) -> str:
        """构建数据库保存的凭证图片地址，当前只保存完整文件名。"""
        return image_path.name

    def _build_display_proof_image_name(self, image_url: str) -> str:
        """去掉系统生成的凭证文件名前缀，仅返回用户上传文件主名。"""
        filename = Path(image_url).name
        filename_parts = filename.split("-", 3)
        if len(filename_parts) < 4:
            return filename
        return filename_parts[3]

    def _build_proof_record_image_url_for_response(
        self,
        proof_record_id: int | None,
    ) -> str:
        """构建列表项中的受保护凭证图片读取地址。"""
        if proof_record_id is None:
            return ""
        return f"/flame/api/image/proof_record/{proof_record_id}"

    def resolve_existing_proof_image_path(
        self,
        old_image_url: str,
        new_image_url: str,
        season_id: int,
    ) -> Path | None:
        """获取更新前的旧图片路径，用于提交成功后清理旧文件。"""
        if old_image_url == new_image_url:
            return None

        old_image_path = (
            settings.PROOF_RECORD_IMAGE_DIR
            / str(season_id)
            / old_image_url
        )
        try:
            self._ensure_proof_record_image_path_safe(old_image_path)
        except HTTPException:
            return None
        return old_image_path

    def _ensure_proof_record_image_path_safe(self, image_path: Path) -> None:
        """确保凭证图片路径没有逃逸出凭证图片目录。"""
        proof_base_dir = settings.PROOF_RECORD_IMAGE_DIR.resolve()
        resolved_image_path = image_path.resolve()
        if not resolved_image_path.is_relative_to(proof_base_dir):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="凭证图片路径非法",
            )

    def remove_file_if_exists(self, file_path: Path) -> None:
        """删除指定文件；文件不存在时忽略。"""
        try:
            if file_path.is_file():
                file_path.unlink()
        except OSError:
            return


proof_service = ProofService()
