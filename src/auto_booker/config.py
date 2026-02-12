"""Load and validate YAML configuration."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class Campground:
    name: str
    url_slug: str


@dataclass
class Dates:
    check_in: date
    check_out: date
    flexible_days: int = 0

    def date_variants(self) -> list[tuple[date, date]]:
        """Return (check_in, check_out) pairs in priority order, starting with
        the exact dates, then shifting by +/- 1, +/- 2, etc."""
        variants: list[tuple[date, date]] = [(self.check_in, self.check_out)]
        stay = (self.check_out - self.check_in).days
        for offset in range(1, self.flexible_days + 1):
            for sign in (1, -1):
                ci = self.check_in + timedelta(days=offset * sign)
                variants.append((ci, ci + timedelta(days=stay)))
        return variants


@dataclass
class Party:
    size: int = 2
    equipment: str = "tent"


@dataclass
class Notifications:
    sound: bool = True
    desktop: bool = True


@dataclass
class Config:
    campgrounds: list[Campground] = field(default_factory=list)
    dates: Dates = field(default_factory=lambda: Dates(date.today(), date.today()))
    party: Party = field(default_factory=Party)
    preferred_sites: list[str] = field(default_factory=list)
    notifications: Notifications = field(default_factory=Notifications)


def load_config(path: str | Path) -> Config:
    """Load configuration from a YAML file."""
    p = Path(path)
    if not p.exists():
        print(f"[error] Config file not found: {p}", file=sys.stderr)
        sys.exit(1)

    with open(p) as f:
        raw = yaml.safe_load(f)

    campgrounds = [
        Campground(name=c["name"], url_slug=c["url_slug"])
        for c in raw.get("campgrounds", [])
    ]

    d = raw.get("dates", {})
    dates = Dates(
        check_in=date.fromisoformat(str(d["check_in"])),
        check_out=date.fromisoformat(str(d["check_out"])),
        flexible_days=int(d.get("flexible_days", 0)),
    )

    p_raw = raw.get("party", {})
    party = Party(
        size=int(p_raw.get("size", 2)),
        equipment=str(p_raw.get("equipment", "tent")),
    )

    n = raw.get("notifications", {})
    notifications = Notifications(
        sound=bool(n.get("sound", True)),
        desktop=bool(n.get("desktop", True)),
    )

    return Config(
        campgrounds=campgrounds,
        dates=dates,
        party=party,
        preferred_sites=raw.get("preferred_sites", []),
        notifications=notifications,
    )
