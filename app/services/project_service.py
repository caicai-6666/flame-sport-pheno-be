import base64
import json
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.runtime_env import CurrentSeasonRuntime
from app.models.project import Project
from app.models.project_rule import ProjectRule
from app.repositories.project_repository import project_repository
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

    async def list_locked_project_progress(
        self,
        season_id: int,
        user_id: str,
        session: AsyncSession,
    ) -> list[dict[str, float | int]]:
        """查询用户在指定赛季已锁定项目的完成进度。"""
        season_user = await season_user_repository.get_by_season_id_and_user_id(
            session=session,
            season_id=season_id,
            user_id=user_id,
        )
        if season_user is None or season_user.id is None:
            return []

        locked_projects = await season_user_repository.list_locked_projects_with_progress(
            session=session,
            season_user_id=season_user.id,
        )
        return [
            {
                "project_id": locked_project.project_id,
                # Decimal 用于数据库精确累计；接口返回 JSON number 便于前端展示百分比。
                "completion_progress": float(locked_project.completion_progress),
            }
            for locked_project in locked_projects
        ]

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
            # 锁定等级才代表正式报名；与等级写入同一事务，避免产生无报名时间的正式参与记录。
            season_user.participated_at = datetime.now()
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


project_service = ProjectService()
