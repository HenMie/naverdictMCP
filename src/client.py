"""Naver 辞典 HTTP 客户端模块。

提供异步 HTTP 客户端，用于获取 Naver 辞典 API 数据。
"""

from typing import Any, Dict, Literal, Optional

import httpx

from .config import config
from .logger import logger

# 字典类型定义
DictType = Literal["ko-zh", "ko-en"]

# 字典类型到 Naver API 代码的映射
DICT_CODE_MAP = {
    "ko-zh": ("kozh", "zh_CN"),
    "ko-en": ("koen", "en"),
}


class ValidationError(Exception):
    """输入验证错误。"""
    pass


class NaverClientPool:
    """HTTP 客户端连接池单例。
    
    使用单例模式管理共享的 HTTP 连接池，提供连接复用以提升性能。
    """
    
    _instance: Optional["NaverClientPool"] = None
    _client: Optional[httpx.AsyncClient] = None
    
    def __new__(cls) -> "NaverClientPool":
        """确保只存在一个实例（单例模式）。"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            logger.debug("创建 NaverClientPool 单例实例")
        return cls._instance
    
    async def get_client(self) -> httpx.AsyncClient:
        """
        获取或创建共享的 HTTP 客户端。
        
        Returns:
            共享的 httpx.AsyncClient 实例
        """
        if self._client is None or self._client.is_closed:
            logger.info("创建新的 HTTP 客户端连接池")
            self._client = httpx.AsyncClient(
                timeout=config.HTTP_TIMEOUT,
                follow_redirects=True,
                limits=httpx.Limits(
                    max_keepalive_connections=20,
                    max_connections=100,
                    keepalive_expiry=30.0,
                ),
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json,*/*",
                    "Referer": "https://korean.dict.naver.com/",
                }
            )
        return self._client
    
    async def close(self) -> None:
        """关闭共享的客户端连接。"""
        if self._client and not self._client.is_closed:
            logger.info("关闭 HTTP 客户端连接池")
            await self._client.aclose()
            self._client = None


# 全局客户端连接池实例
client_pool = NaverClientPool()


class NaverClient:
    """Naver 辞典 API 异步客户端。
    
    使用连接池提供高效的 HTTP 请求能力。
    
    使用示例:
        async with NaverClient() as client:
            data = await client.search("안녕하세요", "ko-zh")
    """
    
    def __init__(self) -> None:
        """初始化客户端。"""
        self.client: Optional[httpx.AsyncClient] = None
        self.base_url = config.NAVER_BASE_URL
        self._use_pool = True  # 默认使用连接池
    
    async def __aenter__(self) -> "NaverClient":
        """异步上下文管理器入口。"""
        if self._use_pool:
            # 使用共享连接池
            self.client = await client_pool.get_client()
            logger.debug("使用共享连接池")
        else:
            # 创建独立客户端（用于测试）
            self.client = httpx.AsyncClient(
                timeout=config.HTTP_TIMEOUT,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json,*/*",
                    "Referer": "https://korean.dict.naver.com/",
                }
            )
            logger.debug("使用独立客户端连接")
        return self
    
    async def __aexit__(
        self, 
        exc_type: Optional[type], 
        exc_val: Optional[BaseException], 
        exc_tb: Optional[object]
    ) -> None:
        """异步上下文管理器出口。"""
        if not self._use_pool and self.client:
            # 只有非连接池模式才关闭客户端
            await self.client.aclose()
    
    async def search(self, word: str, dict_type: DictType = "ko-zh") -> Dict[str, Any]:
        """
        在指定字典中搜索单词。
        
        Args:
            word: 要搜索的单词
            dict_type: 字典类型（"ko-zh" 或 "ko-en"）
            
        Returns:
            API 返回的 JSON 响应（字典格式）
            
        Raises:
            RuntimeError: 客户端未初始化时抛出
            ValidationError: 输入验证失败时抛出
            httpx.HTTPStatusError: HTTP 请求失败时抛出
            httpx.TimeoutException: 请求超时时抛出
        """
        if not self.client:
            raise RuntimeError("客户端未初始化。请使用 'async with' 上下文管理器。")
        
        # 输入验证
        if not word:
            logger.warning("搜索词为空")
            raise ValidationError("搜索词不能为空")
        
        # 清理输入
        word = word.strip()
        
        if not word:
            logger.warning("搜索词清理后为空")
            raise ValidationError("搜索词不能只包含空格")
        
        if len(word) > 100:
            logger.warning(f"搜索词过长: {len(word)} 字符")
            raise ValidationError(f"搜索词过长（最大 100 字符，当前 {len(word)} 字符）")
        
        # 验证字典类型
        if dict_type not in DICT_CODE_MAP:
            logger.error(f"无效的字典类型: {dict_type}")
            raise ValidationError(f"无效的字典类型: {dict_type}，必须是 'ko-zh' 或 'ko-en'")
        
        logger.info(f"开始搜索: word='{word}', dict_type={dict_type}")
        
        dict_code, lang = DICT_CODE_MAP[dict_type]
        url = f"{self.base_url}/{dict_code}/search"
        
        params = {
            "query": word,
            "m": "mobile",
            "lang": lang,
            "shouldSearchVlive": "true"
        }
        
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            logger.debug(f"API 请求成功: {url}")
            return response.json()
        except httpx.TimeoutException:
            logger.error(f"请求超时: {url}", exc_info=True)
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP 错误 {e.response.status_code}: {url}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"未知错误: {e}", exc_info=True)
            raise
