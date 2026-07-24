from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_cache import auth_cache
from app.core.config import settings
from app.core.storage import (
    SavedAvatarImage,
    restore_avatar_image,
    save_avatar_image,
)
from app.core.dingtalk import (
    DingTalkAuthenticationError,
    DingTalkConfigurationError,
    DingTalkRequestError,
    dingtalk_client,
)
from app.models.department import Department
from app.models.user import User
from app.repositories.department_repository import department_repository
from app.repositories.user_repository import user_repository


class AuthService:
    async def check_user_profile_completion(
        self,
        user_id: str,
        session: AsyncSession,
    ) -> dict[str, bool | list[str]]:
        """检查当前用户资料是否完整。"""
        user = await user_repository.get_by_id(session=session, user_id=user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在",
            )

        missing_fields: list[str] = []
        # 当前阶段只要求身高字段完整，后续新增必填资料时扩展这里。
        if user.height_cm is None:
            missing_fields.append("height_cm")

        return {
            "is_complete": not missing_fields,
            "height_cm_completed": user.height_cm is not None,
            "missing_fields": missing_fields,
        }

    async def login_with_auth_code(
        self,
        auth_code: str,
        session: AsyncSession,
    ) -> str:
        """按运行模式解析用户，成功后写入认证缓存。"""
        normalized_auth_code = auth_code.strip()
        if not normalized_auth_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="auth_code 不能为空",
            )

        # 开发模式复用既有请求字段和缓存结构，避免为本地联调请求钉钉。
        user_id = (
            normalized_auth_code
            if settings.APP_MODE == "development"
            else await self._resolve_user_id_from_auth_code(
                auth_code=normalized_auth_code,
            )
        )
        user = await user_repository.get_by_id(session=session, user_id=user_id)
        if user is None:
            if settings.APP_MODE == "development":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="开发登录用户不存在",
                )
            try:
                user = await self._initialize_user_from_dingtalk(
                    user_id=user_id,
                    session=session,
                )
            except DingTalkRequestError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="钉钉用户初始化服务暂时不可用，请稍后重试",
                ) from exc
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="钉钉头像处理失败，请稍后重试",
                ) from exc
        self._ensure_user_is_enabled(user)

        # 前端继续使用原 auth_code 作为会话标识，服务端缓存中保存真实用户主键。
        await auth_cache.set(
            auth_code=normalized_auth_code,
            user_id=user.id,
        )
        return normalized_auth_code

    async def _initialize_user_from_dingtalk(
        self,
        user_id: str,
        session: AsyncSession,
    ) -> User:
        """首次登录时同步必要的员工与部门资料，并原子创建本地用户。"""
        saved_avatar: SavedAvatarImage | None = None
        try:
            profile = await dingtalk_client.get_user_profile(user_id)
            # 当前 user 表仅支持一个部门，暂按钉钉返回列表的第一个部门归属。
            department = await dingtalk_client.get_department(
                profile.department_ids[0],
            )

            local_department = await department_repository.get_by_id(
                session=session,
                department_id=department.department_id,
            )
            if local_department is None:
                department_with_same_name = await department_repository.get_by_name(
                    session=session,
                    name=department.name,
                )
                if department_with_same_name is not None:
                    # 本地部门名有唯一约束，不能猜测地复用另一个钉钉部门 ID。
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="钉钉部门名称与本地部门数据冲突",
                    )
                local_department = await department_repository.create(
                    session=session,
                    department=Department(
                        id=department.department_id,
                        name=department.name,
                    ),
                )

            if local_department.status != 1:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="所属部门已停用，无法登录",
                )

            avatar_url: str | None = None
            if profile.avatar_source_url:
                avatar = await dingtalk_client.download_avatar(
                    profile.avatar_source_url,
                )
                saved_avatar = save_avatar_image(
                    user_id=profile.user_id,
                    content=avatar.content,
                )
                avatar_url = saved_avatar.url

            user = await user_repository.create(
                session=session,
                user=User(
                    id=profile.user_id,
                    name=profile.name,
                    department_id=local_department.id,
                    avatar_url=avatar_url,
                ),
            )
            await session.commit()
            return user
        except IntegrityError:
            # 同一员工并发首次登录时，另一请求可能已先完成创建；回读即可复用。
            await session.rollback()
            user = await user_repository.get_by_id(session=session, user_id=user_id)
            if user is not None:
                return user
            self._restore_saved_avatar(saved_avatar)
            raise
        except Exception:
            await session.rollback()
            self._restore_saved_avatar(saved_avatar)
            raise

    def _restore_saved_avatar(self, saved_avatar: SavedAvatarImage | None) -> None:
        """数据库初始化失败时恢复头像文件；恢复失败不掩盖原始登录异常。"""
        if saved_avatar is None:
            return
        try:
            restore_avatar_image(saved_avatar)
        except OSError:
            pass

    def _ensure_user_is_enabled(self, user: User) -> None:
        """停用用户不能通过已存在记录绕过登录控制。"""
        if user.status != 1:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="用户已停用，无法登录",
            )

    async def _resolve_user_id_from_auth_code(self, auth_code: str) -> str:
        """调用钉钉企业内部 H5 免登接口，将授权码解析为用户 ID。"""
        try:
            return await dingtalk_client.get_user_id_by_auth_code(auth_code)
        except DingTalkConfigurationError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="钉钉登录尚未完成服务端配置",
            ) from exc
        except DingTalkAuthenticationError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="钉钉免登授权码无效或已过期",
            ) from exc
        except DingTalkRequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="钉钉登录服务暂时不可用，请稍后重试",
            ) from exc


auth_service = AuthService()
