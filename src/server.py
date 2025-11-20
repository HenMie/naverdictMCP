"""FastMCP server for Naver Dictionary."""

from fastmcp import FastMCP
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.client import NaverClient, DictType
from src.parser import parse_search_results, format_results
from src.config import config

# Initialize FastMCP server
mcp = FastMCP("Naver Dictionary")


async def _search_word_impl(word: str, dict_type: DictType = "ko-zh") -> str:
    """
    Core implementation of word search functionality.
    
    Args:
        word: The word to search for
        dict_type: Dictionary type - "ko-zh" for Korean-Chinese or "ko-en" for Korean-English
        
    Returns:
        Formatted dictionary results including word, pronunciation, meanings, and examples
    """
    async with NaverClient() as client:
        data = await client.search(word, dict_type)
        results = parse_search_results(data)
        return format_results(results)


@mcp.tool()
async def search_word(word: str, dict_type: DictType = "ko-zh") -> str:
    """
    Search for a word in Naver Dictionary.
    
    Args:
        word: The word to search for
        dict_type: Dictionary type - "ko-zh" for Korean-Chinese or "ko-en" for Korean-English
        
    Returns:
        Formatted dictionary results including word, pronunciation, meanings, and examples
    """
    return await _search_word_impl(word, dict_type)


if __name__ == "__main__":
    # Run the MCP server in HTTP mode
    print(f"Starting Naver Dictionary MCP server on {config.get_server_address()}")
    print(f"Log level: {config.LOG_LEVEL}")
    mcp.run(
        transport="streamable-http",
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        stateless_http=True
    )
