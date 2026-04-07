"""
系统配置文件
使用 Pydantic Settings 进行配置管理
"""
from pathlib import Path
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """系统配置类"""
    
    # 项目路径配置
    PROJECT_ROOT: Path = Field(default=Path(__file__).parent.parent)
    
    # 目录配置（在类外计算）
    @property
    def DATA_DIR(self) -> Path:
        return self.PROJECT_ROOT / "data"
    
    @property
    def LOGS_DIR(self) -> Path:
        return self.PROJECT_ROOT / "logs"
    
    @property
    def CONFIG_DIR(self) -> Path:
        return self.PROJECT_ROOT / "config"
    
    # LLM 配置
    LLM_API_KEY: Optional[str] = Field(default=None, description="LLM API Key")
    LLM_BASE_URL: Optional[str] = Field(default=None, description="LLM API Base URL")
    LLM_MODEL: str = Field(default="gpt-4o", description="使用的 LLM 模型")
    LLM_TEMPERATURE: float = Field(default=0.7, ge=0, le=1)
    
    # 爬虫配置
    REQUEST_DELAY: float = Field(default=1.0, ge=0, description="请求间隔时间（秒）")
    MAX_RETRIES: int = Field(default=3, ge=1, description="最大重试次数")
    USER_AGENT: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    
    # 筛选条件默认值
    DEFAULT_CITIES: List[str] = Field(default=["北京", "上海", "深圳", "杭州"])
    MIN_SALARY: int = Field(default=0, ge=0, description="最低薪资（元/月）")
    MAX_SALARY: int = Field(default=50000, ge=0, description="最高薪资（元/月）")
    JOB_TYPES: List[str] = Field(default=["实习", "全职"], description="工作类型")
    
    # 投递配置
    AUTO_SUBMIT: bool = Field(default=False, description="是否自动投递")
    DAILY_LIMIT: int = Field(default=50, ge=1, description="每日投递上限")
    
    # 日志配置
    LOG_LEVEL: str = Field(default="INFO", description="日志级别")
    LOG_FORMAT: str = Field(
        default="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{line} - {message}",
        description="日志格式"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# 全局配置实例
settings = Settings()
