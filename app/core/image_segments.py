"""凭证图片分段定位校验，供普通上传与结算期补交共用。"""

import json
from io import BytesIO
from typing import Any

from PIL import Image


MAX_IMAGE_SEGMENTS = 5
MAX_IMAGE_SEGMENTS_BYTES = 4096


def validate_image_segments(raw: str | None, webp_content: bytes) -> dict[str, Any] | None:
    """按最终落盘图片校验定位；缺省值兼容尚未传入分段信息的客户端。"""
    if raw is None or not raw.strip():
        return None
    if len(raw.encode("utf-8")) > MAX_IMAGE_SEGMENTS_BYTES:
        raise ValueError("image_segments 不能超过 4096 字节")
    try:
        data = json.loads(raw)
    except (ValueError, RecursionError) as exc:
        raise ValueError("image_segments 必须是合法 JSON 对象") from exc
    if not isinstance(data, dict) or set(data) != {"version", "width", "height", "segments"}:
        raise ValueError("image_segments 必须包含 version、width、height、segments，且不能有额外字段")
    # bool 是 int 的子类，必须用精确类型判断，避免 true 被误认作坐标或版本号。
    if type(data["version"]) is not int or data["version"] != 1:
        raise ValueError("image_segments.version 仅支持整数 1")
    for field in ("width", "height"):
        if type(data[field]) is not int or data[field] <= 0:
            raise ValueError(f"image_segments.{field} 必须为正整数")
    segments = data["segments"]
    if not isinstance(segments, list) or not 1 <= len(segments) <= MAX_IMAGE_SEGMENTS:
        raise ValueError("image_segments.segments 必须包含 1 至 5 个分段")

    # 以修正 EXIF 方向并转码后的实际图片为准，不能信任前端声明的画布大小。
    with Image.open(BytesIO(webp_content)) as image:
        if image.size != (data["width"], data["height"]):
            raise ValueError("image_segments 尺寸与实际保存图片不一致")
    previous_bottom = 0
    for segment in segments:
        if not isinstance(segment, dict) or set(segment) != {"x", "y", "width", "height"}:
            raise ValueError("每个图片分段必须且只能包含 x、y、width、height")
        if any(type(segment[field]) is not int for field in segment):
            raise ValueError("图片分段坐标与尺寸必须为整数")
        x, y, width, height = (segment[field] for field in ("x", "y", "width", "height"))
        if x < 0 or y < 0 or width <= 0 or height <= 0:
            raise ValueError("图片分段坐标必须非负，宽高必须为正数")
        if x + width > data["width"] or y + height > data["height"]:
            raise ValueError("图片分段不能超出图片边界")
        # 前端纵向拼接允许边距与间隙，但原图区域不能重叠或倒序。
        if y < previous_bottom:
            raise ValueError("图片分段必须按从上到下排列且不能重叠")
        previous_bottom = y + height
    return data
