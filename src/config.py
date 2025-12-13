"""配置管理模块。

提供应用配置管理，支持环境变量和配置验证。

注意：为保证测试稳定性，pytest 环境下不会自动读取本地 `.env` 文件，
避免开发者机器上的环境配置影响测试结果。
"""

import os
import sys
from typing import Literal

from dotenv import load_dotenv


def _is_running_tests() -> bool:
    """判断当前是否运行在测试环境中。"""
    # pytest 在运行期间会导入 pytest 包（包括收集阶段），可靠性高于 PYTEST_CURRENT_TEST
    return "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST") is not None


# 仅在非测试环境下从 .env 文件加载环境变量
if not _is_running_tests():
    load_dotenv()

# 日志级别类型
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class ConfigError(Exception):
    """配置验证错误。"""
    pass


class Config:
    """应用配置类，支持环境变量和验证。
    
    配置项:
        - SERVER_HOST: 服务器监听地址
        - SERVER_PORT: 服务器端口
        - HTTP_TIMEOUT: HTTP 请求超时时间
        - LOG_LEVEL: 日志级别
        - NAVER_BASE_URL: Naver API 基础 URL
    """
    
    # 服务器设置
    SERVER_HOST: str
    SERVER_PORT: int
    
    # HTTP 客户端设置
    HTTP_TIMEOUT: float
    
    # 日志设置
    LOG_LEVEL: str
    
    # Naver API 设置
    NAVER_BASE_URL: str
    
    def __init__(self, validate: bool = True) -> None:
        """
        从环境变量初始化配置。
        
        Args:
            validate: 是否在初始化后验证配置
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
        验证配置值。
        
        Raises:
            ConfigError: 如果任何配置值无效
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
        """获取完整的服务器地址。"""
        return f"http://{self.SERVER_HOST}:{self.SERVER_PORT}"


def _init_config() -> Config:
    """初始化全局配置（带错误处理）。"""
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
if not _is_running_tests():
    config = _init_config()
else:
    # 测试环境初始化配置，但不自动验证（让测试自行控制）
    config = Config(validate=False)
