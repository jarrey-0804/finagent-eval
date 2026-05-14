"""
配置模块

提供系统配置管理功能。
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class DatabaseConfig(BaseModel):
    """数据库配置"""

    url: str = Field(
        default="postgresql://localhost:5432/finagent_eval", description="数据库连接URL"
    )
    pool_size: int = Field(default=10, description="连接池大小")
    max_overflow: int = Field(default=20, description="最大溢出连接数")


class LLMConfig(BaseModel):
    """LLM配置"""

    openai_api_key: str | None = Field(None, description="OpenAI API密钥")
    anthropic_api_key: str | None = Field(None, description="Anthropic API密钥")
    deepseek_api_key: str | None = Field(None, description="DeepSeek API密钥")

    default_model: str = Field(default="gpt-4o", description="默认模型")
    temperature: float = Field(default=0.1, description="温度参数")
    max_tokens: int = Field(default=2048, description="最大token数")


class EvaluationConfig(BaseModel):
    """评测配置"""

    default_mode: str = Field(default="full", description="默认评测模式")
    max_concurrent_tasks: int = Field(default=5, description="最大并发任务数")
    task_timeout: int = Field(default=300, description="任务超时时间(秒)")

    # 评分配置
    pass_threshold: float = Field(default=60.0, description="通过阈值")
    veto_threshold: float = Field(default=30.0, description="一票否决阈值")


class APIConfig(BaseModel):
    """API配置"""

    host: str = Field(default="127.0.0.1", description="监听地址 (默认仅本地访问)")
    port: int = Field(default=8000, description="监听端口")
    workers: int = Field(default=4, description="工作进程数")
    cors_origins: list[str] = Field(default=["*"], description="CORS允许的源")


class LoggingConfig(BaseModel):
    """日志配置"""

    level: str = Field(default="INFO", description="日志级别")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="日志格式"
    )
    file: str | None = Field(None, description="日志文件路径")


class Config(BaseModel):
    """主配置"""

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Config":
        """从YAML文件加载配置"""
        path = Path(path)
        if not path.exists():
            return cls()

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        return cls(**data)

    def to_yaml(self, path: str | Path):
        """保存配置到YAML文件"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False)


# 默认配置文件路径
DEFAULT_CONFIG_PATH = Path("config/config.yaml")


def load_config(path: str | Path | None = None) -> Config:
    """加载配置"""
    if path is None:
        path = DEFAULT_CONFIG_PATH

    return Config.from_yaml(path)
