"""配置管理模块。

提供应用配置管理，支持环境变量和配置验证。

注意：为保证测试稳定性，pytest 环境下不会自动读取本地 `.env` 文件，
避免开发者机器上的环境配置影响测试结果。
"""

from __future__ import annotations

import os
import sys
from typing import Literal, Optional

from dotenv import load_dotenv


def _is_running_tests() -> bool:
    """判断当前是否运行在测试环境中。"""
    # pytest 在运行期间会导入 pytest 包（包括收集阶段），可靠性高于 PYTEST_CURRENT_TEST
    return "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST") is not None


class ConfigError(Exception):
    """配置验证错误。"""
    pass


EnvMode = Literal["development", "testing", "production"]

# 日志级别类型
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def _detect_env_mode() -> EnvMode:
    """检测当前运行模式（开发/测试/生产）。

    优先级：
    1) pytest 运行时强制为 testing（避免 .env 污染测试）
    2) 环境变量 APP_ENV（支持 dev/test/prod 别名）
    3) 默认 development
    """
    if _is_running_tests():
        return "testing"

    raw = os.getenv("APP_ENV", "").strip().lower()
    if raw == "":
        return "development"

    alias_map: dict[str, EnvMode] = {
        "dev": "development",
        "development": "development",
        "test": "testing",
        "testing": "testing",
        "prod": "production",
        "production": "production",
    }
    if raw not in alias_map:
        raise ConfigError(
            f"无效的 APP_ENV: {raw}，必须是 development/testing/production（或 dev/test/prod）"
        )
    return alias_map[raw]


# 当前进程运行模式
ENV_MODE: EnvMode = _detect_env_mode()

# 仅在开发模式下从 .env 文件加载环境变量（生产环境建议由部署平台注入环境变量）
if ENV_MODE == "development":
    load_dotenv()


def _parse_int(name: str, raw: str) -> int:
    """解析整数环境变量（内部方法）。"""
    try:
        return int(raw)
    except (TypeError, ValueError) as e:  # pragma: no cover
        raise ConfigError(f"无效的 {name}: {raw}，必须是整数") from e


def _parse_float(name: str, raw: str) -> float:
    """解析浮点环境变量（内部方法）。"""
    try:
        return float(raw)
    except (TypeError, ValueError) as e:  # pragma: no cover
        raise ConfigError(f"无效的 {name}: {raw}，必须是数字") from e


class Config:
    """应用配置类，支持环境变量和验证。
    
    配置项:
        - SERVER_HOST: 服务器监听地址
        - SERVER_PORT: 服务器端口
        - HTTP_TIMEOUT: HTTP 请求超时时间
        - LOG_LEVEL: 日志级别
        - NAVER_BASE_URL: Naver API 基础 URL
        - APP_ENV: 运行模式（development/testing/production）
        - REQUESTS_PER_MINUTE: 上游请求限流（每分钟）
        - CACHE_TTL: 缓存 TTL（秒）
        - CACHE_MAX_SIZE: 缓存最大条目数
        - HTTPX_MAX_KEEPALIVE_CONNECTIONS: httpx 连接池 keep-alive 连接上限
        - HTTPX_MAX_CONNECTIONS: httpx 连接池总连接上限
        - HTTPX_KEEPALIVE_EXPIRY: httpx keep-alive 连接过期时间（秒）
        - BATCH_CONCURRENCY: 批量查询内部并发上限（仅针对上游请求）
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

    # 运行模式
    APP_ENV: EnvMode

    # 限流/缓存/连接池等关键参数
    REQUESTS_PER_MINUTE: int
    CACHE_TTL: int
    CACHE_MAX_SIZE: int
    HTTPX_MAX_KEEPALIVE_CONNECTIONS: int
    HTTPX_MAX_CONNECTIONS: int
    HTTPX_KEEPALIVE_EXPIRY: float
    BATCH_CONCURRENCY: int
    
    def __init__(self, validate: bool = True, env_mode: Optional[EnvMode] = None) -> None:
        """
        从环境变量初始化配置。
        
        Args:
            validate: 是否在初始化后验证配置
            env_mode: 显式指定运行模式（默认自动检测）
        """
        self.APP_ENV = env_mode or _detect_env_mode()

        self.SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
        self.SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
        self.HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "30.0"))
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
        self.NAVER_BASE_URL = os.getenv(
            "NAVER_BASE_URL",
            "https://korean.dict.naver.com/api3"
        )

        # 关键参数（统一从环境变量读取，避免散落在各模块）
        raw_rpm = os.getenv("REQUESTS_PER_MINUTE", "60")
        self.REQUESTS_PER_MINUTE = _parse_int("REQUESTS_PER_MINUTE", raw_rpm)

        raw_cache_ttl = os.getenv("CACHE_TTL", "3600")
        self.CACHE_TTL = _parse_int("CACHE_TTL", raw_cache_ttl)

        raw_cache_max_size = os.getenv("CACHE_MAX_SIZE", "1000")
        self.CACHE_MAX_SIZE = _parse_int("CACHE_MAX_SIZE", raw_cache_max_size)

        raw_keepalive = os.getenv("HTTPX_MAX_KEEPALIVE_CONNECTIONS", "20")
        self.HTTPX_MAX_KEEPALIVE_CONNECTIONS = _parse_int(
            "HTTPX_MAX_KEEPALIVE_CONNECTIONS", raw_keepalive
        )

        raw_max_conn = os.getenv("HTTPX_MAX_CONNECTIONS", "100")
        self.HTTPX_MAX_CONNECTIONS = _parse_int("HTTPX_MAX_CONNECTIONS", raw_max_conn)

        raw_keepalive_expiry = os.getenv("HTTPX_KEEPALIVE_EXPIRY", "30.0")
        self.HTTPX_KEEPALIVE_EXPIRY = _parse_float("HTTPX_KEEPALIVE_EXPIRY", raw_keepalive_expiry)

        raw_batch_concurrency = os.getenv("BATCH_CONCURRENCY", "5")
        self.BATCH_CONCURRENCY = _parse_int("BATCH_CONCURRENCY", raw_batch_concurrency)
        
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

        # 验证运行模式（在实例化时已解析，这里做兜底）
        if self.APP_ENV not in ("development", "testing", "production"):
            raise ConfigError(f"无效的 APP_ENV: {self.APP_ENV}")

        # 限流参数：必须大于 0
        if self.REQUESTS_PER_MINUTE <= 0:
            raise ConfigError(f"无效的 REQUESTS_PER_MINUTE: {self.REQUESTS_PER_MINUTE}，必须大于 0")

        # 缓存参数
        if self.CACHE_TTL <= 0:
            raise ConfigError(f"无效的 CACHE_TTL: {self.CACHE_TTL}，必须大于 0")
        if self.CACHE_MAX_SIZE <= 0:
            raise ConfigError(f"无效的 CACHE_MAX_SIZE: {self.CACHE_MAX_SIZE}，必须大于 0")

        # httpx 连接池参数
        if self.HTTPX_MAX_CONNECTIONS <= 0:
            raise ConfigError(
                f"无效的 HTTPX_MAX_CONNECTIONS: {self.HTTPX_MAX_CONNECTIONS}，必须大于 0"
            )
        if self.HTTPX_MAX_KEEPALIVE_CONNECTIONS < 0:
            raise ConfigError(
                f"无效的 HTTPX_MAX_KEEPALIVE_CONNECTIONS: {self.HTTPX_MAX_KEEPALIVE_CONNECTIONS}，必须 ≥ 0"
            )
        if self.HTTPX_MAX_KEEPALIVE_CONNECTIONS > self.HTTPX_MAX_CONNECTIONS:
            raise ConfigError(
                "HTTPX_MAX_KEEPALIVE_CONNECTIONS 不能大于 HTTPX_MAX_CONNECTIONS"
            )
        if self.HTTPX_KEEPALIVE_EXPIRY <= 0:
            raise ConfigError(
                f"无效的 HTTPX_KEEPALIVE_EXPIRY: {self.HTTPX_KEEPALIVE_EXPIRY}，必须大于 0"
            )

        # 批量查询内部并发上限（只影响上游请求）
        if self.BATCH_CONCURRENCY <= 0:
            raise ConfigError(f"无效的 BATCH_CONCURRENCY: {self.BATCH_CONCURRENCY}，必须大于 0")
    
    def get_server_address(self) -> str:
        """获取完整的服务器地址。"""
        return f"http://{self.SERVER_HOST}:{self.SERVER_PORT}"


def _init_config() -> Config:
    """初始化全局配置（带错误处理）。"""
    return Config(validate=ENV_MODE != "testing", env_mode=ENV_MODE)


# 只在非测试环境下初始化全局配置
config = _init_config()
