"""Debug the actual API response structure."""

import asyncio
import json
from src.client import NaverClient


async def debug_structure():
    """Print the actual structure of API response."""
    async with NaverClient() as client:
        word = "안녕"
        dict_type = "ko-zh"
        
        print(f"Fetching: {word} ({dict_type})")
        data = await client.search(word, dict_type)
        
        # Save to file for inspection
        with open("api_response.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"Saved full response to api_response.json")
        
        # Print structure
        print(f"\nTop-level keys: {list(data.keys())}")
        
        # Check searchResultMap
        if "searchResultMap" in data:
            print(f"\nsearchResultMap keys: {list(data['searchResultMap'].keys())}")
            for key in data['searchResultMap']:
                results = data['searchResultMap'][key]
                if isinstance(results, list) and len(results) > 0:
                    print(f"\n{key} has {len(results)} results")
                    print(f"First result keys: {list(results[0].keys())}")
                    print(f"\nFirst result sample:")
                    print(json.dumps(results[0], ensure_ascii=False, indent=2)[:1000])


if __name__ == "__main__":
    asyncio.run(debug_structure())
