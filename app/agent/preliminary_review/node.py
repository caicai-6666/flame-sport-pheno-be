"""初审工作流节点；模型调用直接使用 OpenAI 异步 API，不处理数据库事务。"""

import logging
from typing import Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from openai.types.responses import Response, ResponseInputParam
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.agent.preliminary_review.image_processing import build_record_images
from app.agent.preliminary_review.output_contract import PreliminaryReviewOutput, REVIEW_OUTPUT_JSON_SCHEMA
from app.agent.preliminary_review.prompt.context_renderer import render_review_messages
from app.agent.preliminary_review.schemas import PreliminaryReviewResult
from app.agent.preliminary_review.state import PreliminaryReviewState
from app.core.config import settings
from app.models.project_upload_config import MONTH_START_RECORD_TYPE


logger = logging.getLogger(__name__)
MAX_OUTPUT_TOKENS = 2048


class DeepSeekPreliminaryReviewError(RuntimeError):
    """上下文准备、模型请求或返回内容不符合初审契约。"""


def _response_input(messages: list[ChatCompletionMessageParam]) -> ResponseInputParam:
    """只适配节点2的消息格式，保留公共前缀、图片编号和图文顺序。"""
    if len(messages) != 2 or [item.get("role") for item in messages] != ["system", "user"]:
        raise DeepSeekPreliminaryReviewError("初审消息必须包含 system 和 user 上下文")
    result: ResponseInputParam = []
    for message in messages:
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            result.append({"role": message["role"], "content": content})
            continue
        if not isinstance(content, list) or not content or message["role"] != "user":
            raise DeepSeekPreliminaryReviewError("初审上下文内容无效")
        parts = []
        for part in content:
            if part.get("type") == "text" and isinstance(part.get("text"), str):
                parts.append({"type": "input_text", "text": part["text"]})
            elif part.get("type") == "image_url" and isinstance(part.get("image_url"), dict):
                url = part["image_url"].get("url")
                if not isinstance(url, str) or not url:
                    raise DeepSeekPreliminaryReviewError("初审图片内容为空")
                # 保留数字与日期的可读性，不请求低分辨率图片处理。
                parts.append({"type": "input_image", "image_url": url, "detail": "high"})
            else:
                raise DeepSeekPreliminaryReviewError("初审上下文包含不支持的内容类型")
        result.append({"role": "user", "content": parts})
    return result


def _review_result(response: Response, *, preserve_baseline: bool = False) -> PreliminaryReviewResult:
    """仅接受已完成的完整结构化回答，拒答或截断属于技术失败。"""
    if (getattr(response, "status", None) != "completed"
            or getattr(response, "error", None) is not None
            or getattr(response, "incomplete_details", None) is not None):
        raise DeepSeekPreliminaryReviewError("初审响应失败或未完整生成")
    if not isinstance(getattr(response, "output", None), list):
        raise DeepSeekPreliminaryReviewError("初审响应缺少输出")
    messages = []
    for item in response.output:
        if getattr(item, "type", None) == "reasoning":
            continue
        if (getattr(item, "type", None) != "message" or getattr(item, "role", None) != "assistant"
                or getattr(item, "status", None) != "completed"):
            raise DeepSeekPreliminaryReviewError("初审响应包含非预期输出")
        messages.append(item)
    if len(messages) != 1 or not isinstance(getattr(messages[0], "content", None), list) or not messages[0].content:
        raise DeepSeekPreliminaryReviewError("初审响应缺少唯一的审核结果")
    parts = messages[0].content
    if any(getattr(part, "type", None) != "output_text" or not isinstance(getattr(part, "text", None), str)
           for part in parts):
        raise DeepSeekPreliminaryReviewError("模型拒绝审核或返回非文本结果")
    content = "".join(part.text for part in parts)
    try:
        return PreliminaryReviewOutput.model_validate_json(content).to_review_result(preserve_baseline=preserve_baseline)
    except ValidationError:
        # 不输出 ValidationError 内容，其中可能带有用户图片取证信息。
        raise DeepSeekPreliminaryReviewError("初审结果不符合严格五字段契约") from None


async def prepare_images(state: PreliminaryReviewState) -> dict[str, Any]:
    """在线程池中构建记录图片，原始请求保持不变。"""
    image = state["request"].image
    if image is None:
        # 兼容既有独立文本评测；业务上传入口仍要求提供图片。
        return {"prepared_images": ()}
    try:
        prepared = await run_in_threadpool(build_record_images, image)
    except (ValueError, TypeError, RecursionError) as exc:
        # 图片处理错误属于技术失败，由外围保留待审，不生成用户审核不通过结论。
        raise DeepSeekPreliminaryReviewError("凭证图片准备失败") from exc
    return {"prepared_images": prepared}


async def render_context(state: PreliminaryReviewState) -> dict[str, Any]:
    """将规则追加到 system，按图片顺序和用户备注构建 user 消息。"""
    if "prepared_images" not in state:
        raise DeepSeekPreliminaryReviewError("上下文渲染前尚未准备记录图片")
    # 多张切片的 Base64 编码放在线程池中，避免阻塞并发审核的事件循环。
    messages = await run_in_threadpool(
        render_review_messages, state["request"], state["prepared_images"],
    )
    return {"messages": messages}


async def review(state: PreliminaryReviewState) -> dict[str, PreliminaryReviewResult]:
    """直接消费节点2消息，单次调用异步 Responses API 并返回既有业务结果。"""
    if not state.get("messages"):
        raise DeepSeekPreliminaryReviewError("模型判断前尚未渲染上下文")
    inputs = _response_input(state["messages"])
    if not settings.DEEPSEEK_API_KEY:
        raise DeepSeekPreliminaryReviewError("未配置 DEEPSEEK_API_KEY")
    try:
        async with AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL.rstrip("/"),
            timeout=settings.DEEPSEEK_HTTP_TIMEOUT_SECONDS,
            # 单条任务不因网络或格式失败隐式重复调用；后续重审由外围调度负责。
            max_retries=0,
        ) as client:
            response = await client.responses.create(
                model=settings.DEEPSEEK_MODEL,
                input=inputs,
                text={"format": {
                    "type": "json_schema", "name": "preliminary_review",
                    "strict": True, "schema": REVIEW_OUTPUT_JSON_SCHEMA,
                }},
                reasoning={"effort": "none"},
                temperature=0,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                stream=False,
            )
    except Exception as exc:
        raise DeepSeekPreliminaryReviewError(
            f"DeepSeek 初审请求失败：{type(exc).__name__}",
        ) from None
    usage = getattr(response, "usage", None)
    if usage is not None:
        logger.info(
            "DeepSeek preliminary review usage: input_tokens=%s cached_tokens=%s output_tokens=%s",
            getattr(usage, "input_tokens", None),
            getattr(getattr(usage, "input_tokens_details", None), "cached_tokens", None),
            getattr(usage, "output_tokens", None),
        )
    return {"result": _review_result(
        response, preserve_baseline=state["request"].record_type == MONTH_START_RECORD_TYPE,
    )}
