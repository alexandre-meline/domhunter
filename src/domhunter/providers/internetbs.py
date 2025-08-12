from typing import Optional
import httpx


async def check_availability(
    client: httpx.AsyncClient,
    domain: str,
    api_key: str,
    password: str,
) -> Optional[bool]:
    """
    Retourne True si disponible, False si non, None si indéterminé/erreur.
    """
    url = "https://api.internet.bs/Domain/Check"
    params = {
        "ApiKey": api_key,
        "Password": password,
        "Domain": domain,
        "ResponseFormat": "JSON",
    }
    try:
        r = await client.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        status = data.get("status", "").lower()
        # Heuristique tolérante selon variantes de réponses
        if status == "available":
            return True
        if status == "unavailable":
            return False
        # Fallback
        return None
    except Exception:
        return None