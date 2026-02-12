"""Authentication flow — manual GCKey login with polling."""

from __future__ import annotations

import time

from playwright.sync_api import Page
from rich.console import Console

from .browser import RESERVATION_URL
from .notify import alert

console = Console()

# Indicators that the user is logged in
_LOGGED_IN_SELECTORS = [
    "text=Sign Out",
    "text=My Account",
    "text=Déconnexion",        # French variant
]


def is_logged_in(page: Page) -> bool:
    """Check whether the user appears to be signed in."""
    for sel in _LOGGED_IN_SELECTORS:
        try:
            if page.locator(sel).first.is_visible(timeout=500):
                return True
        except Exception:
            continue
    return False


def wait_for_login(page: Page, timeout_minutes: int = 15) -> bool:
    """Navigate to the reservation site and wait for the user to log in manually.

    Returns True once logged in, False on timeout.
    """
    console.rule("[bold cyan]Step 1 · Log In[/]")
    page.goto(RESERVATION_URL)
    console.print(
        "\n[yellow]Please log in manually using GCKey in the browser window.[/]\n"
        "The script will detect your login and continue automatically.\n"
    )

    deadline = time.time() + timeout_minutes * 60
    while time.time() < deadline:
        if is_logged_in(page):
            console.print("[bold green]✓ Login detected![/]")
            alert("Auto-Booker", "Login successful", sound=True, desktop=True)
            return True
        time.sleep(2)

    console.print("[bold red]✗ Login timed out.[/]")
    return False
