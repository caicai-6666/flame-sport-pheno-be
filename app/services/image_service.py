from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.proof_record_repository import proof_record_repository
from app.repositories.user_repository import user_repository


class ImageService:
    async def get_avatar_image_path(
        self,
        user_id: str,
        session: AsyncSession,
    ) -> Path:
        """根据用户 ID 查询头像地址，并转换为本地头像文件路径。"""
        user = await user_repository.get_by_id(session=session, user_id=user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在",
            )

        if not user.avatar_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户未配置头像",
            )

        avatar_filename = user.avatar_url.strip().lstrip("/\\")
        avatar_path = settings.AVATAR_IMAGE_DIR / avatar_filename
        self._ensure_avatar_path_safe(avatar_path)
        return avatar_path

    def get_product_image_path(self, filename: str) -> Path:
        """根据前端传入的商品图片路径，转换为本地商品图片路径。"""
        if not filename or not filename.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="商品图片路径不能为空",
            )

        # 数据库当前可能保存 /xxx.jpg，这里去掉前导斜杠后再拼接商品图片目录。
        product_filename = filename.strip().lstrip("/\\")
        product_path = settings.PRODUCT_IMAGE_DIR / product_filename
        self._ensure_product_path_safe(product_path)
        return product_path

    def get_project_icon_image_path(self, filename: str) -> Path:
        """将项目图标相对地址转换为本地文件路径。"""
        if not filename or not filename.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="项目图标路径不能为空",
            )

        icon_relative_path = Path(filename.strip().lstrip("/\\"))
        # 兼容历史地址 /project_icon/xxx.png，统一以图标目录为根。
        if icon_relative_path.parts and icon_relative_path.parts[0] == "project_icon":
            icon_relative_path = Path(*icon_relative_path.parts[1:])
        icon_path = settings.PROJECT_ICON_IMAGE_DIR / icon_relative_path
        self._ensure_project_icon_path_safe(icon_path)
        return icon_path

    async def get_proof_record_image_path(
        self,
        proof_record_id: int,
        user_id: str,
        session: AsyncSession,
    ) -> Path:
        """返回当前用户本人有效凭证的本地图片路径。"""
        proof_record_with_season = (
            await proof_record_repository.get_active_user_record_with_season(
                session=session,
                proof_record_id=proof_record_id,
                user_id=user_id,
            )
        )
        if proof_record_with_season is None:
            # 凭证读取按归属过滤，避免通过 ID 枚举其他用户的上传图片。
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="凭证不存在",
            )

        proof_record, season = proof_record_with_season
        proof_image_path = (
            settings.PROOF_RECORD_IMAGE_DIR
            / str(season.id)
            / proof_record.image_url
        )
        self._ensure_proof_record_path_safe(proof_image_path)
        return proof_image_path

    def _ensure_avatar_path_safe(self, avatar_path: Path) -> None:
        """确保头像路径没有逃逸出头像存储目录。"""
        avatar_base_dir = settings.AVATAR_IMAGE_DIR.resolve()
        resolved_avatar_path = avatar_path.resolve()
        if not resolved_avatar_path.is_relative_to(avatar_base_dir):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="头像路径非法",
            )

    def _ensure_product_path_safe(self, product_path: Path) -> None:
        """确保商品图片路径没有逃逸出商品图片目录。"""
        product_base_dir = settings.PRODUCT_IMAGE_DIR.resolve()
        resolved_product_path = product_path.resolve()
        if not resolved_product_path.is_relative_to(product_base_dir):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="商品图片路径非法",
            )

    def _ensure_project_icon_path_safe(self, icon_path: Path) -> None:
        """确保项目图标路径没有逃逸出项目图标目录。"""
        icon_base_dir = settings.PROJECT_ICON_IMAGE_DIR.resolve()
        resolved_icon_path = icon_path.resolve()
        if not resolved_icon_path.is_relative_to(icon_base_dir):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="项目图标路径非法",
            )

    def _ensure_proof_record_path_safe(self, proof_image_path: Path) -> None:
        """确保凭证图片路径没有逃逸出凭证资源目录。"""
        proof_base_dir = settings.PROOF_RECORD_IMAGE_DIR.resolve()
        resolved_proof_image_path = proof_image_path.resolve()
        if not resolved_proof_image_path.is_relative_to(proof_base_dir):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="凭证图片路径非法",
            )


image_service = ImageService()
