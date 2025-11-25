"""应用日志配置模块。

提供统一的日志配置和格式化。
"""

import logging
import sys
from typing import Optional


def setup_logger(
    name: str = "naver-dict-mcp",
    level: Optional[str] = None
) -> logging.Logger:
    """
    设置应用日志器，使用统一的格式。
    
    Args:
        name: 日志器名称
        level: 日志级别（如果提供则覆盖配置）
        
    Returns:
        配置好的日志器实例
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


# 全局日志器实例
logger = setup_logger()
