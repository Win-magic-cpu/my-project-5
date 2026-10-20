from typing import Any

from langchain.chat_models import init_chat_model

from shopmate.conf.config import settings


def build_llm() -> Any:
    """按配置创建大模型客户端。"""
    if not settings.llm_api_key:
        raise RuntimeError(
            "未配置 LLM_API_KEY：请复制 .env.example 为 .env 并填入百炼 API Key。"
        )
    return init_chat_model(
        model=settings.llm_model,
        model_provider="openai",
        api_key=settings.llm_api_key,
        temperature=0,
        base_url=settings.llm_base_url,
    )


def get_llm() -> Any:
    """返回全局 LLM 客户端；未配置 Key 时给出明确错误。"""
    if llm is None:
        raise RuntimeError(
            "LLM 客户端尚未就绪：请在 .env 中配置 LLM_API_KEY 后重启服务。"
        )
    return llm


# 未配置 Key 时保持 None，保证单元测试和纯流程逻辑可以正常导入
llm = build_llm() if settings.llm_api_key else None
