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
