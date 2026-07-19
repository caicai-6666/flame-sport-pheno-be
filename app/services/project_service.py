import base64
import json
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.runtime_env import CurrentSeasonRuntime
from app.core.storage import build_proof_record_image_path
from app.models.project import Project
from app.models.project_rule import ProjectRule
from app.models.project_upload_config import ProjectUploadConfig
from app.repositories.project_repository import project_repository
from app.repositories.proof_record_repository import proof_record_repository
from app.repositories.season_repository import season_repository
from app.repositories.season_user_repository import season_user_repository


class ProjectService:
    async def list_visible_projects(
        self,
        session: AsyncSession,
    ) -> list[dict[str, int | str]]:
        """查询可见项目，并将项目图标转换为 base64 字符串。"""
        projects = await project_repository.list_visible(session=session)
        return [self._build_project_item(project) for project in projects]

    async def list_project_rules(
        self,
        project_id: int,
        session: AsyncSession,
    ) -> list[dict[str, int | str | list[dict[str, str]]]]:
        """查询指定项目的启用挑战规则，并返回挑战等级奖励积分供前端排序。"""
        rules = await project_repository.list_visible_rules_by_project_id(
            session=session,
            project_id=project_id,
        )
        return [
            {
                "project_rule_level_id": level.id or 0,
                "name": level.name,
                "reward": level.reward,
                "sub_desc": rule.sub_desc or "",
                "rule_content": self._parse_rule_content(rule),
                "rule_note": rule.rule_note or "",
            }
            for rule, level in rules
        ]

    async def list_project_upload_configs(
        self,
        project_id: int,
        session: AsyncSession,
    ) -> dict[str, list[dict[str, int | str]]]:
        """查询指定项目启用的上传凭证配置，返回顺序按 sort_order 升序排列。"""
        upload_configs = await project_repository.list_enabled_upload_configs_by_project_id(
            session=session,
            project_id=project_id,
        )
        return {
            "uploadConfigs": [
                self._build_upload_config_item(upload_config)
                for upload_config in upload_configs
            ]
        }

    async def list_locked_project_ids(
        self,
        season_id: int,
        user_id: str,
        session: AsyncSession,
    ) -> list[int]:
        """查询用户在指定赛季已锁定且有效的项目 ID。"""
        season_user = await season_user_repository.get_by_season_id_and_user_id(
            session=session,
            season_id=season_id,
            user_id=user_id,
        )
        if season_user is None or season_user.id is None:
            return []

        return await season_user_repository.list_locked_project_ids(
            session=session,
            season_user_id=season_user.id,
        )

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

    async def lock_project(
        self,
        season_id: int,
        project_id: int,
        user_id: str,
        session: AsyncSession,
    ) -> dict[str, int]:
        """锁定当前用户在当前赛季下的项目。"""
        await self._ensure_current_season_runtime_initialized(session=session)
        if CurrentSeasonRuntime.season_id != season_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请求赛季不是当前激活赛季",
            )

        project = await project_repository.get_visible_by_id(
            session=session,
            project_id=project_id,
        )
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在或不可见",
            )

        try:
            season_user = await season_user_repository.get_by_season_id_and_user_id(
                session=session,
                season_id=season_id,
                user_id=user_id,
            )
            if season_user is None:
                season_user = await season_user_repository.create(
                    session=session,
                    season_id=season_id,
                    user_id=user_id,
                )

            if season_user.id is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="赛季用户记录创建失败",
                )

            project_lock = await season_user_repository.get_project_lock(
                session=session,
                season_user_id=season_user.id,
                project_id=project_id,
            )
            if project_lock is not None and project_lock.status == 1:
                return {"code": 200}

            locked_project_count = await season_user_repository.count_locked_projects(
                session=session,
                season_user_id=season_user.id,
            )
            required_project_count = CurrentSeasonRuntime.required_project_count or 0
            if locked_project_count + 1 > required_project_count:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"当前赛季最多只能锁定 {required_project_count} 个项目",
                )

            if project_lock is None:
                await season_user_repository.create_project_lock(
                    session=session,
                    season_user_id=season_user.id,
                    project_id=project_id,
                )
            else:
                project_lock.status = 1
                await session.flush()

            season_user.status = locked_project_count + 1
            await session.commit()
            return {"code": 200}
        except HTTPException:
            await session.rollback()
            raise
        except Exception:
            await session.rollback()
            raise

    async def lock_project_level(
        self,
        season_id: int,
        project_rule_level_id: int,
        user_id: str,
        session: AsyncSession,
    ) -> dict[str, int]:
        """锁定当前用户在当前赛季下的挑战等级。"""
        await self._ensure_current_season_runtime_initialized(session=session)
        if CurrentSeasonRuntime.season_id != season_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请求赛季不是当前激活赛季",
            )

        project_level = await project_repository.get_visible_level_by_id(
            session=session,
            project_rule_level_id=project_rule_level_id,
        )
        if project_level is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="挑战等级不存在或不可用",
            )

        try:
            season_user = await season_user_repository.get_by_season_id_and_user_id(
                session=session,
                season_id=season_id,
                user_id=user_id,
            )
            required_project_count = CurrentSeasonRuntime.required_project_count or 0
            if season_user is None or season_user.id is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="尚未完成当前赛季项目锁定",
                )

            if season_user.status != required_project_count:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"需要先锁定 {required_project_count} 个项目",
                )

            if season_user.level_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="当前赛季挑战等级已锁定",
                )

            season_user.level_id = project_rule_level_id
            await session.commit()
            return {"code": 200}
        except HTTPException:
            await session.rollback()
            raise
        except Exception:
            await session.rollback()
            raise

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

    def _build_project_item(self, project: Project) -> dict[str, int | str]:
        """构建前端项目列表项。"""
        return {
            "project_id": project.id or 0,
            "name": project.name,
            "description": project.description or "",
            "image": self._read_project_icon_as_base64(project),
        }

    def _read_project_icon_as_base64(self, project: Project) -> str:
        """读取项目图标文件并转换为 base64 字符串。"""
        if not project.icon_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"项目 {project.name} 未配置图标",
            )

        icon_path = self._resolve_project_icon_path(project.icon_url)
        if not icon_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"项目 {project.name} 的图标文件不存在",
            )

        return base64.b64encode(icon_path.read_bytes()).decode("utf-8")

    def _resolve_project_icon_path(self, icon_url: str) -> Path:
        """将数据库中的 icon_url 转换为本地项目图标路径。"""
        icon_relative_path = Path(icon_url.strip().lstrip("/\\"))
        if icon_relative_path.parts and icon_relative_path.parts[0] == "project_icon":
            icon_relative_path = Path(*icon_relative_path.parts[1:])

        icon_path = settings.PROJECT_ICON_IMAGE_DIR / icon_relative_path
        self._ensure_project_icon_path_safe(icon_path)
        return icon_path

    def _ensure_project_icon_path_safe(self, icon_path: Path) -> None:
        """确保项目图标路径没有逃逸出项目图标目录。"""
        icon_base_dir = settings.PROJECT_ICON_IMAGE_DIR.resolve()
        resolved_icon_path = icon_path.resolve()
        if not resolved_icon_path.is_relative_to(icon_base_dir):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="项目图标路径非法",
            )

    def _parse_rule_content(self, rule: ProjectRule) -> list[dict[str, str]]:
        """解析并校验项目规则指标内容。"""
        rule_content = rule.rule_content
        if isinstance(rule_content, str):
            try:
                rule_content = json.loads(rule_content)
            except json.JSONDecodeError as exc:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"项目规则 {rule.id} 的 rule_content 不是合法 JSON",
                ) from exc

        if not isinstance(rule_content, list):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"项目规则 {rule.id} 的 rule_content 必须是数组",
            )

        parsed_items: list[dict[str, str]] = []
        for item in rule_content:
            if not isinstance(item, dict):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"项目规则 {rule.id} 的 rule_content 指标项格式错误",
                )

            parsed_items.append(
                {
                    "label": str(item.get("label", "")),
                    "value": str(item.get("value", "")),
                }
            )

        return parsed_items

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


project_service = ProjectService()
