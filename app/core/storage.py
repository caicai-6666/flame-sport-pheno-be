import re
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings


# 首次登录可能拿到高分辨率企业头像，限制本地文件避免排行榜重复加载大图。
AVATAR_WEBP_MAX_BYTES = 300 * 1024
_AVATAR_WEBP_QUALITY_STEPS = (90, 85, 80, 75, 70, 65, 60, 55)
_AVATAR_RESIZE_RATIO = 0.85
_AVATAR_MIN_DIMENSION = 128
_AVATAR_SOURCE_FORMATS = {"JPEG", "PNG", "WEBP"}
PROJECT_ICON_MAX_EDGE = 1600
PROJECT_ICON_SOURCE_FORMATS = {"JPEG", "PNG", "WEBP"}
PROOF_RECORD_WEBP_QUALITY = 82
PROOF_RECORD_SOURCE_FORMATS = {"JPEG", "PNG", "WEBP"}
POSTER_WEBP_QUALITY = 90
POSTER_SOURCE_FORMATS = {"JPEG", "PNG", "WEBP"}


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
    settings.POSTER_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


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
    return season_dir / (
        f"{safe_user_id}-{project_id}-{safe_timestamp}-{safe_filename}.webp"
    )


def ensure_proof_record_season_directory(season_id: int) -> Path:
    """确保指定赛季的凭证目录存在，并返回该目录。"""
    season_dir = settings.PROOF_RECORD_IMAGE_DIR / str(season_id)
    season_dir.mkdir(parents=True, exist_ok=True)
    return season_dir


def convert_proof_record_image_to_webp(content: bytes) -> bytes:
    """解码常见上传图片并统一重编码为 WebP，避免信任客户端文件后缀。"""
    if not content:
        raise ValueError("凭证图片不能为空")

    try:
        with Image.open(BytesIO(content)) as source_image:
            if source_image.format not in PROOF_RECORD_SOURCE_FORMATS:
                raise ValueError("凭证图片仅支持 JPEG、PNG 或 WebP")
            normalized_image = ImageOps.exif_transpose(source_image)
            has_transparency = (
                "A" in normalized_image.getbands()
                or "transparency" in normalized_image.info
            )
            output_image = normalized_image.convert(
                "RGBA" if has_transparency else "RGB"
            )
            output = BytesIO()
            output_image.save(
                output,
                format="WEBP",
                quality=PROOF_RECORD_WEBP_QUALITY,
                method=6,
                alpha_quality=100,
            )
            encoded_image = output.getvalue()

        # 重新解码编码结果，确保不会将损坏文件写入凭证目录。
        with Image.open(BytesIO(encoded_image)) as verified_image:
            verified_image.verify()
            if verified_image.format != "WEBP":
                raise ValueError("凭证图片转换为 WebP 失败")
        return encoded_image
    except ValueError:
        raise
    except (
        Image.DecompressionBombError,
        OSError,
        UnidentifiedImageError,
    ) as exc:
        raise ValueError("上传内容不是有效的凭证图片") from exc


def save_proof_record_image(*, path: Path, content: bytes) -> None:
    """将已转换的 WebP 凭证图片原子写入凭证资源目录。"""
    proof_record_base_dir = settings.PROOF_RECORD_IMAGE_DIR.resolve()
    resolved_path = path.resolve()
    if not resolved_path.is_relative_to(proof_record_base_dir):
        raise ValueError("凭证图片路径非法")
    if resolved_path.suffix.lower() != ".webp":
        raise ValueError("凭证图片存储地址必须以 .webp 结尾")

    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    _write_bytes_atomically(path=resolved_path, content=content)


def save_avatar_image(
    *,
    user_id: str,
    content: bytes,
) -> SavedAvatarImage:
    """将钉钉头像统一转为 WebP 后按用户 ID 保存，并保留旧文件用于补偿。"""
    if not content:
        raise ValueError("头像图片不能为空")

    settings.AVATAR_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    safe_user_id = _normalize_path_part(user_id)
    image_path = settings.AVATAR_IMAGE_DIR / f"{safe_user_id}.webp"
    previous_content = image_path.read_bytes() if image_path.is_file() else None
    _write_bytes_atomically(
        path=image_path,
        content=convert_avatar_to_webp(content),
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


def convert_project_icon_to_webp(content: bytes) -> bytes:
    """将常见项目图标无损转换为 WebP，并限制解码后的像素尺寸。"""
    if not content:
        raise ValueError("项目图标不能为空")

    try:
        with Image.open(BytesIO(content)) as source_image:
            if source_image.format not in PROJECT_ICON_SOURCE_FORMATS:
                raise ValueError("项目图标仅支持 JPEG、PNG 或 WebP")
            normalized_image = ImageOps.exif_transpose(source_image)
            if max(normalized_image.size) > PROJECT_ICON_MAX_EDGE:
                raise ValueError("项目图标最长边不能超过 1600 像素")
            has_transparency = (
                "A" in normalized_image.getbands()
                or "transparency" in normalized_image.info
            )
            converted_image = normalized_image.convert(
                "RGBA" if has_transparency else "RGB"
            )
            output = BytesIO()
            # 图标包含透明边缘和细线，无损 WebP 能避免有损压缩产生描边杂色。
            converted_image.save(
                output,
                format="WEBP",
                lossless=True,
                method=6,
                exact=True,
            )
            encoded_image = output.getvalue()

        with Image.open(BytesIO(encoded_image)) as verified_image:
            verified_image.verify()
            if verified_image.format != "WEBP":
                raise ValueError("项目图标转换为 WebP 失败")
        return encoded_image
    except ValueError:
        raise
    except (
        Image.DecompressionBombError,
        OSError,
        UnidentifiedImageError,
    ) as exc:
        raise ValueError("上传内容不是有效的项目图标") from exc


def save_project_icon_image(*, path: Path, content: bytes) -> None:
    """将已转换的 WebP 项目图标原子写入项目图标目录。"""
    if not content:
        raise ValueError("项目图标不能为空")

    project_icon_base_dir = settings.PROJECT_ICON_IMAGE_DIR.resolve()
    resolved_path = path.resolve()
    if not resolved_path.is_relative_to(project_icon_base_dir):
        raise ValueError("项目图标路径非法")
    if resolved_path.suffix.lower() != ".webp":
        raise ValueError("项目图标存储地址必须以 .webp 结尾")

    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    _write_bytes_atomically(path=resolved_path, content=content)


def convert_poster_image_to_webp(content: bytes) -> bytes:
    """将活动海报解码并统一重编码为适合文字展示的高质量 WebP。"""
    if not content:
        raise ValueError("活动海报不能为空")

    try:
        with Image.open(BytesIO(content)) as source_image:
            if source_image.format not in POSTER_SOURCE_FORMATS:
                raise ValueError("活动海报仅支持 JPEG、PNG 或 WebP")
            normalized_image = ImageOps.exif_transpose(source_image)
            has_transparency = (
                "A" in normalized_image.getbands()
                or "transparency" in normalized_image.info
            )
            converted_image = normalized_image.convert(
                "RGBA" if has_transparency else "RGB"
            )
            output = BytesIO()
            converted_image.save(
                output,
                format="WEBP",
                quality=POSTER_WEBP_QUALITY,
                method=6,
                alpha_quality=100,
            )
            encoded_image = output.getvalue()

        with Image.open(BytesIO(encoded_image)) as verified_image:
            verified_image.verify()
            if verified_image.format != "WEBP":
                raise ValueError("活动海报转换为 WebP 失败")
        return encoded_image
    except ValueError:
        raise
    except (
        Image.DecompressionBombError,
        OSError,
        UnidentifiedImageError,
    ) as exc:
        raise ValueError("上传内容不是有效的活动海报") from exc


def save_poster_image(*, path: Path, content: bytes) -> None:
    """将 WebP 海报原子写入固定资源目录，避免读取到半写入文件。"""
    if not content:
        raise ValueError("活动海报不能为空")

    poster_base_dir = settings.POSTER_IMAGE_DIR.resolve()
    resolved_path = path.resolve()
    if not resolved_path.is_relative_to(poster_base_dir):
        raise ValueError("活动海报路径非法")
    if resolved_path.suffix.lower() != ".webp":
        raise ValueError("活动海报存储地址必须以 .webp 结尾")

    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    _write_bytes_atomically(path=resolved_path, content=content)


def save_product_image(*, path: Path, content: bytes) -> None:
    """将已校验的奖品图片原子写入奖品资源目录。"""
    if not content:
        raise ValueError("奖品图片不能为空")

    product_base_dir = settings.PRODUCT_IMAGE_DIR.resolve()
    resolved_path = path.resolve()
    if not resolved_path.is_relative_to(product_base_dir):
        raise ValueError("商品图片路径非法")

    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    _write_bytes_atomically(path=resolved_path, content=content)


def remove_replaced_product_image(*, old_path: Path, new_path: Path) -> bool:
    """新奖品图片存在后移除旧文件，重试时旧文件缺失仍视为成功。"""
    product_base_dir = settings.PRODUCT_IMAGE_DIR.resolve()
    resolved_old_path = old_path.resolve()
    resolved_new_path = new_path.resolve()
    if not resolved_old_path.is_relative_to(product_base_dir):
        raise ValueError("商品图片路径非法")
    if not resolved_new_path.is_relative_to(product_base_dir):
        raise ValueError("商品图片路径非法")
    if resolved_old_path == resolved_new_path or not old_path.is_file():
        return False

    old_path.unlink()
    return True


def _write_bytes_atomically(*, path: Path, content: bytes) -> None:
    """先写入同目录临时文件，再原子替换，避免请求中途读到不完整图片。"""
    temporary_path = path.parent / f".{path.name}.{uuid4().hex}.tmp"
    try:
        temporary_path.write_bytes(content)
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def convert_avatar_to_webp(content: bytes) -> bytes:
    """解码远端图片并重编码为不超过 300 KiB 的标准 WebP。"""
    try:
        with Image.open(BytesIO(content)) as source_image:
            if source_image.format not in _AVATAR_SOURCE_FORMATS:
                raise ValueError("头像图片仅支持 JPEG、PNG 或 WebP")
            normalized_image = ImageOps.exif_transpose(source_image)
            has_transparency = (
                "A" in normalized_image.getbands()
                or "transparency" in normalized_image.info
            )
            converted_image = normalized_image.convert(
                "RGBA" if has_transparency else "RGB"
            )
            encoded_image = _encode_avatar_webp_with_size_limit(converted_image)

        with Image.open(BytesIO(encoded_image)) as verified_image:
            verified_image.verify()
            if verified_image.format != "WEBP":
                raise ValueError("头像图片转换为 WebP 失败")
        return encoded_image
    except ValueError:
        raise
    except (
        Image.DecompressionBombError,
        OSError,
        UnidentifiedImageError,
    ) as exc:
        raise ValueError("头像图片无法转换为 WebP") from exc


def _encode_avatar_webp_with_size_limit(image: Image.Image) -> bytes:
    """优先降低 WebP 质量，必要时缩放尺寸，限制新用户头像体积。"""
    current_image = image
    while True:
        for quality in _AVATAR_WEBP_QUALITY_STEPS:
            output = BytesIO()
            current_image.save(
                output,
                format="WEBP",
                quality=quality,
                method=6,
                alpha_quality=100,
            )
            encoded_image = output.getvalue()
            if len(encoded_image) <= AVATAR_WEBP_MAX_BYTES:
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
