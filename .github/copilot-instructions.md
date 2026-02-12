# Copilot Instructions — auto-booker

## Build & Run

```bash
# First-time setup
setup.bat                        # or manually: python -m venv venv && venv\Scripts\activate && pip install -e ".[dev]" && playwright install chromium

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

## Conventions

- **Config as dataclasses**: `config.py` uses `@dataclass` types (`Config`, `Campground`, `Dates`, `Party`, `Notifications`) loaded from YAML via `load_config()`.
- **Error handling pattern**: Playwright interactions wrap in try/except, return `bool` success, and take a screenshot on failure to `~/.auto-booker/screenshots/`.
- **Notifications**: `notify.alert()` is the unified entry point for sound + desktop alerts. Windows toast notifications use PowerShell subprocess; falls back to terminal bell.
- **Selectors are fragile**: The reservation site changes its DOM. When updating selectors in `search.py` or `booking.py`, test against the live site in browse mode (no login required to search).
