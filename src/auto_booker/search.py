"""Campground search and date selection on reservation.pc.gc.ca."""

from __future__ import annotations

import time
from datetime import date

from playwright.sync_api import Page
from rich.console import Console

from .config import Campground
from .notify import alert

console = Console()

# Base URL pattern for Banff campgrounds
BANFF_SEARCH_URL = "https://reservation.pc.gc.ca/Banff"

# Queue / waiting-room indicators
_QUEUE_INDICATORS = [
    "text=waiting room",
    "text=salle d'attente",
    "text=Your estimated wait time",
    "text=you are in line",
    "#MainPart_lbWhich498702498702702702",  # queue-it widget
]


def detect_queue(page: Page) -> bool:
    """Return True if the page appears to be a virtual waiting room."""
    for sel in _QUEUE_INDICATORS:
        try:
            if page.locator(sel).first.is_visible(timeout=1000):
                return True
        except Exception:
            continue
    return False


def wait_through_queue(page: Page, timeout_minutes: int = 120) -> bool:
    """Wait until the user passes through the virtual queue.

    Returns True once through, False on timeout.
    """
    if not detect_queue(page):
        return True  # no queue active

    console.rule("[bold cyan]Step 2 · Queue[/]")
    console.print("[yellow]Virtual waiting room detected. Waiting...[/]\n")

    deadline = time.time() + timeout_minutes * 60
    while time.time() < deadline:
        if not detect_queue(page):
            console.print("[bold green]✓ Through the queue![/]")
            alert("Auto-Booker", "You are through the queue!", sound=True, desktop=True)
            return True
        time.sleep(3)

    console.print("[bold red]✗ Queue wait timed out.[/]")
    return False


def _format_date_for_url(d: date) -> str:
    """Format date as used in Parks Canada URL parameters."""
    return d.strftime("%Y-%m-%dT00:00:00.000Z")


def navigate_to_campground(
    page: Page,
    campground: Campground,
    check_in: date,
    check_out: date,
    party_size: int,
    equipment: str,
) -> bool:
    """Navigate to the campground search results page.

    Returns True if the page loaded successfully.
    """
    console.print(
        f"[cyan]→ Searching:[/] {campground.name}  "
        f"({check_in} to {check_out}, {party_size} ppl, {equipment})"
    )

    # Build the search URL with parameters
    # Parks Canada uses query params for search filters
    url = (
        f"https://reservation.pc.gc.ca/{campground.url_slug}"
        f"?mapId=-2147483535"
        f"&searchTabGroupId=0"
        f"&bookingCategoryId=0"
        f"&startDate={_format_date_for_url(check_in)}"
        f"&endDate={_format_date_for_url(check_out)}"
        f"&nights={(check_out - check_in).days}"
        f"&is498702702702702702702702=true"
        f"&partySize={party_size}"
    )

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        # Wait for results or error
        time.sleep(3)
        return True
    except Exception as e:
        console.print(f"[red]Navigation error: {e}[/]")
        return False
