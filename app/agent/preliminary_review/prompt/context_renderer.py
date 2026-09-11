"""渲染本次审核的 system 与多模态 user 消息，不调用模型。"""

from base64 import b64encode

from openai.types.chat import ChatCompletionContentPartParam, ChatCompletionMessageParam

from app.agent.preliminary_review.prompt.preliminary_review_prompt import SYSTEM_PROMPT
from app.agent.preliminary_review.schemas import PreliminaryReviewRequest, PreparedReviewImage


def render_review_messages(
    request: PreliminaryReviewRequest,
    images: tuple[PreparedReviewImage, ...],
) -> list[ChatCompletionMessageParam]:
    """公共提示词保持原样，项目上下文随后追加，用户图片和备注单独成消息。"""
    project_context = [
        "【项目上下文开始】",
        f"项目名称：{request.project_name}",
        f"凭证类型：{request.record_type}",
        "项目规则：",
        *(f"- {rule['label']}：{rule['value']}" for rule in request.rule_content),
    ]
    if request.season_start_date is not None and request.season_end_date is not None:
        if request.season_start_date > request.season_end_date:
            raise ValueError("赛季开始日期不得晚于结束日期")
        project_context.extend([
            f"赛季开始日期：{request.season_start_date.isoformat()}（含当日）",
            f"赛季结束日期：{request.season_end_date.isoformat()}（含当日）",
        ])
    elif request.season_start_date is not None or request.season_end_date is not None:
        raise ValueError("赛季起止日期必须同时提供")
    if request.rule_note:
        project_context.extend(["规则补充说明：", request.rule_note])
    if request.initial_review_comment:
        # 月初评价放在规则之后，保留前面公共提示词和同项目规则的稳定前缀。
        project_context.extend([
            "【月初评价开始】", request.initial_review_comment,
        ])

    content: list[ChatCompletionContentPartParam] = []
    if request.proof_date is not None:
        content.append({"type": "text", "text": f"运动日期：{request.proof_date.isoformat()}"})
    for image in images:
        content.append({
            "type": "text",
            "text": f"【第{image.index}张图片开始】",
        })
        # 编号文本与实际图片内容交错排列；Base64 只进入图片字段，不拼入普通文本。
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{image.media_type};base64,{b64encode(image.content).decode('ascii')}",
            },
        })
    content.append({
        "type": "text",
        "text": f"【用户备注开始】\n{request.note}",
    })
    return [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + "\n".join(project_context)},
        {"role": "user", "content": content},
    ]
