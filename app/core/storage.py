import re
from datetime import datetime
from pathlib import Path

from app.core.config import settings


def ensure_asset_directories() -> None:
    """确保项目运行所需的本地资源目录存在。"""
    settings.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    settings.IMAGE_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    settings.AVATAR_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    settings.PROJECT_ICON_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
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
    season_dir = settings.PROOF_RECORD_IMAGE_DIR / str(season_id)
    season_dir.mkdir(parents=True, exist_ok=True)
    safe_user_id = _normalize_path_part(user_id)
    safe_timestamp = _normalize_proof_record_timestamp(timestamp)
    safe_filename = _normalize_proof_record_filename(filename)
    return season_dir / f"{safe_user_id}-{project_id}-{safe_timestamp}-{safe_filename}.jpg"


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
