"""Logging configuration for the application."""

import logging
import sys
from typing import Optional


def setup_logger(
    name: str = "naver-dict-mcp",
    level: Optional[str] = None
) -> logging.Logger:
    """
    Setup application logger with consistent formatting.
    
    Args:
        name: Logger name
        level: Log level (overrides config if provided)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # 避免重复添加 handler
    if logger.handlers:
        return logger
    
    # 延迟导入避免循环依赖
    if level is None:
        from .config import config
        level = config.LOG_LEVEL
    
    # 设置日志级别
    logger.setLevel(getattr(logging, level, logging.INFO))
    
    # 创建 handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level, logging.INFO))
    
    # 创建 formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    return logger


# 全局 logger 实例
logger = setup_logger()


