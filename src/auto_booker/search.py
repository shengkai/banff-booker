"""Campground search and date selection on reservation.pc.gc.ca."""

from __future__ import annotations

import time
from datetime import date

from playwright.sync_api import Page
from rich.console import Console

from .config import Campground
from .notify import alert

console = Console()

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


def navigate_to_campground(
    page: Page,
    campground: Campground,
    check_in: date,
    check_out: date,
    party_size: int,
    equipment: str,
) -> bool:
    """Search for the campground and open its site list.

    Steps:
      1. Submit the search form (park, dates, party, equipment).
      2. Switch to list view.
      3. Return False immediately if "#ListView" shows "No Available Sites".
      4. Find the campground card labelled "Available" and click it.
      5. Wait for individual site buttons to appear, then return True.
    """
    console.print(
        f"[cyan]→ Searching:[/] {campground.name}  "
        f"({check_in} to {check_out}, {party_size} ppl, {equipment})"
    )

    try:
        # ------------------------------------------------------------------
        # 1. Home page
        # ------------------------------------------------------------------
        page.goto("https://reservation.pc.gc.ca/", wait_until="domcontentloaded", timeout=60_000)

        # Consent banner (may or may not appear)
        try:
            page.get_by_role("button", name="I Consent").click(timeout=3000)
            time.sleep(1)
        except Exception:
            pass

        # ------------------------------------------------------------------
        # 2. Park — mat-select dropdown (first arrow on the page)
        # ------------------------------------------------------------------
        page.locator(".mat-mdc-select-arrow > svg").first.click()
        page.get_by_role("option", name="Banff", exact=True).click()

        # ------------------------------------------------------------------
        # 3. Dates
        # ------------------------------------------------------------------
        arrival_month_long = check_in.strftime("%B")      # e.g. "July"
        departure_month_long = check_out.strftime("%B")

        console.print(
            f"[cyan]Setting dates:[/] {arrival_month_long} {check_in.day}"
            f" – {departure_month_long} {check_out.day}"
        )

        # Open arrival calendar
        page.get_by_role("textbox", name="Arrival").click()

        # Switch to month-year view (button label contains "Select to change view")
        page.get_by_role("button", name="Select to").click()

        # Pick arrival month
        page.get_by_role("button", name=arrival_month_long).click()

        # Pick arrival day  (label format: "July 3, 2026")
        page.get_by_role("button", name=f"{arrival_month_long} {check_in.day},").click()

        # Pick departure day (may need to navigate to next month)
        if arrival_month_long == departure_month_long:
            page.get_by_role(
                "button", name=f"{departure_month_long} {check_out.day},"
            ).click()
        else:
            try:
                page.get_by_role(
                    "button", name=f"{departure_month_long} {check_out.day},"
                ).click(timeout=2000)
            except Exception:
                page.locator("button.mat-calendar-next-button").click()
                page.get_by_role(
                    "button", name=f"{departure_month_long} {check_out.day},"
                ).click()

        # ------------------------------------------------------------------
        # 4. Party size
        # ------------------------------------------------------------------
        page.get_by_role("spinbutton", name="Party Size").click()
        page.get_by_role("spinbutton", name="Party Size").fill(str(party_size))

        # ------------------------------------------------------------------
        # 5. Equipment — second mat-select dropdown on the page
        # ------------------------------------------------------------------
        page.locator("div:nth-child(2) > .mat-mdc-select-arrow > svg").click()
        page.get_by_role("option", name=equipment).click()

        # ------------------------------------------------------------------
        # 6. Submit search
        # ------------------------------------------------------------------
        page.get_by_role("button", name="Search for availability").click()
        page.wait_for_load_state("domcontentloaded")

        # ------------------------------------------------------------------
        # 7. Switch to list view and wait for Angular to finish rendering cards
        # ------------------------------------------------------------------
        page.get_by_role("radio", name="List view of results").click()
        # Wait for the list container, then let the network settle so that the
        # async Angular card components finish rendering before we inspect them.
        page.wait_for_selector("#ListView", timeout=20_000)
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:
            pass  # networkidle may time-out on busy pages; proceed anyway

        # ------------------------------------------------------------------
        # 8. Find the campground card and click it.
        #
        # NOTE: "#ListView contains 'No Available Sites'" is NOT a reliable
        # signal — the e2e test itself asserts that text while Tunnel Mountain
        # is still listed as Available.  That string appears for *other*
        # campgrounds in the same list.  We look directly for our campground.
        # ------------------------------------------------------------------
        console.print(f"[cyan]Finding campground:[/] {campground.name}")

        campground_btn = page.get_by_role("button", name=f"Site {campground.name}")

        # Use wait_for() so we give the page time to populate the card rather
        # than checking exactly once with is_visible().
        try:
            campground_btn.first.wait_for(state="visible", timeout=20_000)
        except Exception:
            try:
                page.screenshot(path="list_view_debug.png")
                console.print("[dim]Screenshot saved: list_view_debug.png[/]")
            except Exception:
                pass
            console.print(
                f"[yellow]✗ Campground '{campground.name}' not found in list view.[/]"
            )
            return False

        # Confirm the card is marked Available before clicking
        card_label = page.get_by_label(f"Site {campground.name}")
        if card_label.count() > 0:
            label_text = card_label.first.text_content(timeout=3_000) or ""
            if "Available" not in label_text:
                console.print(
                    f"[yellow]✗ Campground '{campground.name}' is not marked Available.[/]"
                )
                return False

        campground_btn.first.click()

        # ------------------------------------------------------------------
        # 9. Wait for individual site/section buttons to appear.
        #    After clicking the campground card, section buttons appear, e.g.
        #    "Site A  Available".  The selector covers both section and
        #    individual site buttons (both carry aria-label with "Site " + "Available").
        # ------------------------------------------------------------------
        # Use has_text filter rather than a CSS aria-label attribute selector so
        # this works whether the accessible name comes from aria-label or inner text.
        page.locator("button", has_text="Available").first.wait_for(
            state="visible", timeout=20_000
        )
        console.print(f"[bold green]✓ Sites loaded for {campground.name}[/]")
        return True

    except Exception as e:
        console.print(f"[red]Navigation error: {e}[/]")
        try:
            page.screenshot(path="nav_error.png")
        except Exception:
            pass
        return False
