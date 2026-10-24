from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# shopmate/conf/config.py -> parents[2] 即项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    # LLM
    llm_api_key: str = ""
    llm_model: str = "qwen-plus"
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # 数据库
    database_url: str = (
        "mysql+aiomysql://root:123456@127.0.0.1:3306"
        "/customer_service?charset=utf8mb4"
    )

    # 商城 API
    commerce_api_base_url: str = "http://127.0.0.1:18081"

    # 服务器
    app_host: str = "0.0.0.0"
    app_port: int = 18082

    # 会话超时时间（秒），默认 1 小时
    session_timeout_seconds: int = 60 * 60
    # 启动时自动建表，方便本地一条命令跑起来
    auto_create_tables: bool = True

    # 检索增强（RAG）
    # auto: 配了 LLM_API_KEY 用 dashscope，否则用本地 hashing
    embedding_provider: str = "auto"
    embedding_model: str = "text-embedding-v3"
    embedding_dim: int = 512
    rag_top_k: int = 3
    rag_min_score: float = 0.15
    rag_index_path: str = "./data/rag_index.json"

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
