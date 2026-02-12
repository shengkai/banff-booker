"""
Full project setup: Creates all source files for the auto-booker project.
Run once:  python setup_project.py
Then:      pip install -e . && playwright install chromium
"""
import os
import textwrap

BASE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Directory structure
# ---------------------------------------------------------------------------
for d in ["src/auto_booker", "tests", ".github"]:
    os.makedirs(os.path.join(BASE, d), exist_ok=True)

# ---------------------------------------------------------------------------
# File contents
# ---------------------------------------------------------------------------
FILES = {}

# -- src/auto_booker/__init__.py ---------------------------------------------
FILES["src/auto_booker/__init__.py"] = textwrap.dedent('''\
    """Banff National Park Campsite Auto-Booker."""

    __version__ = "0.1.0"
''')

# -- src/auto_booker/config.py -----------------------------------------------
FILES["src/auto_booker/config.py"] = textwrap.dedent('''\
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
''')

# -- src/auto_booker/notify.py ------------------------------------------------
FILES["src/auto_booker/notify.py"] = textwrap.dedent('''\
    """Notification helpers — sound alerts and desktop notifications."""

    from __future__ import annotations

    import sys
    import subprocess
    from pathlib import Path


    def beep(times: int = 3) -> None:
        """Play a terminal bell / system beep."""
        for _ in range(times):
            sys.stdout.write("\\a")
            sys.stdout.flush()


    def play_sound() -> None:
        """Play an alert sound (Windows-specific, falls back to beep)."""
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            beep()


    def desktop_notify(title: str, message: str) -> None:
        """Show a Windows toast notification (best-effort)."""
        try:
            # Use PowerShell toast notification on Windows
            ps_script = (
                "[Windows.UI.Notifications.ToastNotificationManager, "
                "Windows.UI.Notifications, ContentType = WindowsRuntime] > $null; "
                "$xml = [Windows.UI.Notifications.ToastNotificationManager]"
                "::GetTemplateContent("
                "[Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
                '$text = $xml.GetElementsByTagName("text"); '
                f'$text[0].AppendChild($xml.CreateTextNode("{title}")) > $null; '
                f'$text[1].AppendChild($xml.CreateTextNode("{message}")) > $null; '
                "$toast = [Windows.UI.Notifications.ToastNotification]::new($xml); "
                '[Windows.UI.Notifications.ToastNotificationManager]'
                '::CreateToastNotifier("AutoBooker").Show($toast)'
            )
            subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, timeout=5,
            )
        except Exception:
            # Fallback: just beep
            beep(1)


    def alert(title: str, message: str, *, sound: bool = True, desktop: bool = True) -> None:
        """Fire both sound and desktop notification."""
        if sound:
            play_sound()
        if desktop:
            desktop_notify(title, message)
''')

# -- src/auto_booker/browser.py -----------------------------------------------
FILES["src/auto_booker/browser.py"] = textwrap.dedent('''\
    """Playwright browser session management."""

    from __future__ import annotations

    from pathlib import Path
    from playwright.sync_api import sync_playwright, Playwright, Browser, BrowserContext, Page

    # Persistent profile directory for cookies / session state
    PROFILE_DIR = Path.home() / ".auto-booker" / "browser-profile"

    RESERVATION_URL = "https://reservation.pc.gc.ca/"


    class BrowserSession:
        """Manages a headed Chromium browser with a persistent profile."""

        def __init__(self) -> None:
            self._pw: Playwright | None = None
            self._context: BrowserContext | None = None
            self.page: Page | None = None

        def launch(self) -> Page:
            """Launch browser and return the main page."""
            PROFILE_DIR.mkdir(parents=True, exist_ok=True)
            self._pw = sync_playwright().start()

            self._context = self._pw.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_DIR),
                headless=False,
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                args=[
                    "--disable-blink-features=AutomationControlled",
                ],
            )

            # Apply stealth patches
            try:
                from playwright_stealth import stealth_sync
                for p in self._context.pages:
                    stealth_sync(p)
                self._context.on("page", lambda p: stealth_sync(p))
            except ImportError:
                pass  # stealth plugin not installed, continue without

            self.page = self._context.pages[0] if self._context.pages else self._context.new_page()
            return self.page

        def close(self) -> None:
            """Close browser and playwright."""
            if self._context:
                self._context.close()
            if self._pw:
                self._pw.stop()

        def __enter__(self) -> "BrowserSession":
            self.launch()
            return self

        def __exit__(self, *args) -> None:
            self.close()
''')

# -- src/auto_booker/auth.py --------------------------------------------------
FILES["src/auto_booker/auth.py"] = textwrap.dedent('''\
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
            "\\n[yellow]Please log in manually using GCKey in the browser window.[/]\\n"
            "The script will detect your login and continue automatically.\\n"
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
''')

# -- src/auto_booker/search.py -------------------------------------------------
FILES["src/auto_booker/search.py"] = textwrap.dedent('''\
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
        console.print("[yellow]Virtual waiting room detected. Waiting...[/]\\n")

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
''')

# -- src/auto_booker/booking.py ------------------------------------------------
FILES["src/auto_booker/booking.py"] = textwrap.dedent('''\
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
            "\\n[bold yellow]⚠  PAUSED — Review the booking in the browser window.[/]\\n"
            "[yellow]Complete the payment manually when ready.[/]\\n"
            "[dim]The browser will stay open. Press Ctrl+C in the terminal to exit.[/]\\n"
        )
        alert("Auto-Booker", "Booking ready for payment! Review now.", sound=True, desktop=True)

        take_screenshot(page, "pre_payment")

        # Keep the script alive so the browser stays open
        try:
            while True:
                time.sleep(5)
        except KeyboardInterrupt:
            console.print("\\n[dim]Exiting. Browser may remain open.[/]")
''')

# -- src/auto_booker/main.py ---------------------------------------------------
FILES["src/auto_booker/main.py"] = textwrap.dedent('''\
    """CLI entry point for the Banff auto-booker."""

    from __future__ import annotations

    import sys
    from pathlib import Path

    import click
    from rich.console import Console
    from rich.panel import Panel

    from .config import load_config
    from .browser import BrowserSession
    from .auth import wait_for_login
    from .search import wait_through_queue, navigate_to_campground
    from .booking import (
        find_available_sites,
        select_site,
        click_book,
        fill_booking_form,
        advance_to_checkout,
        pause_before_payment,
        take_screenshot,
    )

    console = Console()


    @click.command()
    @click.option(
        "-c", "--config",
        default="config.yaml",
        type=click.Path(exists=True),
        help="Path to YAML config file.",
    )
    @click.option(
        "--login-timeout",
        default=15,
        type=int,
        help="Minutes to wait for manual login (default 15).",
    )
    @click.option(
        "--queue-timeout",
        default=120,
        type=int,
        help="Minutes to wait in virtual queue (default 120).",
    )
    def cli(config: str, login_timeout: int, queue_timeout: int) -> None:
        """Banff National Park campsite auto-booker.

        Semi-automated tool that helps you book frontcountry campsites
        on Parks Canada's reservation system (reservation.pc.gc.ca).
        """
        console.print(Panel(
            "[bold cyan]🏕  Banff Campsite Auto-Booker[/]\\n"
            "[dim]Semi-automated · You handle login & payment · Bot handles speed[/]",
            border_style="cyan",
        ))

        cfg = load_config(config)
        console.print(f"[dim]Config loaded: {len(cfg.campgrounds)} campground(s), "
                       f"{cfg.dates.check_in} → {cfg.dates.check_out}[/]\\n")

        session = BrowserSession()
        try:
            page = session.launch()

            # ── Step 1: Login ──────────────────────────────────────────────
            if not wait_for_login(page, timeout_minutes=login_timeout):
                session.close()
                sys.exit(1)

            # ── Step 2: Queue ──────────────────────────────────────────────
            if not wait_through_queue(page, timeout_minutes=queue_timeout):
                session.close()
                sys.exit(1)

            # ── Step 3: Search & Book ──────────────────────────────────────
            console.rule("[bold cyan]Step 3 · Search & Book[/]")

            booked = False
            date_variants = cfg.dates.date_variants()

            for campground in cfg.campgrounds:
                if booked:
                    break
                for check_in, check_out in date_variants:
                    if not navigate_to_campground(
                        page, campground, check_in, check_out,
                        cfg.party.size, cfg.party.equipment,
                    ):
                        continue

                    available = find_available_sites(page)
                    if not available:
                        console.print("[yellow]No sites available, trying next option...[/]")
                        continue

                    site = select_site(page, available, cfg.preferred_sites)
                    if site is None:
                        continue

                    if not click_book(page, site):
                        continue

                    fill_booking_form(page, cfg.party.size, cfg.party.equipment)

                    if advance_to_checkout(page):
                        booked = True
                        break

            if not booked:
                console.print("\\n[bold red]✗ Could not book any campsite. All options exhausted.[/]")
                take_screenshot(page, "no_availability")
                # Keep browser open for manual attempt
                console.print("[yellow]Browser stays open for manual booking. Press Ctrl+C to exit.[/]")
                try:
                    while True:
                        import time; time.sleep(5)
                except KeyboardInterrupt:
                    pass
                session.close()
                sys.exit(1)

            # ── Step 4: Pause for payment ──────────────────────────────────
            pause_before_payment(page)
        except KeyboardInterrupt:
            console.print("\\n[dim]Interrupted.[/]")
        finally:
            session.close()


    if __name__ == "__main__":
        cli()
''')

# -- tests/test_config.py ------------------------------------------------------
FILES["tests/__init__.py"] = ""

FILES["tests/test_config.py"] = textwrap.dedent('''\
    """Tests for configuration loading."""

    import tempfile
    from pathlib import Path

    import pytest
    from auto_booker.config import load_config


    SAMPLE_YAML = """
    campgrounds:
      - name: "Two Jack Lakeside"
        url_slug: "TwoJackLakeside"
      - name: "Tunnel Mountain Village I"
        url_slug: "TunnelMountainVillageI"

    dates:
      check_in: "2026-07-10"
      check_out: "2026-07-13"
      flexible_days: 2

    party:
      size: 4
      equipment: tent

    preferred_sites: ["A21", "A22"]

    notifications:
      sound: true
      desktop: false
    """


    def test_load_config():
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(SAMPLE_YAML)
            f.flush()
            cfg = load_config(f.name)

        assert len(cfg.campgrounds) == 2
        assert cfg.campgrounds[0].name == "Two Jack Lakeside"
        assert cfg.campgrounds[0].url_slug == "TwoJackLakeside"
        assert str(cfg.dates.check_in) == "2026-07-10"
        assert str(cfg.dates.check_out) == "2026-07-13"
        assert cfg.dates.flexible_days == 2
        assert cfg.party.size == 4
        assert cfg.party.equipment == "tent"
        assert cfg.preferred_sites == ["A21", "A22"]
        assert cfg.notifications.sound is True
        assert cfg.notifications.desktop is False

        Path(f.name).unlink()


    def test_date_variants():
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(SAMPLE_YAML)
            f.flush()
            cfg = load_config(f.name)

        variants = cfg.dates.date_variants()
        # Original + 2 flexible days * 2 directions = 5
        assert len(variants) == 5
        assert variants[0] == (cfg.dates.check_in, cfg.dates.check_out)

        Path(f.name).unlink()
''')

# -- README.md -----------------------------------------------------------------
FILES["README.md"] = textwrap.dedent("""\
    # 🏕 Banff Campsite Auto-Booker

    Semi-automated tool to help you book **frontcountry campsites** at Banff National Park
    on Parks Canada's reservation system ([reservation.pc.gc.ca](https://reservation.pc.gc.ca)).

    ## What It Does

    1. **Opens a browser** for you to manually log in via GCKey and wait through the virtual queue
    2. **Automatically navigates** to your target campground, selects dates, and picks an available site at maximum speed
    3. **Pauses before payment** so you can review and confirm manually

    > ⚠️ This tool does **not** skip the queue or bypass any anti-bot measures.
    > It simply automates form navigation so you don't lose precious seconds clicking through menus.

    ## Setup

    ```bash
    # 1. Create project structure
    python setup_project.py

    # 2. Install the package
    pip install -e .

    # 3. Install Playwright browsers
    playwright install chromium

    # 4. Copy and edit config
    copy config.example.yaml config.yaml
    # Edit config.yaml with your campground preferences
    ```

    ## Usage

    ```bash
    # Run with default config.yaml
    auto-booker

    # Run with a custom config file
    auto-booker -c my_config.yaml

    # Adjust timeouts
    auto-booker --login-timeout 20 --queue-timeout 180
    ```

    ## Configuration

    See `config.example.yaml` for all options:

    - **campgrounds** — Priority-ordered list of target campgrounds
    - **dates** — Check-in/out dates with optional flexibility window
    - **party** — Party size and equipment type
    - **preferred_sites** — Optional list of preferred site numbers
    - **notifications** — Sound and desktop alert preferences

    ## Launch Day Tips

    1. **Create your GCKey account** well before launch day
    2. **Test the tool** in advance by running it against the live site (you can search without booking)
    3. On launch day, start the tool **30+ minutes early** — the virtual queue opens ~30 min before reservations
    4. **Log in via GCKey** in the browser window when prompted
    5. Wait in the queue — the tool will alert you when you're through
    6. The bot takes over navigation — watch it go!
    7. **Review and pay** manually when prompted

    ## Architecture

    ```
    src/auto_booker/
    ├── main.py      # CLI entry point (Click)
    ├── config.py    # YAML config loading
    ├── browser.py   # Playwright browser session (persistent, stealth)
    ├── auth.py      # Manual login detection
    ├── search.py    # Campground search, queue detection
    ├── booking.py   # Site selection, form filling, checkout
    └── notify.py    # Sound & desktop notifications
    ```

    ## Disclaimer

    This tool is for **personal educational use**. Use responsibly and respect Parks Canada's
    terms of service. The tool does not circumvent any queue or security measures.
""")

# -- .github/copilot-instructions.md -------------------------------------------
FILES[".github/copilot-instructions.md"] = textwrap.dedent("""\
    # Copilot Instructions — auto-booker

    ## Build & Run

    ```bash
    # First-time setup (creates src/ and tests/ directories + all source files)
    python setup_project.py
    pip install -e .
    playwright install chromium

    # Run
    auto-booker -c config.yaml

    # Tests
    pytest                           # full suite
    pytest tests/test_config.py -k test_load_config   # single test
    ```

    ## Architecture

    This is a **semi-automated Playwright browser tool** for booking Banff National Park frontcountry campsites on `reservation.pc.gc.ca`. The user handles login and payment; the bot handles fast form navigation.

    **Runtime flow** (orchestrated by `main.py` → `cli()`):

    1. **auth.py** — Opens browser, waits for manual GCKey login (polls for "Sign Out" link)
    2. **search.py** — Detects virtual queue, waits until through, then navigates to campground search URL
    3. **booking.py** — Parses available sites, selects preferred or first available, fills form, advances to checkout
    4. **booking.py** → `pause_before_payment()` — Stops before payment, keeps browser open for manual confirmation

    **Key design decisions:**
    - `BrowserSession` (browser.py) uses `launch_persistent_context` so cookies/sessions survive across runs. Profile stored at `~/.auto-booker/browser-profile/`.
    - `main.py` manages browser lifecycle **manually** (not via context manager) so the browser stays open for manual fallback when booking fails.
    - `config.py` `Dates.date_variants()` generates fallback check-in/out pairs by shifting ±N days, iterated in the main booking loop.
    - All modules use `rich.console.Console` for terminal output. Playwright selectors are best-effort since the reservation site DOM changes periodically.

    ## Source Generation

    Source files live in `setup_project.py` as `textwrap.dedent` string blocks written to `src/auto_booker/`. After running `python setup_project.py`, edit the generated files in `src/` directly — not `setup_project.py`.

    ## Conventions

    - **Config as dataclasses**: `config.py` uses `@dataclass` types (`Config`, `Campground`, `Dates`, `Party`, `Notifications`) loaded from YAML via `load_config()`.
    - **Error handling pattern**: Playwright interactions wrap in try/except, return `bool` success, and take a screenshot on failure to `~/.auto-booker/screenshots/`.
    - **Notifications**: `notify.alert()` is the unified entry point for sound + desktop alerts. Windows toast notifications use PowerShell subprocess; falls back to terminal bell.
    - **Selectors are fragile**: The reservation site changes its DOM. When updating selectors in `search.py` or `booking.py`, test against the live site in browse mode (no login required to search).
""")

# ---------------------------------------------------------------------------
# Write all files
# ---------------------------------------------------------------------------
for rel_path, content in FILES.items():
    full_path = os.path.join(BASE, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  ✓ {rel_path}")

print(f"\nAll {len(FILES)} files created successfully!")
print("\nNext steps:")
print("  pip install -e .")
print("  playwright install chromium")
print("  copy config.example.yaml config.yaml")
print("  auto-booker")
