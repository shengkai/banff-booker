"""Site selection and booking flow on reservation.pc.gc.ca.

Flow (matching reservation.spec.ts):
  1. find_section()      — list section buttons like "Site A  Available"
  2. select_section()    — pick section containing preferred site, else first available
  3. find_site()         — list individual site buttons like "Site A49  Available"
  4. select_site()       — pick preferred site number, else first available
  5. reserve_site()      — click Reserve, Acknowledge, check checkbox, Confirm
  6. pause_before_payment() — alert user, keep browser open
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Locator, Page
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _available_buttons(page: Page, prefix: str) -> list[Locator]:
    """Return all visible role=button elements whose name starts with *prefix*
    and contains "Available"."""
    btns = page.get_by_role("button", name=prefix)
    result = []
    count = btns.count()
    for i in range(count):
        btn = btns.nth(i)
        label = btn.get_attribute("aria-label") or btn.text_content() or ""
        if "Available" in label and btn.is_visible():
            result.append(btn)
    return result


# ---------------------------------------------------------------------------
# Step 1 – sections
# ---------------------------------------------------------------------------

# Recognized section label prefixes (case-insensitive prefix match)
_SECTION_PREFIXES = ("site ", "loops", "loop ")


def _is_section_label(label: str) -> bool:
    """True if the label looks like a section/loop button (not an individual site).

    Section buttons:   "Site A  Available",  "Loops 22-27  Available"
    Individual sites:  "Site A49  Available"  (letter immediately followed by digits)
    """
    lower = label.lower()
    if not any(lower.startswith(p) for p in _SECTION_PREFIXES):
        return False
    # If it starts with "site " check whether the identifier has a digit —
    # "Site A  Available"  → no digit immediately → section
    # "Site A49  Available" → has digit → individual site (not a section)
    if lower.startswith("site "):
        import re
        identifier = label[5:].split()[0]  # e.g. "A" or "A49" or "Loops"
        if re.search(r'\d', identifier):
            return False  # looks like an individual site
    return True


def find_sections(page: Page) -> list[Locator]:
    """Return all section/loop buttons that contain available sites.

    Handles both naming conventions seen on Parks Canada:
        "Site A  Available"       (lettered loop)
        "Loops 22-27  Available"  (numbered loop at Two Jack Main, etc.)
    """
    all_btns = page.locator("button")
    sections: list[Locator] = []
    count = all_btns.count()
    for i in range(count):
        btn = all_btns.nth(i)
        try:
            label = (btn.get_attribute("aria-label") or btn.text_content() or "").strip()
            if "Available" in label and _is_section_label(label) and btn.is_visible():
                sections.append(btn)
        except Exception:
            continue
    return sections


def section_letter(locator: Locator) -> str:
    """Extract the section identifier from a button label.

    "Site A  Available"       → "A"
    "Site Loops 22-27  Available" → "Loops 22-27"
    """
    label = (locator.get_attribute("aria-label") or locator.text_content() or "").strip()
    # label = "Site A  Available" or "Site A49  Available"
    # Strip leading "Site " and trailing " Available" (or similar)
    part = label.removeprefix("Site ").strip()
    # Remove trailing availability text
    for suffix in ["Available", "Not Available", "Unavailable"]:
        part = part.replace(suffix, "").strip()
    return part


def select_section(
    page: Page,
    sections: list[Locator],
    preferred_sections: list[str],
    preferred_sites: list[str],
) -> Locator | None:
    """Choose a section to click.

    Priority:
      1. preferred_sections (explicit section names, e.g. "Loops 22-27", "A")
      2. section derived from preferred_sites letter prefix (e.g. "A21" → "A")
      3. First available section
    """
    if not sections:
        return None

    def _label(loc: Locator) -> str:
        return (loc.get_attribute("aria-label") or loc.inner_text() or "").strip()

    # 1. Explicit preferred sections (case-insensitive substring match)
    for pref in preferred_sections:
        for sec in sections:
            if pref.lower() in _label(sec).lower():
                console.print(f"[green]✓ Clicking preferred section: {_label(sec)}[/]")
                return sec

    # 2. Derive section letter from preferred site numbers (e.g. "A21" → "A")
    for pref in preferred_sites:
        pref_section = "".join(c for c in pref if c.isalpha()).upper()
        if not pref_section:
            continue
        for sec in sections:
            lbl = _label(sec)
            identifier = section_letter(sec)
            if identifier.upper() == pref_section:
                console.print(f"[green]✓ Clicking derived section: {lbl}[/]")
                return sec

    # 3. Fall back to first available section
    label = _label(sections[0])
    console.print(f"[yellow]Using first available section: {label}[/]")
    return sections[0]


# ---------------------------------------------------------------------------
# Step 2 – individual sites
# ---------------------------------------------------------------------------

@dataclass
class SiteEntry:
    """A bookable site with its display name and the Locator to click."""
    name: str
    locator: Locator


def _details_buttons(page: Page) -> list[Locator]:
    """Return all visible .btn-view-details elements (the reliable site indicator).

    In the Parks Canada Angular app the 'Details' affordance is a div with
    class 'btn-view-details', NOT a <button> element.
    """
    items = page.locator(".btn-view-details")
    count = items.count()
    return [items.nth(i) for i in range(count) if items.nth(i).is_visible()]


def find_sites(page: Page) -> list[SiteEntry]:
    """Return all bookable available sites using the real Angular DOM structure.

    From sites_example.html each site row is:
        <mat-expansion-panel data-resource="A50">
          <mat-expansion-panel-header role="button"
              aria-labelledby="resource-name-N availability-N">
            <h3 class="resource-name" id="resource-name-N">
              <span class="cdk-visually-hidden">Site</span> A50
            </h3>
            <div class="resource-availability">
              <span class="availability-label">Available</span>
            </div>
            <div class="btn-view-details" aria-label="select for details">Details</div>
          </mat-expansion-panel-header>
          <div class="mat-expansion-panel-body"><!-- Reserve button appears here --></div>
        </mat-expansion-panel>

    The site name comes from the data-resource attribute.
    The locator to click is mat-expansion-panel-header (which expands the panel).
    """
    sites: list[SiteEntry] = []
    seen: set[str] = set()

    panels = page.locator("mat-expansion-panel")
    count = panels.count()
    for i in range(count):
        panel = panels.nth(i)
        try:
            if not panel.is_visible():
                continue
            # Confirm this panel shows an available site
            avail_labels = panel.locator(".availability-label")
            avail_text = ""
            for j in range(avail_labels.count()):
                t = (avail_labels.nth(j).text_content(timeout=500) or "").strip()
                if t == "Available":
                    avail_text = t
                    break
            if avail_text != "Available":
                continue
            # Get site name from data-resource attribute (e.g. "A50")
            name = panel.get_attribute("data-resource") or ""
            if not name:
                # Fallback: read h3.resource-name inner text
                h3 = panel.locator("h3.resource-name")
                if h3.count() > 0:
                    name = (h3.first.inner_text(timeout=500) or "").strip()
                if not name:
                    name = f"Site {i+1}"
            if name in seen:
                continue
            seen.add(name)
            # Click target: mat-expansion-panel-header (the accordion row)
            header = panel.locator("mat-expansion-panel-header")
            if header.count() == 0:
                continue
            sites.append(SiteEntry(name=name, locator=header.first))
        except Exception:
            continue

    if sites:
        console.print(f"[dim]Found {len(sites)} site(s) via expansion panels[/]")
        return sites

    # Fallback: Pattern A — 'Site A49  Available' all-in-one buttons (Tunnel Mountain style)
    import re
    all_btns = page.locator("button")
    btn_count = all_btns.count()
    for i in range(btn_count):
        btn = all_btns.nth(i)
        try:
            label = (btn.get_attribute("aria-label") or btn.inner_text() or "").strip()
            if not ("Available" in label and label.startswith("Site ") and btn.is_visible()):
                continue
            identifier = label[5:].split()[0]
            if re.search(r'\d', identifier) and identifier not in seen:
                seen.add(identifier)
                sites.append(SiteEntry(name=identifier, locator=btn))
        except Exception:
            continue

    if sites:
        console.print(f"[dim]Found {len(sites)} site(s) via Site-label buttons (Pattern A)[/]")
    return sites


def select_site(
    page: Page,
    sites: list[SiteEntry],
    preferred_sites: list[str],
) -> SiteEntry | None:
    """Pick the preferred site or fall back to first available."""
    if not sites:
        return None

    for pref in preferred_sites:
        pref_upper = pref.strip().upper()
        for site in sites:
            if pref_upper in site.name.upper():
                console.print(f"[bold green]✓ Preferred site matched: {site.name}[/]")
                return site

    console.print(f"[yellow]Using first available site: {sites[0].name}[/]")
    return sites[0]


# ---------------------------------------------------------------------------
# Step 3 – reserve
# ---------------------------------------------------------------------------

def reserve_site(page: Page) -> bool:
    """Click Reserve → Acknowledge → check checkbox → Confirm reservation details.

    Returns True if the confirmation page loaded, False on error.
    """
    try:
        # 1. Click "Reserve" button (adds to cart)
        console.print("[cyan]Clicking Reserve...[/]")
        page.get_by_role("button", name="Reserve").click(timeout=10_000)
        time.sleep(1)

        # 2. Click "Acknowledge" dialog button (optional — only shown for some notifications)
        try:
            page.get_by_role("button", name="Acknowledge").click(timeout=4_000)
            console.print("[cyan]Acknowledged notification.[/]")
            time.sleep(1)
        except Exception:
            console.print("[dim]No Acknowledge dialog — continuing.[/]")

        # 3. Wait for the "Please read and acknowledge" heading
        page.get_by_role("heading", name="Please read and acknowledge").wait_for(
            state="visible", timeout=15_000
        )

        # 4. Check the "All reservation details are" checkbox
        page.get_by_role("checkbox", name="All reservation details are").check(timeout=5_000)

        # 5. Confirm reservation details
        console.print("[cyan]Confirming reservation details...[/]")
        page.get_by_role("button", name="Confirm reservation details").click(timeout=10_000)

        page.wait_for_load_state("domcontentloaded")
        console.print("[bold green]✓ Reservation details confirmed — proceeding to checkout.[/]")
        return True

    except Exception as e:
        console.print(f"[red]reserve_site error: {e}[/]")
        take_screenshot(page, "reserve_error")
        return False


# ---------------------------------------------------------------------------
# Step 4 – book (orchestrates steps 1–3)
# ---------------------------------------------------------------------------

def book_site(page: Page, preferred_sections: list[str], preferred_sites: list[str]) -> bool:
    """Full booking flow after navigate_to_campground() returned True.

    Uses "Details ▾" button presence as the definitive indicator of site level:
    - Details visible → already at site level, skip section selection
    - No Details → still at section level, pick and click a section first

    Args:
        preferred_sections: e.g. ["Loops 22-27"] or ["A"] from campground config.
        preferred_sites:    e.g. ["A21", "A22"] from the campground config.
    """
    console.rule("[bold cyan]Step 3 · Site Selection[/]")

    # --- check if we're already at site level (Details buttons visible) ---
    if not _details_buttons(page):
        # Still at section level — find and click the right section
        try:
            sections = find_sections(page)
        except Exception as e:
            console.print(f"[red]Could not list sections: {e}[/]")
            take_screenshot(page, "sections_error")
            return False

        if not sections:
            console.print("[red]No available sections found.[/]")
            take_screenshot(page, "no_sections")
            return False

        console.print(f"[green]Found {len(sections)} section(s)[/]")

        chosen_section = select_section(page, sections, preferred_sections, preferred_sites)
        if chosen_section is None:
            return False
        chosen_section.click()

        # Wait for .btn-view-details (site-level indicator) or Pattern A buttons
        try:
            page.locator(".btn-view-details").first.wait_for(
                state="visible", timeout=10_000
            )
        except Exception:
            # No .btn-view-details — may be Pattern A (Tunnel Mountain); press on
            pass
        time.sleep(1)

    # --- find sites (Details-button rows first, then Site-label buttons) ---
    sites = find_sites(page)
    if not sites:
        console.print("[red]No individual available sites found.[/]")
        take_screenshot(page, "no_sites")
        return False

    console.print(f"[green]Found {len(sites)} available site(s)[/]")

    # --- pick and click site ---
    chosen_site = select_site(page, sites, preferred_sites)
    if chosen_site is None:
        return False
    chosen_site.locator.click()

    # Wait for Reserve button to appear (Details click expands to show it)
    try:
        page.get_by_role("button", name="Reserve").wait_for(state="visible", timeout=8_000)
    except Exception:
        pass

    # --- reserve ---
    return reserve_site(page)


# ---------------------------------------------------------------------------
# Pause before payment
# ---------------------------------------------------------------------------

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

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        console.print("\n[dim]Exiting. Browser may remain open.[/]")
