from datetime import datetime, timedelta
from pathlib import Path
from time import monotonic

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.runtime_env import CurrentSeasonRuntime
from app.core.storage import build_proof_record_image_path
from app.models.project_upload_config import ProjectUploadConfig
from app.repositories.project_repository import project_repository
from app.repositories.proof_record_repository import proof_record_repository
from app.repositories.season_repository import season_repository
from app.repositories.season_user_repository import season_user_repository


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
        note: str | None,
        image: UploadFile,
        user_id: str,
        session: AsyncSession,
    ) -> dict[str, str]:
        """上传或更新当前用户当天的项目凭证。"""
        normalized_record_type = self._normalize_record_type(record_type)
        normalized_note = self._normalize_note(note)
        await self._ensure_jpg_image(image)

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

        old_image_path: Path | None = None
        saved_new_image = False
        try:
            # 锁定赛季用户行，避免并发上传时同时插入当天重复凭证。
            locked_season_user = await season_user_repository.lock_by_id(
                session=session,
                season_user_id=season_user.id,
            )
            if locked_season_user is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="用户尚未正式参与该赛季",
                )

            # 保存文件后写数据库；如果数据库失败，会删除本次新文件避免残留。
            image_path.write_bytes(image_bytes)
            saved_new_image = True
            old_image_path = await self._create_or_update_today_proof_record(
                session=session,
                season_user_id=season_user.id,
                project_id=project_id,
                project_upload_config_id=project_upload_config_id,
                image_url=image_url,
                note=normalized_note,
                uploaded_at=uploaded_at,
                season_id=season_id,
            )
            await session.commit()
        except HTTPException:
            await session.rollback()
            if saved_new_image:
                self._remove_file_if_exists(image_path)
            raise
        except Exception:
            await session.rollback()
            if saved_new_image:
                self._remove_file_if_exists(image_path)
            raise

        if old_image_path is not None:
            self._remove_file_if_exists(old_image_path)

        return {"created_at": uploaded_at.isoformat(timespec="seconds")}

    async def list_user_proof_history(
        self,
        user_id: str,
        session: AsyncSession,
    ) -> list[dict[str, str]]:
        """查询当前用户过往赛季历史凭证列表。"""
        await self._ensure_current_season_runtime_initialized(session=session)
        current_season_id = CurrentSeasonRuntime.season_id or 0
        history_records = await proof_record_repository.list_user_history(
            session=session,
            user_id=user_id,
            excluded_season_id=current_season_id,
        )
        return [
            {
                "seasonName": season.name,
                "projectName": project.name,
                "reviewStatus": proof_record.review_status,
                "reviewComment": proof_record.review_comment or "",
                "imageName": self._build_display_proof_image_name(
                    proof_record.image_url,
                ),
                "createdAt": proof_record.created_at.isoformat(timespec="seconds"),
            }
            for proof_record, season, project in history_records
        ]

    async def list_user_current_proofs(
        self,
        user_id: str,
        session: AsyncSession,
    ) -> list[dict[str, str]]:
        """查询当前用户当前赛季凭证列表。"""
        await self._ensure_current_season_runtime_initialized(session=session)
        current_season_id = CurrentSeasonRuntime.season_id or 0
        current_records = await proof_record_repository.list_user_current(
            session=session,
            user_id=user_id,
            current_season_id=current_season_id,
        )
        return [
            {
                "seasonName": season.name,
                "projectName": project.name,
                "reviewStatus": proof_record.review_status,
                "note": proof_record.note or "",
                "imageName": self._build_display_proof_image_name(
                    proof_record.image_url,
                ),
                "createdAt": proof_record.created_at.isoformat(timespec="seconds"),
            }
            for proof_record, season, project in current_records
        ]

    async def _ensure_current_season_runtime_initialized(
        self,
        session: AsyncSession,
    ) -> None:
        """确保当前赛季运行时缓存已经初始化。"""
        if CurrentSeasonRuntime.is_initialized():
            return

        season = await season_repository.get_current(session=session)
        if season is None or season.id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="当前没有激活的赛季",
            )

        CurrentSeasonRuntime.set(
            season_id=season.id,
            required_project_count=season.required_project_count,
        )

    async def _create_or_update_today_proof_record(
        self,
        session: AsyncSession,
        season_user_id: int,
        project_id: int,
        project_upload_config_id: int,
        image_url: str,
        note: str | None,
        uploaded_at: datetime,
        season_id: int,
    ) -> Path | None:
        """创建或更新当天同项目同上传配置的凭证记录。"""
        day_start = uploaded_at.replace(hour=0, minute=0, second=0, microsecond=0)
        next_day_start = day_start + timedelta(days=1)
        proof_record = await proof_record_repository.get_today_record(
            session=session,
            season_user_id=season_user_id,
            project_id=project_id,
            project_upload_config_id=project_upload_config_id,
            day_start=day_start,
            next_day_start=next_day_start,
        )
        if proof_record is None:
            await proof_record_repository.create(
                session=session,
                season_user_id=season_user_id,
                project_id=project_id,
                project_upload_config_id=project_upload_config_id,
                image_url=image_url,
                note=note,
                created_at=uploaded_at,
            )
            return None

        old_image_path = self._resolve_existing_proof_image_path(
            old_image_url=proof_record.image_url,
            new_image_url=image_url,
            season_id=season_id,
        )
        # 用户当天重复上传时覆盖图片和备注，并重新进入待审核状态。
        proof_record.image_url = image_url
        proof_record.note = note
        proof_record.review_status = "pending"
        proof_record.review_comment = None
        proof_record.created_at = uploaded_at
        await session.flush()
        return old_image_path

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

    def _normalize_record_type(self, record_type: str | None) -> str | None:
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

    def _normalize_note(self, note: str | None) -> str | None:
        """规范化用户备注，空字符串按未填写处理。"""
        if note is None:
            return None

        normalized_note = note.strip()
        if not normalized_note:
            return None

        if len(normalized_note) > 255:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="note 长度不能超过 255",
            )
        return normalized_note

    async def _ensure_jpg_image(self, image: UploadFile) -> None:
        """校验上传文件必须是 JPG 图片。"""
        if image.content_type not in {"image/jpeg", "image/jpg"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="仅支持上传 JPG 图片",
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

    def _resolve_existing_proof_image_path(
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

    def _remove_file_if_exists(self, file_path: Path) -> None:
        """删除指定文件；文件不存在时忽略。"""
        try:
            if file_path.is_file():
                file_path.unlink()
        except OSError:
            return


proof_service = ProofService()
