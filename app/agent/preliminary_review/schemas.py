"""初审模型的输入输出契约。"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any
from decimal import Decimal

from app.models.proof_record import ProofReviewStatus


@dataclass(frozen=True)
class PreliminaryReviewImage:
    """完整凭证图片与基于落盘图片像素坐标的分段定位。"""

    content: bytes = field(repr=False)
    media_type: str
    image_segments: dict[str, Any] | None = None


@dataclass(frozen=True)
class PreparedReviewImage:
    """节点准备的记录图片；序号从 1 开始，坐标对应原始整图。"""

    index: int
    x: int
    y: int
    width: int
    height: int
    media_type: str
    content: bytes = field(repr=False)


@dataclass(frozen=True)
class PreliminaryReviewRequest:
    project_name: str
    record_type: str
    rule_content: list[dict[str, str]]
    rule_note: str
    note: str
    initial_review_comment: str | None = None
    proof_date: date | None = None
    image: PreliminaryReviewImage | None = field(default=None, repr=False)
    season_start_date: date | None = None
    season_end_date: date | None = None


@dataclass(frozen=True)
class PreliminaryReviewResult:
    review_comment: str
    review_status: ProofReviewStatus
    progress_delta: Decimal
