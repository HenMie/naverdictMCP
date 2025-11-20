"""HTTP client for fetching Naver Dictionary pages."""

import httpx
from typing import Literal, Dict, Any
from .config import config

DictType = Literal["ko-zh", "ko-en"]

# Mapping of our dict types to Naver's API codes
DICT_CODE_MAP = {
    "ko-zh": ("kozh", "zh_CN"),
    "ko-en": ("koen", "en"),
}


class NaverClient:
    """Async HTTP client for Naver Dictionary API."""
    
    def __init__(self):
        """Initialize the client."""
        self.client: httpx.AsyncClient | None = None
        self.base_url = config.NAVER_BASE_URL
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.client = httpx.AsyncClient(
            timeout=config.HTTP_TIMEOUT,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json,*/*",
                "Referer": "https://korean.dict.naver.com/",
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client:
            await self.client.aclose()
    
    async def search(self, word: str, dict_type: DictType = "ko-zh") -> Dict[str, Any]:
        """
        Search for a word in the specified dictionary.
        
        Args:
            word: The word to search for
            dict_type: Dictionary type ("ko-zh" or "ko-en")
            
        Returns:
            JSON response from the API as a dictionary
        """
        if not self.client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")
        
        dict_code, lang = DICT_CODE_MAP[dict_type]
        url = f"{self.base_url}/{dict_code}/search"
        
        params = {
            "query": word,
            "m": "mobile",
            "lang": lang,
            "shouldSearchVlive": "true"
        }
        
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        
        return response.json()
