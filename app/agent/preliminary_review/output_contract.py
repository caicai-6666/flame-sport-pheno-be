"""初审严格输出契约；用于模型节点原生 Schema 与返回值校验。"""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.agent.preliminary_review.schemas import PreliminaryReviewResult
from app.models.proof_record import ProofReviewStatus


class PreliminaryReviewOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    evidence: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]] = Field(
        min_length=1, max_length=5, description="注明图片编号或其他来源的判断证据，不编造缺失事实",
    )
    reasoning: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)] = Field(
        description="简短审核理由，说明规则对应关系、最终判断和增量计算，不输出完整思维过程",
    )
    result_type: Literal["通过", "不通过"]
    delta: float = Field(ge=0, le=1, allow_inf_nan=False, description="本条记录的原始进度增量")

    comment: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)] = Field(
        description="面向用户的简短审核评论，一句话说明结论与关键原因，不含字段名或计算过程",
    )

    @model_validator(mode="after")
    def check_rejected_delta(self) -> "PreliminaryReviewOutput":
        if self.result_type == "不通过" and self.delta != 0:
            raise ValueError("不通过时 delta 必须为 0")
        return self

    def to_review_result(self, *, preserve_baseline: bool = False) -> PreliminaryReviewResult:
        # 普通意见展示短评；月初还需保存完整基线供月末读取，合并后仍不超过500字符。
        comment = self.comment
        if preserve_baseline:
            comment += "\n证据：" + "；".join(self.evidence) + "\n理由：" + self.reasoning
        return PreliminaryReviewResult(
            review_comment=comment,
            review_status=(
                ProofReviewStatus.PRELIMINARY_APPROVED
                if self.result_type == "通过"
                else ProofReviewStatus.PRELIMINARY_REJECTED
            ),
            progress_delta=Decimal(str(self.delta)),
        )


# properties 的声明顺序与提示词一致；所有字段必填，禁止额外字段。
REVIEW_OUTPUT_JSON_SCHEMA = PreliminaryReviewOutput.model_json_schema()
