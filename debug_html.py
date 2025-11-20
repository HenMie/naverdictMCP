"""Debug script to inspect Naver Dictionary HTML structure."""

import asyncio
from src.client import NaverClient


async def inspect_html():
    """Fetch and save HTML for inspection."""
    async with NaverClient() as client:
        word = "안녕하세요"
        dict_type = "ko-zh"
        
        print(f"Fetching: {word} ({dict_type})")
        html = await client.search(word, dict_type)
        
        # Save HTML to file
        with open("debug_output.html", "w", encoding="utf-8") as f:
            f.write(html)
        
        print(f"Saved HTML to debug_output.html ({len(html)} characters)")
        
        # Print first 2000 characters
        print("\nFirst 2000 characters:")
        print("=" * 60)
        print(html[:2000])


if __name__ == "__main__":
    asyncio.run(inspect_html())
