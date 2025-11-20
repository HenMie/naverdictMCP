"""Configuration management for Naver Dictionary MCP server."""

import os
from typing import Literal
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Config:
    """Application configuration with environment variable support."""
    
    # Server settings
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))
    
    # HTTP client settings
    HTTP_TIMEOUT: float = float(os.getenv("HTTP_TIMEOUT", "30.0"))
    
    # Logging settings
    LOG_LEVEL: LogLevel = os.getenv("LOG_LEVEL", "INFO")  # type: ignore
    
    # Naver API settings
    NAVER_BASE_URL: str = os.getenv(
        "NAVER_BASE_URL", 
        "https://korean.dict.naver.com/api3"
    )
    
    @classmethod
    def get_server_address(cls) -> str:
        """Get the full server address."""
        return f"http://{cls.SERVER_HOST}:{cls.SERVER_PORT}"


# Global config instance
config = Config()
