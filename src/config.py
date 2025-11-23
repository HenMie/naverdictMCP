"""Configuration management for Naver Dictionary MCP server."""

import os
from typing import Literal
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class ConfigError(Exception):
    """Configuration validation error."""
    pass


class Config:
    """Application configuration with environment variable support and validation."""
    
    # Server settings
    SERVER_HOST: str
    SERVER_PORT: int
    
    # HTTP client settings
    HTTP_TIMEOUT: float
    
    # Logging settings
    LOG_LEVEL: str
    
    # Naver API settings
    NAVER_BASE_URL: str
    
    def __init__(self, validate: bool = True):
        """Initialize configuration from environment variables.
        
        Args:
            validate: Whether to validate configuration after initialization
        """
        self.SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
        self.SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
        self.HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "30.0"))
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
        self.NAVER_BASE_URL = os.getenv(
            "NAVER_BASE_URL",
            "https://korean.dict.naver.com/api3"
        )
        
        # 自动验证配置（除非明确禁用）
        if validate:
            self.validate()
    
    def validate(self) -> None:
        """
        Validate configuration values.
        
        Raises:
            ConfigError: If any configuration value is invalid
        """
        # 验证端口号
        if not 0 < self.SERVER_PORT < 65536:
            raise ConfigError(f"无效的端口号: {self.SERVER_PORT}，必须在 1-65535 之间")
        
        # 验证超时时间
        if self.HTTP_TIMEOUT <= 0:
            raise ConfigError(f"无效的超时时间: {self.HTTP_TIMEOUT}，必须大于 0")
        
        if self.HTTP_TIMEOUT > 300:
            raise ConfigError(f"超时时间过长: {self.HTTP_TIMEOUT}，建议不超过 300 秒")
        
        # 验证日志级别
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.LOG_LEVEL not in valid_log_levels:
            raise ConfigError(
                f"无效的日志级别: {self.LOG_LEVEL}，"
                f"必须是以下之一: {', '.join(valid_log_levels)}"
            )
        
        # 验证 URL 格式
        if not self.NAVER_BASE_URL.startswith(("http://", "https://")):
            raise ConfigError(f"无效的 URL 格式: {self.NAVER_BASE_URL}")
    
    def get_server_address(self) -> str:
        """Get the full server address."""
        return f"http://{self.SERVER_HOST}:{self.SERVER_PORT}"


# Global config instance
def _init_config():
    """Initialize global config with error handling."""
    try:
        return Config()
    except ConfigError as e:
        # 如果配置无效，打印错误并使用默认值
        print(f"配置错误: {e}")
        print("使用默认配置...")
        # 清除环境变量，使用默认值
        for key in ["SERVER_HOST", "SERVER_PORT", "HTTP_TIMEOUT", "LOG_LEVEL", "NAVER_BASE_URL"]:
            os.environ.pop(key, None)
        return Config()

# 只在非测试环境下初始化全局配置
if not os.getenv("PYTEST_CURRENT_TEST"):
    config = _init_config()
else:
    # 测试环境也初始化配置，但不自动验证（让测试自行控制）
    config = Config(validate=False)
