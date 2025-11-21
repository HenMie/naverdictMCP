"""FastMCP server for Naver Dictionary."""

from fastmcp import FastMCP
import sys
import os
import json

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
        JSON formatted dictionary results including word, pronunciation, meanings, and examples
    """
    async with NaverClient() as client:
        data = await client.search(word, dict_type)
        results = parse_search_results(data)
        
        # Return JSON formatted results
        return json.dumps({
            "success": True,
            "word": word,
            "dict_type": dict_type,
            "count": len(results),
            "results": results
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def search_word(word: str, dict_type: DictType = "ko-zh") -> str:
    """
    Search for a word in Naver Dictionary.
    
    Args:
        word: The word to search for
        dict_type: Dictionary type - "ko-zh" for Korean-Chinese or "ko-en" for Korean-English
        
    Returns:
        JSON formatted string containing dictionary results with the following structure:
        {
            "success": true,
            "word": "searched word",
            "dict_type": "ko-zh or ko-en",
            "count": number of results,
            "results": [
                {
                    "word": "word/phrase",
                    "pronunciation": "pronunciation",
                    "meanings": ["meaning1", "meaning2", ...],
                    "examples": ["example1", "example2", ...]
                },
                ...
            ]
        }
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
