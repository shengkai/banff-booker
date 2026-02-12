"""Site selection and booking form filling."""

from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import Page
from rich.console import Console

from .notify import alert

console = Console()

SCREENSHOT_DIR = Path.home() / ".auto-booker" / "screenshots"


def take_screenshot(page: Page, name: str) -> Path:
    """Save a screenshot for debugging."""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOT_DIR / f"{name}.png"
    page.screenshot(path=str(path))
    console.print(f"[dim]Screenshot saved: {path}[/]")
    return path


def find_available_sites(page: Page) -> list[dict]:
    """Parse the search results page for available campsites.

    Returns a list of dicts with keys: name, element (Playwright locator).
    """
    sites: list[dict] = []
    try:
        # Look for availability result items / book buttons
        # The exact selectors depend on the current reservation.pc.gc.ca DOM
        book_buttons = page.locator('button:has-text("Book"), a:has-text("Book")')
        count = book_buttons.count()
        console.print(f"[green]Found {count} available site(s)[/]")

        for i in range(count):
            btn = book_buttons.nth(i)
            # Try to extract a site name from nearby elements
            parent = btn.locator('xpath=ancestor::div[contains(@class,"result") or contains(@class,"site")]').first
            try:
                name = parent.locator("h3, h4, .site-name, .resource-name").first.inner_text(timeout=1000)
            except Exception:
                name = f"Site {i + 1}"
            sites.append({"name": name.strip(), "button": btn})
    except Exception as e:
        console.print(f"[red]Error parsing sites: {e}[/]")

    return sites


def select_site(
    page: Page,
    available: list[dict],
    preferred: list[str],
) -> dict | None:
    """Pick a site — try preferred list first, then fall back to any available."""
    if not available:
        return None

    # Try preferred sites first
    for pref in preferred:
        for site in available:
            if pref.lower() in site["name"].lower():
                console.print(f"[bold green]✓ Preferred site matched: {site['name']}[/]")
                return site

    # Fall back to first available
    chosen = available[0]
    console.print(f"[yellow]Using first available site: {chosen['name']}[/]")
    return chosen


def click_book(page: Page, site: dict) -> bool:
    """Click the Book button for the selected site."""
    try:
        site["button"].click(timeout=5000)
        time.sleep(2)
        return True
    except Exception as e:
        console.print(f"[red]Failed to click Book: {e}[/]")
        return False


def fill_booking_form(page: Page, party_size: int, equipment: str) -> bool:
    """Fill out the booking details form (party size, equipment, etc.).

    This is a best-effort attempt — the exact form fields depend on the
    current reservation.pc.gc.ca DOM structure, which changes periodically.
    """
    console.print("[cyan]Filling booking form...[/]")
    try:
        # Try to fill party size if a field exists
        party_input = page.locator('input[name*="party"], select[name*="party"], #partySize')
        if party_input.count() > 0:
            first = party_input.first
            tag = first.evaluate("el => el.tagName.toLowerCase()")
            if tag == "select":
                first.select_option(str(party_size))
            else:
                first.fill(str(party_size))

        # Try to select equipment type if a dropdown exists
        equip_select = page.locator('select[name*="equip"], select[name*="Equipment"]')
        if equip_select.count() > 0:
            try:
                equip_select.first.select_option(label=equipment.capitalize())
            except Exception:
                equip_select.first.select_option(index=0)

        # Accept any terms/conditions checkboxes
        checkboxes = page.locator('input[type="checkbox"][name*="agree"], input[type="checkbox"][name*="terms"]')
        for i in range(checkboxes.count()):
            if not checkboxes.nth(i).is_checked():
                checkboxes.nth(i).check()

        time.sleep(1)
        return True
    except Exception as e:
        console.print(f"[red]Error filling form: {e}[/]")
        take_screenshot(page, "form_error")
        return False


def advance_to_checkout(page: Page) -> bool:
    """Click through to the checkout / payment page.

    Stops BEFORE submitting payment so the user can review.
    """
    try:
        # Look for "Continue", "Proceed", or "Checkout" buttons
        for label in ["Continue", "Proceed", "Checkout", "Next", "Continuer"]:
            btn = page.locator(f'button:has-text("{label}"), a:has-text("{label}")')
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click(timeout=5000)
                time.sleep(2)
                break
        return True
    except Exception as e:
        console.print(f"[red]Error advancing to checkout: {e}[/]")
        take_screenshot(page, "checkout_error")
        return False


def pause_before_payment(page: Page) -> None:
    """Alert the user and pause before final payment submission."""
    console.rule("[bold green]Step 4 · Review & Pay[/]")
    console.print(
        "\n[bold yellow]⚠  PAUSED — Review the booking in the browser window.[/]\n"
        "[yellow]Complete the payment manually when ready.[/]\n"
        "[dim]The browser will stay open. Press Ctrl+C in the terminal to exit.[/]\n"
    )
    alert("Auto-Booker", "Booking ready for payment! Review now.", sound=True, desktop=True)

    take_screenshot(page, "pre_payment")

    # Keep the script alive so the browser stays open
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        console.print("\n[dim]Exiting. Browser may remain open.[/]")
