import asyncio
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List

import httpx

from .models import DomainResult
from .utils import ensure_dir, write_csv, write_json
from .providers.internetbs import check_availability
from .providers.google_cse import is_indexed
from .providers.wayback import list_snapshots, download_screenshots


async def process_domain(
    domain: str,
    http_client: httpx.AsyncClient,
    keys: Dict[str, str],
    out_screens_dir: Path,
    max_screenshots: int,
    semaphore: asyncio.Semaphore,
) -> DomainResult:
    res = DomainResult(domain=domain)
    async with semaphore:
        res.available = await check_availability(
            http_client, domain, keys["INTERNETBS_API_KEY"], keys["INTERNETBS_PASSWORD"]
        )
        if res.available is not True:
            return res

        res.indexed_google = await is_indexed(
            http_client, keys["GOOGLE_API_KEY"], keys["GOOGLE_CX"], domain
        )
        if res.indexed_google is not True:
            return res

        try:
            snaps = await list_snapshots(http_client, domain, limit=50)
            if snaps:
                ddir = out_screens_dir / domain
                res.wayback_screenshots = await download_screenshots(
                    http_client, snaps, ddir, max_count=max_screenshots
                )
        except Exception as e:
            res.notes += f"Wayback error: {e}"
    return res


async def run(
    domains: List[str],
    out_dir: Path,
    keys: Dict[str, str],
    max_screenshots: int = 5,
    concurrency: int = 5,
) -> List[DomainResult]:
    ensure_dir(out_dir / "screenshots")
    timeout = httpx.Timeout(30.0)
    limits = httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        sem = asyncio.Semaphore(concurrency)
        tasks = [
            process_domain(d, client, keys, out_dir / "screenshots", max_screenshots, sem)
            for d in domains
        ]
        results = await asyncio.gather(*tasks)

    # write outputs
    write_json(out_dir / "results.json", [r.to_dict() for r in results])
    write_csv(out_dir / "results.csv", [r.to_dict() for r in results])
    return list(results)