"""渲染本次审核的 system 与多模态 user 消息，不调用模型。"""

from base64 import b64encode

from openai.types.chat import ChatCompletionContentPartParam, ChatCompletionMessageParam

from app.agent.preliminary_review.prompt import MONTHLY_SYSTEM_PROMPT, ORDINARY_SYSTEM_PROMPT
from app.agent.preliminary_review.schemas import PreliminaryReviewRequest, PreparedReviewImage
from app.models.project_upload_config import MONTH_START_RECORD_TYPE, MONTH_END_RECORD_TYPE


def render_review_messages(
    request: PreliminaryReviewRequest,
    images: tuple[PreparedReviewImage, ...],
) -> list[ChatCompletionMessageParam]:
    """按凭证类型选择提示词，再追加项目上下文和用户图文消息。"""
    # 阶段由上传配置决定，不按项目名称分流，其他阶段型项目和补交快照也使用相同规则。
    system_prompt = (
        MONTHLY_SYSTEM_PROMPT
        if request.record_type in {MONTH_START_RECORD_TYPE, MONTH_END_RECORD_TYPE}
        else ORDINARY_SYSTEM_PROMPT
    )
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
        # 月初评价放在规则之后，保留所选提示词和同项目规则的稳定前缀。
        project_context.extend([
            "【月初评价开始】", request.initial_review_comment,
        ])

    content: list[ChatCompletionContentPartParam] = []
    # 阶段型凭证按原赛季边界注入审核日期，不改变上传日期字段或原始请求。
    review_date = request.proof_date
    if request.record_type in {MONTH_START_RECORD_TYPE, MONTH_END_RECORD_TYPE}:
        if request.season_start_date is None or request.season_end_date is None:
            raise ValueError("月初、月末初审必须提供赛季起止日期")
        review_date = (
            request.season_start_date
            if request.record_type == MONTH_START_RECORD_TYPE
            else request.season_end_date
        )
    if review_date is not None:
        content.append({"type": "text", "text": f"运动日期：{review_date.isoformat()}"})
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
        {"role": "system", "content": system_prompt + "\n\n" + "\n".join(project_context)},
        {"role": "user", "content": content},
    ]
