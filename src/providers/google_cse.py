from typing import Optional
import httpx


async def is_indexed(
    client: httpx.AsyncClient,
    api_key: str,
    cx: str,
    domain: str,
) -> Optional[bool]:
    """
    Utilise Google Custom Search API: True si totalResults > 0.
    """
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cx,
        "q": f"site:{domain}",
        "num": 1,
        "fields": "searchInformation(totalResults)",
    }
    try:
        r = await client.get(url, params=params, timeout=20)
        if r.status_code == 403:
            return None  # quota/auth error
        r.raise_for_status()
        data = r.json()
        total = int(data.get("searchInformation", {}).get("totalResults", "0"))
        return total > 0
    except Exception:
        return None