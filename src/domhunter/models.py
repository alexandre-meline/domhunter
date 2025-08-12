from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


@dataclass
class DomainResult:
    domain: str
    available: Optional[bool] = None
    indexed_google: Optional[bool] = None
    wayback_screenshots: int = 0
    wayback_html_pages: int = 0  # Nouveau champ
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)