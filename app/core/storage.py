import re
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings


# 首次登录可能拿到高分辨率企业头像，限制本地文件避免排行榜重复加载大图。
AVATAR_JPEG_MAX_BYTES = 300 * 1024
_AVATAR_JPEG_QUALITY_STEPS = (90, 85, 80, 75, 70, 65, 60, 55)
_AVATAR_RESIZE_RATIO = 0.85
_AVATAR_MIN_DIMENSION = 128


@dataclass(frozen=True)
class SavedAvatarImage:
    """本次头像覆盖前的状态，用于数据库事务失败时恢复文件。"""

    path: Path
    previous_content: bytes | None

    @property
    def url(self) -> str:
        """数据库保存的头像相对路径。"""
        return f"/{self.path.name}"


def ensure_asset_directories() -> None:
    """确保项目运行所需的本地资源目录存在。"""
    settings.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    settings.IMAGE_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    settings.AVATAR_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    settings.PROJECT_ICON_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    settings.PRODUCT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    settings.PROOF_RECORD_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def build_proof_record_image_path(
    *,
    season_id: int,
    user_id: str,
    project_id: int,
    filename: str,
    timestamp: datetime | int | str,
) -> Path:
    """按凭证图片整理规则构建本地保存路径。"""
    season_dir = ensure_proof_record_season_directory(season_id)
    safe_user_id = _normalize_path_part(user_id)
    safe_timestamp = _normalize_proof_record_timestamp(timestamp)
    safe_filename = _normalize_proof_record_filename(filename)
    return season_dir / f"{safe_user_id}-{project_id}-{safe_timestamp}-{safe_filename}.jpg"


def ensure_proof_record_season_directory(season_id: int) -> Path:
    """确保指定赛季的凭证目录存在，并返回该目录。"""
    season_dir = settings.PROOF_RECORD_IMAGE_DIR / str(season_id)
    season_dir.mkdir(parents=True, exist_ok=True)
    return season_dir


def save_avatar_image(
    *,
    user_id: str,
    content: bytes,
) -> SavedAvatarImage:
    """将钉钉头像统一转为 JPEG 后按用户 ID 保存，并保留旧文件以支持事务补偿。"""
    if not content:
        raise ValueError("头像图片不能为空")

    settings.AVATAR_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    safe_user_id = _normalize_path_part(user_id)
    image_path = settings.AVATAR_IMAGE_DIR / f"{safe_user_id}.jpg"
    previous_content = image_path.read_bytes() if image_path.is_file() else None
    _write_bytes_atomically(
        path=image_path,
        content=_convert_avatar_to_jpeg(content),
    )
    return SavedAvatarImage(
        path=image_path,
        previous_content=previous_content,
    )


def restore_avatar_image(saved_avatar: SavedAvatarImage) -> None:
    """恢复头像覆盖前的状态，避免失败初始化留下无主文件。"""
    if saved_avatar.previous_content is None:
        saved_avatar.path.unlink(missing_ok=True)
        return
    _write_bytes_atomically(
        path=saved_avatar.path,
        content=saved_avatar.previous_content,
    )


def _write_bytes_atomically(*, path: Path, content: bytes) -> None:
    """先写入同目录临时文件，再原子替换，避免请求中途读到半张头像。"""
    temporary_path = path.parent / f".{path.name}.{uuid4().hex}.tmp"
    try:
        temporary_path.write_bytes(content)
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _convert_avatar_to_jpeg(content: bytes) -> bytes:
    """解码远端图片并重编码为不超过 300 KiB 的标准 JPEG。"""
    try:
        with Image.open(BytesIO(content)) as source_image:
            normalized_image = ImageOps.exif_transpose(source_image).convert("RGB")
            return _encode_avatar_jpeg_with_size_limit(normalized_image)
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError("头像图片无法转换为 JPEG") from exc


def _encode_avatar_jpeg_with_size_limit(image: Image.Image) -> bytes:
    """优先降低 JPEG 质量，必要时缩放尺寸，确保首次初始化不会写入大头像。"""
    current_image = image
    while True:
        for quality in _AVATAR_JPEG_QUALITY_STEPS:
            output = BytesIO()
            current_image.save(
                output,
                format="JPEG",
                quality=quality,
                optimize=True,
                progressive=True,
            )
            encoded_image = output.getvalue()
            if len(encoded_image) <= AVATAR_JPEG_MAX_BYTES:
                return encoded_image

        width, height = current_image.size
        if min(width, height) <= _AVATAR_MIN_DIMENSION:
            # 极端噪点图在最低质量和最小尺寸下仍超限时不能写入，避免突破存储上限。
            raise ValueError("头像图片压缩后仍超过 300 KiB")
        current_image = current_image.resize(
            (
                max(_AVATAR_MIN_DIMENSION, int(width * _AVATAR_RESIZE_RATIO)),
                max(_AVATAR_MIN_DIMENSION, int(height * _AVATAR_RESIZE_RATIO)),
            ),
            Image.Resampling.LANCZOS,
        )


def _normalize_proof_record_timestamp(timestamp: datetime | int | str) -> str:
    """规范化凭证图片时间戳。"""
    if isinstance(timestamp, datetime):
        return timestamp.strftime("%Y%m%d%H%M%S")
    return _normalize_path_part(str(timestamp))


def _normalize_proof_record_filename(filename: str) -> str:
    """规范化上传文件名，只保留安全的文件主名。"""
    filename_stem = Path(filename).stem or "proof"
    return _normalize_path_part(filename_stem)


def _normalize_path_part(value: str) -> str:
    """规范化文件名片段，避免路径穿越和特殊字符影响保存。"""
    normalized_value = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", value.strip())
    return normalized_value.strip("_") or "unknown"
