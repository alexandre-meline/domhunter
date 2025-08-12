from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple, Optional, Dict, Any

import httpx

try:
    from waybackpy import WaybackMachineCDXServerAPI, WaybackMachineAvailabilityAPI
except ImportError:
    WaybackMachineCDXServerAPI = None  # type: ignore
    WaybackMachineAvailabilityAPI = None  # type: ignore

logger = logging.getLogger(__name__)


# =============================================================================
# Données
# =============================================================================
@dataclass
class SnapshotItem:
    timestamp: str
    original: str
    archive_url: str
    statuscode: Optional[str] = None
    mimetype: Optional[str] = None


# =============================================================================
# Outils internes
# =============================================================================
def _normalize_original(original: str) -> str:
    # Supprime le :80/ standardisé que Wayback renvoie parfois
    if original.startswith("http://") and original.endswith(":80/"):
        return original.replace(":80/", "/")
    return original


def _cdx_fetch_for_base(
    base_url: str,
    user_agent: str,
    limit: int,
    include_availability: bool = True,
    only_status_200: bool = True,
    accept_mimetypes: Optional[Iterable[str]] = ("text/html",),
) -> List[SnapshotItem]:
    """
    Fonction synchrone (exécutée dans un thread via asyncio.to_thread).
    Utilise waybackpy pour lister des snapshots pour une base (http/https/www).
    """
    if WaybackMachineCDXServerAPI is None:
        raise RuntimeError(
            "Le package 'waybackpy' n'est pas installé. Faites: pip install waybackpy"
        )

    results: List[SnapshotItem] = []

    cdx = WaybackMachineCDXServerAPI(
        url=base_url,
        user_agent=user_agent,
    )

    count = 0
    for snap in cdx.snapshots():
        ts = getattr(snap, "timestamp", None)
        original = getattr(snap, "original", None)
        statuscode = getattr(snap, "statuscode", None)
        mimetype = getattr(snap, "mimetype", None)
        archive_url = getattr(snap, "archive_url", None)

        if not (ts and original and archive_url):
            continue

        if only_status_200 and statuscode and statuscode != "200":
            continue

        if accept_mimetypes and mimetype:
            # Conserver uniquement si mimetype commence par un des types autorisés
            if not any(mimetype.startswith(acc) for acc in accept_mimetypes):
                continue

        original = _normalize_original(original)
        results.append(
            SnapshotItem(
                timestamp=ts,
                original=original,
                archive_url=archive_url,
                statuscode=statuscode,
                mimetype=mimetype,
            )
        )

        count += 1
        if count >= limit:
            break

    if include_availability and WaybackMachineAvailabilityAPI is not None:
        try:
            avail = WaybackMachineAvailabilityAPI(url=base_url, user_agent=user_agent)
            newest_url = avail.newest()
            # Format attendu: https://web.archive.org/web/<ts>/<original>
            if newest_url and "/web/" in newest_url:
                part = newest_url.split("/web/")[1]
                if "/" in part:
                    ts_part, original_part = part.split("/", 1)
                    if not any(s.timestamp == ts_part for s in results):
                        original_norm = original_part
                        if not original_norm.startswith(("http://", "https://")):
                            # Heuristique: si l'original archivédans newest_url commence par http(s), Wayback le pré fixe déjà
                            original_norm = "https://" + original_norm
                        original_norm = _normalize_original(original_norm)
                        results.append(
                            SnapshotItem(
                                timestamp=ts_part,
                                original=original_norm,
                                archive_url=newest_url,
                                statuscode="200",
                                mimetype="text/html",
                            )
                        )
        except Exception:
            # On ignore les erreurs d'Availability API
            pass

    return results


def _merge_and_dedupe(lists: Iterable[List[SnapshotItem]]) -> List[SnapshotItem]:
    seen = set()
    merged: List[SnapshotItem] = []
    for lst in lists:
        for s in lst:
            key = (s.timestamp, s.original)
            if key not in seen:
                seen.add(key)
                merged.append(s)
    # Tri descendant sur timestamp (lexicographiquement triable)
    merged.sort(key=lambda x: x.timestamp, reverse=True)
    return merged


# =============================================================================
# API publique
# =============================================================================
async def list_snapshots(
    client: httpx.AsyncClient,   # conservé pour compat signature (non utilisé ici)
    domain: str,
    limit: int = 50,
    user_agent: str = "domhunter/0.1 (+https://example.com)",
    include_variants: bool = True,
    include_availability: bool = True,
    only_status_200: bool = True,
    accept_mimetypes: Optional[Iterable[str]] = ("text/html",),
) -> List[Tuple[str, str]]:
    """
    Retourne une liste [(timestamp, original_url)] triée desc pour un domaine.
    Utilise waybackpy (synchrone) exécuté dans des threads.

    Rem: l'argument `client` est conservé pour compatibilité mais inutilisé
    car waybackpy encapsule ses propres requêtes.
    """
    base_patterns = [
        f"http://{domain}/",
        f"https://{domain}/",
    ]
    if include_variants:
        base_patterns.extend(
            [
                f"http://www.{domain}/",
                f"https://www.{domain}/",
            ]
        )

    tasks = [
        asyncio.to_thread(
            _cdx_fetch_for_base,
            base_url,
            user_agent,
            limit,
            include_availability,
            only_status_200,
            accept_mimetypes,
        )
        for base_url in base_patterns
    ]

    partials: List[List[SnapshotItem]] = []
    for fut in asyncio.as_completed(tasks):
        try:
            part = await fut
            partials.append(part)
        except Exception as e:
            logger.debug(f"Erreur Wayback (base fetch) domaine={domain}: {e}")

    merged = _merge_and_dedupe(partials)

    # Limitation globale
    if len(merged) > limit:
        merged = merged[:limit]

    return [(s.timestamp, s.original) for s in merged]


async def download_screenshots(  # Nom conservé pour compat pipeline, mais ne télécharge plus QUE du HTML
    client: httpx.AsyncClient,
    snapshots: List[Tuple[str, str]],
    out_dir: Path,
    max_count: int = 5,
    user_agent: str = "domhunter/0.1 (+https://example.com)",
    delay_seconds: float = 0.3,
    save_manifest: bool = True,
    overwrite: bool = False,
) -> int:
    """
    Télécharge uniquement le HTML archivé des snapshots (pas d'images / pas de /__wb/screenshot/).
    Sauvegarde chaque snapshot sous: <timestamp>.html
    Retourne le nombre de fichiers sûrs écrits.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": user_agent}
    subset = snapshots[:max_count]
    saved = 0
    manifest: List[Dict[str, Any]] = []

    logger.info(f"Téléchargement de {len(subset)} snapshot(s) vers {out_dir}")

    for idx, (ts, original) in enumerate(subset, 1):
        original_norm = _normalize_original(original)
        archive_url = f"https://web.archive.org/web/{ts}/{original_norm}"
        print(original_norm)
        target_file = out_dir / f"{ts}.html"

        if target_file.exists() and not overwrite:
            logger.debug(f"[{idx}/{len(subset)}] Déjà présent: {target_file.name} (skip)")
            manifest.append(
                {
                    "timestamp": ts,
                    "original": original_norm,
                    "archive_url": archive_url,
                    "saved": target_file.name,
                    "skipped": True,
                    "reason": "exists",
                }
            )
            continue

        try:
            resp = await client.get(
                archive_url, timeout=45, follow_redirects=True, headers=headers
            )
            ctype = resp.headers.get("content-type", "")
            logger.debug(
                f"[{idx}/{len(subset)}] {archive_url} -> {resp.status_code} {ctype}"
            )
            if resp.status_code == 200 and "text/html" in ctype:
                target_file.write_text(resp.text, encoding="utf-8")
                saved += 1
                manifest.append(
                    {
                        "timestamp": ts,
                        "original": original_norm,
                        "archive_url": archive_url,
                        "saved": target_file.name,
                        "status": resp.status_code,
                        "content_type": ctype,
                    }
                )
            else:
                manifest.append(
                    {
                        "timestamp": ts,
                        "original": original_norm,
                        "archive_url": archive_url,
                        "saved": None,
                        "status": resp.status_code,
                        "content_type": ctype,
                    }
                )
        except Exception as e:
            logger.debug(f"[{idx}/{len(subset)}] Erreur {archive_url}: {e}")
            manifest.append(
                {
                    "timestamp": ts,
                    "original": original_norm,
                    "archive_url": archive_url,
                    "saved": None,
                    "error": str(e),
                }
            )

        if delay_seconds:
            await asyncio.sleep(delay_seconds)

    if save_manifest and manifest:
        import json

        (out_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    logger.info(f"{saved} fichier(s) HTML sauvegardé(s) dans {out_dir}")
    return saved


# =============================================================================
# Alias optionnel si on veut un nom plus clair côté import futur
# =============================================================================
download_archives_html = download_screenshots