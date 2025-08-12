from typing import List, Tuple
from pathlib import Path
import httpx


async def list_snapshots(
    client: httpx.AsyncClient,
    domain: str,
    limit: int = 50
) -> List[Tuple[str, str]]:
    bases = [
        f"http://{domain}/",
        f"https://{domain}/",
        f"http://www.{domain}/",
        f"https://www.{domain}/",
    ]
    rows: List[Tuple[str, str]] = []
    for base in bases:
        try:
            url = "https://web.archive.org/cdx/search/cdx"
            params = {
                "url": base,
                "output": "json",
                "fl": "timestamp,original,statuscode,mimetype",
                "filter": "statuscode:200",
                "collapse": "timestamp:8",
                "limit": str(limit),
            }
            r = await client.get(url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            start_idx = 1 if data and data[0] and data[0][0] == "timestamp" else 0
            for row in data[start_idx:]:
                if len(row) >= 2:
                    rows.append((row[0], row[1]))
        except Exception:
            continue
    # unique + tri desc par timestamp
    seen = set()
    uniq: List[Tuple[str, str]] = []
    for ts, original in rows:
        if (ts, original) not in seen:
            seen.add((ts, original))
            uniq.append((ts, original))
    uniq.sort(key=lambda x: x[0], reverse=True)
    return uniq


async def download_screenshots(
    client: httpx.AsyncClient,
    snapshots: List[Tuple[str, str]],
    out_dir: Path,
    max_count: int = 5,
) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    for ts, original in snapshots[:max_count]:
        shot_url = f"https://web.archive.org/__wb/screenshot/{ts}/{original}"
        try:
            r = await client.get(shot_url, timeout=60)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
                ext = ".png" if "png" in r.headers.get("content-type", "") else ".jpg"
                (out_dir / f"{ts}{ext}").write_bytes(r.content)
                saved += 1
        except Exception:
            continue
    return saved