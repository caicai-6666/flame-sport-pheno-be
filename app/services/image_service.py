from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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


image_service = ImageService()
