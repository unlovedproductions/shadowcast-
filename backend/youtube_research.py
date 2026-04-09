
import httpx
import re
import asyncio
import json

async def _fetch_suggestions(query: str) -> list[str]:
    """Fetches autocomplete suggestions from YouTube Suggest API."""
    url = f"https://suggestqueries.google.com/complete/search?client=youtube&ds=yt&q={query}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=5)
            response.raise_for_status()  # Raise an exception for HTTP errors
            # The response is not standard JSON, it's a JavaScript function call.
            # We need to extract the JSON part.
            match = re.search(r'window\.google\.ac\.h\((.*)\)', response.text)
            if match:
                json_str = match.group(1)
                data = json.loads(json_str)
                # The suggestions are usually in the second element of the main list
                # and then the first element of each sublist.
                suggestions = [item[0] for item in data[1]]
                return suggestions
            else:
                return []
    except httpx.RequestError as e:
        print(f"HTTP request failed for query '{query}': {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"JSON decode error for query '{query}': {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred for query '{query}': {e}")
        return []

async def research_youtube_keywords(query: str) -> dict:
    """
    Performs YouTube keyword and topic research using free autocomplete methods.
    """
    autocomplete_suggestions = await _fetch_suggestions(query)

    long_tail_keywords = set()
    for char_code in range(ord('a'), ord('z') + 1):
        char = chr(char_code)
        suggestions = await _fetch_suggestions(f"{query} {char}")
        long_tail_keywords.update(suggestions)

    question_prefixes = ["how to", "what is", "best", "vs", "review"]
    question_keywords = set()
    for prefix in question_prefixes:
        suggestions = await _fetch_suggestions(f"{prefix} {query}")
        question_keywords.update(suggestions)

    # Combine all suggestions for title and tag generation
    all_suggestions = list(autocomplete_suggestions) + list(long_tail_keywords) + list(question_keywords)
    all_suggestions = list(set(all_suggestions)) # Remove duplicates

    # Generate recommended titles (simple heuristic: pick top 5 unique suggestions)
    recommended_titles = all_suggestions[:5]
    if len(recommended_titles) < 5 and autocomplete_suggestions:
        # If not enough unique suggestions, try to fill from autocomplete
        for suggestion in autocomplete_suggestions:
            if suggestion not in recommended_titles:
                recommended_titles.append(suggestion)
            if len(recommended_titles) == 5:
                break
    # Ensure at least one title if possible
    if not recommended_titles and autocomplete_suggestions:
        recommended_titles.append(autocomplete_suggestions[0])
    elif not recommended_titles:
        recommended_titles.append(f"Top 5 {query} Videos") # Fallback title

    # Generate recommended tags (top 20 unique suggestions, prioritizing shorter ones)
    # Sort by length to prioritize shorter, more general tags first, then take top 20
    recommended_tags = sorted(all_suggestions, key=len)[:20]

    return {
        "autocomplete_suggestions": autocomplete_suggestions,
        "long_tail_keywords": list(long_tail_keywords),
        "question_keywords": list(question_keywords),
        "recommended_titles": recommended_titles,
        "recommended_tags": recommended_tags,
    }

if __name__ == "__main__":
    async def main():
        test_query = "faceless affiliate marketing"
        print(f"\nResearching keywords for: '{test_query}'")
        results = await research_youtube_keywords(test_query)
        for key, value in results.items():
            print(f"\n{key.replace('_', ' ').title()}:")
            for item in value:
                print(f"- {item}")

    asyncio.run(main())
