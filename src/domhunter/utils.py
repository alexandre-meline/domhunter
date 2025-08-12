import csv
import json
import re
from pathlib import Path
from typing import List, Optional

DOMAIN_RE = re.compile(r"^[a-z0-9.-]+$")


def normalize_domain(raw: str) -> Optional[str]:
    d = raw.strip().lower()
    if not d:
        return None
    # enlever schéma et paths éventuels
    d = re.sub(r"^https?://", "", d)
    d = d.split("/")[0].strip()
    try:
        d = d.encode("idna").decode("ascii")
    except Exception:
        return None
    d = d.rstrip(".")
    if not DOMAIN_RE.match(d):
        return None
    return d or None


def read_domains_file(path: Path) -> List[str]:
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        n = normalize_domain(line)
        if n:
            items.append(n)
    return sorted(set(items))


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: List[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)