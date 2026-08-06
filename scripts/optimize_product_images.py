"""压缩积分商城商品图片，并在替换前将原文件备份到同一资源卷。"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from PIL import Image


SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="压缩超过目标大小的商品图片")
    parser.add_argument("--source-dir", type=Path, required=True, help="商品图片目录")
    parser.add_argument("--backup-dir", type=Path, required=True, help="原图备份目录")
    parser.add_argument("--target-kib", type=int, default=450, help="单图目标大小，默认 450 KiB")
    return parser.parse_args()


def save_candidate(image: Image.Image, target: Path, image_format: str, quality: int | None) -> None:
    options: dict[str, object] = {"optimize": True}
    if image_format == "JPEG":
        options.update({"quality": quality, "progressive": True})
    else:
        options.update({"compress_level": 9})
    image.save(target, format=image_format, **options)


def compress_image(source: Path, target_bytes: int) -> tuple[int, tuple[int, int], tuple[int, int]]:
    """返回新大小、原始尺寸、最终尺寸；替换过程使用同目录临时文件。"""
    with Image.open(source) as opened:
        image_format = opened.format
        if image_format not in {"JPEG", "PNG"}:
            raise ValueError(f"不支持的图片格式: {image_format}")
        image = opened.copy()

    original_dimensions = image.size
    temporary = source.with_suffix(f"{source.suffix}.tmp")
    quality_values = (88, 82, 76, 70, 64, 58) if image_format == "JPEG" else (None,)

    # 先降低 JPEG 质量；仍不达标时逐步缩小像素尺寸，PNG 保留透明通道。
    for _ in range(12):
        for quality in quality_values:
            save_candidate(image, temporary, image_format, quality)
            if temporary.stat().st_size <= target_bytes:
                temporary.replace(source)
                return source.stat().st_size, original_dimensions, image.size
        width, height = image.size
        if min(width, height) <= 240:
            break
        image = image.resize((max(1, int(width * 0.85)), max(1, int(height * 0.85))), Image.Resampling.LANCZOS)

    temporary.unlink(missing_ok=True)
    raise RuntimeError(f"压缩后仍无法达到 {target_bytes} bytes")


def main() -> None:
    args = parse_args()
    target_bytes = args.target_kib * 1024
    source_dir = args.source_dir.resolve()
    backup_dir = args.backup_dir.resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)

    candidates = [
        path for path in sorted(source_dir.iterdir())
        if path.is_file() and not path.name.startswith("._") and path.suffix.lower() in SUPPORTED_SUFFIXES
        and path.stat().st_size > target_bytes
    ]
    if not candidates:
        print("没有超过目标大小的商品图片。")
        return

    for source in candidates:
        backup = backup_dir / source.name
        if not backup.exists():
            shutil.copy2(source, backup)
        new_size, original_dimensions, final_dimensions = compress_image(source, target_bytes)
        print(f"{source.name}: {backup.stat().st_size} -> {new_size} bytes, {original_dimensions} -> {final_dimensions}")


if __name__ == "__main__":
    main()
