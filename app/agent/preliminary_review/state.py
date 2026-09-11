"""工作流仅传递模型输入与结果，不携带数据库会话或 ORM 对象。"""

from typing import NotRequired, TypedDict

from openai.types.chat import ChatCompletionMessageParam

from app.agent.preliminary_review.schemas import (
    PreparedReviewImage,
    PreliminaryReviewRequest,
    PreliminaryReviewResult,
)


class PreliminaryReviewState(TypedDict):
    request: PreliminaryReviewRequest
    prepared_images: NotRequired[tuple[PreparedReviewImage, ...]]
    messages: NotRequired[list[ChatCompletionMessageParam]]
    result: NotRequired[PreliminaryReviewResult]
