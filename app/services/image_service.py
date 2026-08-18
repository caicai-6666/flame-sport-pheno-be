from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.storage import (
    convert_poster_image_to_webp,
    convert_project_icon_to_webp,
    remove_replaced_product_image,
    save_poster_image,
    save_product_image,
    save_project_icon_image,
)
from app.repositories.proof_record_repository import proof_record_repository
from app.repositories.user_repository import user_repository


PROJECT_ICON_MAX_BYTES = 5 * 1024 * 1024
PRODUCT_IMAGE_MAX_BYTES = 5 * 1024 * 1024
POSTER_IMAGE_MAX_BYTES = 10 * 1024 * 1024
POSTER_IMAGE_FILENAME = "活动规则.webp"
POSTER_SOURCE_MEDIA_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}
PRODUCT_IMAGE_FORMAT_BY_SUFFIX = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
}
PRODUCT_IMAGE_FORMAT_BY_MEDIA_TYPE = {
    "image/jpeg": "JPEG",
    "image/jpg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}


class ImageService:
    def get_poster_image_path(self) -> Path:
        """返回固定活动海报路径，调用方不能通过请求参数选择其他资源。"""
        poster_path = settings.POSTER_IMAGE_DIR / POSTER_IMAGE_FILENAME
        poster_base_dir = settings.POSTER_IMAGE_DIR.resolve()
        if not poster_path.resolve().is_relative_to(poster_base_dir):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="活动海报路径非法",
            )
        return poster_path

    async def replace_poster_image(
        self,
        image: UploadFile,
    ) -> dict[str, int | str]:
        """将管理端上传图片转换为 WebP，并原子覆盖唯一活动海报。"""
        if image.content_type not in POSTER_SOURCE_MEDIA_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="活动海报仅支持 JPEG、PNG 或 WebP",
            )

        content = await image.read(POSTER_IMAGE_MAX_BYTES + 1)
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="活动海报不能为空",
            )
        if len(content) > POSTER_IMAGE_MAX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="活动海报不能超过 10 MiB",
            )

        try:
            encoded_image = await run_in_threadpool(
                convert_poster_image_to_webp,
                content,
            )
            save_poster_image(
                path=self.get_poster_image_path(),
                content=encoded_image,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        return {
            "image_url": f"/{POSTER_IMAGE_FILENAME}",
            "size_bytes": len(encoded_image),
        }

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

        return self.get_avatar_image_path_by_url(avatar_url=user.avatar_url)

    def get_avatar_image_path_by_url(self, avatar_url: str) -> Path:
        """将数据库风格的头像地址转换为安全的本地文件路径。"""
        if not avatar_url or not avatar_url.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="头像地址不能为空",
            )

        # 头像统一保存 /xxx.webp；这里仍按通用安全路径规则解析数据库地址。
        avatar_filename = avatar_url.strip().lstrip("/\\")
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

        # 数据库保存 /xxx.webp 等相对地址，这里去掉前导斜杠后再拼接商品图片目录。
        product_filename = filename.strip().lstrip("/\\")
        product_path = settings.PRODUCT_IMAGE_DIR / product_filename
        self._ensure_product_path_safe(product_path)
        return product_path

    async def replace_product_image(
        self,
        old_image_url: str | None,
        new_image_url: str,
        image: UploadFile,
    ) -> dict[str, bool | int | str]:
        """原子存储新奖品图片后清理旧文件，兼容首次新建。"""
        new_image_path = self.get_product_image_path(filename=new_image_url)
        expected_format = PRODUCT_IMAGE_FORMAT_BY_SUFFIX.get(
            new_image_path.suffix.lower()
        )
        if expected_format is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="奖品图片地址仅支持 .jpg、.jpeg、.png 或 .webp",
            )

        normalized_old_image_url = (old_image_url or "").strip()
        old_image_path = (
            self.get_product_image_path(filename=normalized_old_image_url)
            if normalized_old_image_url
            else None
        )

        media_type_format = PRODUCT_IMAGE_FORMAT_BY_MEDIA_TYPE.get(
            image.content_type or ""
        )
        if media_type_format is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="奖品图片仅支持 JPEG、PNG 或 WebP",
            )
        if media_type_format != expected_format:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="奖品图片地址后缀与媒体类型不匹配",
            )

        content = await image.read(PRODUCT_IMAGE_MAX_BYTES + 1)
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="奖品图片不能为空",
            )
        if len(content) > PRODUCT_IMAGE_MAX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="奖品图片不能超过 5 MiB",
            )
        self._validate_product_image_content(
            content=content,
            expected_format=expected_format,
        )

        try:
            # 先原子写入新图，之后才删除旧图，避免上传失败造成资源丢失。
            save_product_image(path=new_image_path, content=content)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        old_image_removed = False
        if old_image_path is not None:
            old_image_removed = remove_replaced_product_image(
                old_path=old_image_path,
                new_path=new_image_path,
            )

        return {
            "image_url": self._build_product_image_url(new_image_path),
            "size_bytes": len(content),
            "old_image_removed": old_image_removed,
        }

    def get_project_icon_image_path(self, filename: str) -> Path:
        """将项目图标相对地址转换为本地文件路径。"""
        if not filename or not filename.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="项目图标路径不能为空",
            )

        icon_relative_path = Path(filename.strip().lstrip("/\\"))
        # 兼容历史 /project_icon/xxx.webp 路径前缀，统一以图标目录为根。
        if icon_relative_path.parts and icon_relative_path.parts[0] == "project_icon":
            icon_relative_path = Path(*icon_relative_path.parts[1:])
        icon_path = settings.PROJECT_ICON_IMAGE_DIR / icon_relative_path
        self._ensure_project_icon_path_safe(icon_path)
        return icon_path

    async def store_project_icon_image(
        self,
        icon_url: str,
        image: UploadFile,
    ) -> dict[str, int | str]:
        """校验上传图标并按指定相对地址统一保存为 WebP。"""
        image_path = self.get_project_icon_image_path(filename=icon_url)
        if image_path.suffix.lower() != ".webp":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="项目图标存储地址必须以 .webp 结尾",
            )
        if image.content_type not in {
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/webp",
        }:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="项目图标仅支持 JPEG、PNG 或 WebP",
            )

        # 多读 1 字节即可识别超限，避免先将过大文件全部读入内存。
        content = await image.read(PROJECT_ICON_MAX_BYTES + 1)
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="项目图标不能为空",
            )
        if len(content) > PROJECT_ICON_MAX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="项目图标不能超过 5 MiB",
            )

        try:
            encoded_image = await run_in_threadpool(
                convert_project_icon_to_webp,
                content,
            )
            save_project_icon_image(path=image_path, content=encoded_image)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        normalized_icon_url = image_path.relative_to(
            settings.PROJECT_ICON_IMAGE_DIR.resolve()
        ).as_posix()
        return {
            "icon_url": f"/{normalized_icon_url}",
            "size_bytes": len(encoded_image),
        }

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
        return self._build_proof_record_image_path(
            season_id=season.id,
            image_url=proof_record.image_url,
        )

    async def get_admin_proof_record_image_path(
        self,
        proof_record_id: int,
        session: AsyncSession,
    ) -> Path:
        """返回管理端按记录 ID 查询到的有效凭证图片路径。"""
        proof_record_with_season = (
            await proof_record_repository.get_active_record_with_season(
                session=session,
                proof_record_id=proof_record_id,
            )
        )
        if proof_record_with_season is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="凭证不存在",
            )

        proof_record, season = proof_record_with_season
        return self._build_proof_record_image_path(
            season_id=season.id,
            image_url=proof_record.image_url,
        )

    def _build_proof_record_image_path(
        self,
        season_id: int | None,
        image_url: str,
    ) -> Path:
        """根据凭证关联赛季构建并校验本地图片路径。"""
        if season_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="凭证所属赛季不存在",
            )

        proof_image_path = (
            settings.PROOF_RECORD_IMAGE_DIR
            / str(season_id)
            / image_url
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

    def _build_product_image_url(self, image_path: Path) -> str:
        """将奖品图片本地路径转换为数据库使用的相对地址。"""
        relative_path = image_path.relative_to(
            settings.PRODUCT_IMAGE_DIR.resolve()
        ).as_posix()
        return f"/{relative_path}"

    def _validate_product_image_content(
        self,
        content: bytes,
        expected_format: str,
    ) -> None:
        """校验奖品图片可解码，且实际格式与地址后缀一致。"""
        try:
            with Image.open(BytesIO(content)) as source_image:
                if source_image.format != expected_format:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="奖品图片实际格式与存储地址不匹配",
                    )
                source_image.verify()
        except HTTPException:
            raise
        except (
            Image.DecompressionBombError,
            OSError,
            UnidentifiedImageError,
        ) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="上传内容不是有效的奖品图片",
            ) from exc

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
