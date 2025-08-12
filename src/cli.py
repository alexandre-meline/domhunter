import os
import sys
import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv

from .utils import read_domains_file
from .pipeline import run


def parse_args(argv):
    p = argparse.ArgumentParser(description="Domain availability + indexation + wayback screenshots")
    p.add_argument("--domains", required=True, help="Fichier texte avec un domaine par ligne")
    p.add_argument("--out", default="output", help="Dossier de sortie")
    p.add_argument("--max-screenshots", type=int, default=5, help="Max screenshots par domaine")
    p.add_argument("--concurrency", type=int, default=5, help="Nb de domaines traités en parallèle")
    return p.parse_args(argv)


def main():
    ns = parse_args(sys.argv[1:])
    load_dotenv()

    keys = {
        "INTERNETBS_API_KEY": os.getenv("INTERNETBS_API_KEY", "").strip(),
        "INTERNETBS_PASSWORD": os.getenv("INTERNETBS_PASSWORD", "").strip(),
        "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY", "").strip(),
        "GOOGLE_CX": os.getenv("GOOGLE_CX", "").strip(),
    }
    missing = [k for k, v in keys.items() if not v]
    if missing:
        print(f"Variables manquantes dans .env: {', '.join(missing)}", file=sys.stderr)
        sys.exit(2)

    domains_path = Path(ns.domains)
    if not domains_path.exists():
        print(f"Fichier introuvable: {domains_path}", file=sys.stderr)
        sys.exit(1)

    domains = read_domains_file(domains_path)
    if not domains:
        print("Aucun domaine valide trouvé dans le fichier.", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(ns.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        asyncio.run(run(
            domains=domains,
            out_dir=out_dir,
            keys=keys,
            max_screenshots=ns.max_screenshots,
            concurrency=ns.concurrency,
        ))
    except KeyboardInterrupt:
        sys.exit(130)