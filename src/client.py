"""HTTP client for fetching Naver Dictionary pages."""

import httpx
from typing import Literal, Dict, Any, Optional
from .config import config
from .logger import logger

DictType = Literal["ko-zh", "ko-en"]

# Mapping of our dict types to Naver's API codes
DICT_CODE_MAP = {
    "ko-zh": ("kozh", "zh_CN"),
    "ko-en": ("koen", "en"),
}


class ValidationError(Exception):
    """Input validation error."""
    pass


class NaverClientPool:
    """Singleton HTTP client pool for connection reuse."""
    
    _instance: Optional["NaverClientPool"] = None
    _client: Optional[httpx.AsyncClient] = None
    _ref_count: int = 0
    
    def __new__(cls):
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            logger.debug("创建 NaverClientPool 单例实例")
        return cls._instance
    
    async def get_client(self) -> httpx.AsyncClient:
        """
        Get or create shared HTTP client.
        
        Returns:
            Shared httpx.AsyncClient instance
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
        """Close the shared client."""
        if self._client and not self._client.is_closed:
            logger.info("关闭 HTTP 客户端连接池")
            await self._client.aclose()
            self._client = None


# Global client pool instance
client_pool = NaverClientPool()


class NaverClient:
    """Async HTTP client for Naver Dictionary API using connection pool."""
    
    def __init__(self):
        """Initialize the client."""
        self.client: httpx.AsyncClient | None = None
        self.base_url = config.NAVER_BASE_URL
        self._use_pool = True  # Use connection pool by default
    
    async def __aenter__(self):
        """Async context manager entry."""
        if self._use_pool:
            # Use shared connection pool
            self.client = await client_pool.get_client()
            logger.debug("使用共享连接池")
        else:
            # Create dedicated client (for testing)
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
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if not self._use_pool and self.client:
            # Only close if not using pool
            await self.client.aclose()
    
    async def search(self, word: str, dict_type: DictType = "ko-zh") -> Dict[str, Any]:
        """
        Search for a word in the specified dictionary.
        
        Args:
            word: The word to search for
            dict_type: Dictionary type ("ko-zh" or "ko-en")
            
        Returns:
            JSON response from the API as a dictionary
            
        Raises:
            RuntimeError: If client not initialized
            ValidationError: If input validation fails
            httpx.HTTPStatusError: If HTTP request fails
            httpx.TimeoutException: If request times out
        """
        if not self.client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")
        
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
        except httpx.TimeoutException as e:
            logger.error(f"请求超时: {url}", exc_info=True)
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP 错误 {e.response.status_code}: {url}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"未知错误: {e}", exc_info=True)
            raise
