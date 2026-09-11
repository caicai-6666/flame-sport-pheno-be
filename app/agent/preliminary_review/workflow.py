"""初审 LangGraph 工作流入口，由业务层准备上下文并处理结果。"""

from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.preliminary_review.node import prepare_images, render_context, review
from app.agent.preliminary_review.schemas import (
    PreliminaryReviewRequest,
    PreliminaryReviewResult,
)
from app.agent.preliminary_review.state import PreliminaryReviewState


def build_workflow() -> CompiledStateGraph:
    """构建独立工作流；编译不发起模型请求，也不启动定时任务。"""
    builder = StateGraph(PreliminaryReviewState)
    builder.add_node("prepare_images", prepare_images)
    builder.add_node("render_context", render_context)
    builder.add_node("review", review)
    builder.add_edge(START, "prepare_images")
    builder.add_edge("prepare_images", "render_context")
    builder.add_edge("render_context", "review")
    builder.add_edge("review", END)
    return builder.compile()


@lru_cache(maxsize=1)
def get_workflow() -> CompiledStateGraph:
    # 只缓存图定义，不启用检查点；每次调用使用独立状态，避免跨用户保留审核内容。
    return build_workflow()


async def run_preliminary_review(request: PreliminaryReviewRequest) -> PreliminaryReviewResult:
    """异步执行模型初审；结果持久化仍由调用方的 Service 负责。"""
    state = await get_workflow().ainvoke({"request": request})
    return state["result"]
