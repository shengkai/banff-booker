---
name: banff-booker
description: Set up, configure, run, and maintain the Banff National Park campsite auto-booker. Use when the user wants to book campsites on reservation.pc.gc.ca, update Playwright selectors for the Parks Canada site, add new campgrounds or features, or troubleshoot booking failures.
compatibility: Requires Python 3.10+, Playwright, and Chromium browser. Windows recommended (notifications use winsound/PowerShell).
metadata:
  author: yychenca
  version: "0.1.0"
---

# Banff Campsite Auto-Booker

Semi-automated Playwright tool for booking frontcountry campsites at Banff National Park on Parks Canada's reservation system (reservation.pc.gc.ca).

## Project Setup

```bash
setup.bat                        # one-click: creates venv, installs deps, Chromium
copy config.example.yaml config.yaml   # then edit with target campgrounds/dates
```

## Running

```bash
auto-booker                              # uses config.yaml
auto-booker -c my_config.yaml            # custom config
auto-booker --login-timeout 20 --queue-timeout 180
```

## Runtime Flow

Orchestrated by `main.py` → `cli()`:

1. **Browser launch** (`browser.py`): Headed Chromium with persistent profile at `~/.auto-booker/browser-profile/`. Uses `playwright-stealth` to reduce detection.
2. **Manual login** (`auth.py`): Navigates to reservation.pc.gc.ca, waits for user to log in via GCKey. Polls for "Sign Out" / "My Account" text.
3. **Queue wait** (`search.py`): Detects virtual waiting room, polls until through, fires sound + desktop alert.
4. **Search & book** (`search.py` + `booking.py`): Iterates campgrounds × date variants. For each: navigates via URL params, finds "Book" buttons, selects preferred or first available site, fills form, advances to checkout.
5. **Pause** (`booking.py`): Stops before payment for manual review. Keeps browser open.

If all options exhausted, browser stays open for manual fallback.

## Configuration (config.yaml)

```yaml
campgrounds:                    # priority-ordered
  - name: "Two Jack Lakeside"
    url_slug: "TwoJackLakeside"
dates:
  check_in: "2026-07-10"
  check_out: "2026-07-13"
  flexible_days: 2              # tries +/- N day shifts
party:
  size: 4
  equipment: "tent"             # tent | rv | trailer
preferred_sites: ["A21"]        # optional, falls back to any
notifications:
  sound: true
  desktop: true
```

The `url_slug` must match the campground path on reservation.pc.gc.ca.

## Key Patterns

- **Config**: Dataclasses in `config.py` (`Config`, `Campground`, `Dates`, `Party`, `Notifications`). Loaded from YAML via `load_config()`.
- **Error handling**: All Playwright interactions return `bool`. On failure: screenshot saved to `~/.auto-booker/screenshots/`, then try next option.
- **Browser lifecycle**: `main.py` manages `BrowserSession` manually (not context manager) so browser stays open on failure.
- **Notifications**: Call `notify.alert(title, msg)` for combined sound + desktop. Windows toast via PowerShell subprocess; falls back to terminal bell.
- **Date flexibility**: `Dates.date_variants()` yields (check_in, check_out) tuples: exact dates first, then ±1 day, ±2 days, etc.

## Updating Selectors

The reservation.pc.gc.ca DOM changes periodically. When selectors break:

1. Open the site in a browser, inspect the current DOM structure
2. Update selectors in `search.py` (queue indicators) and `booking.py` (book buttons, form fields, checkout buttons)
3. Test by running `auto-booker` against the live site in browse mode (searching works without login)

Key selector locations:
- `search.py` `_QUEUE_INDICATORS` — virtual waiting room detection
- `booking.py` `find_available_sites()` — "Book" button locators
- `booking.py` `fill_booking_form()` — party size, equipment, checkbox selectors
- `booking.py` `advance_to_checkout()` — "Continue" / "Proceed" button locators
- `auth.py` `_LOGGED_IN_SELECTORS` — login state detection

## Testing

```bash
pytest                                          # full suite
pytest tests/test_config.py -k test_load_config # single test
```

## Adding a New Campground

1. Visit reservation.pc.gc.ca, navigate to the campground
2. Copy the URL path segment (e.g., `TwoJackLakeside` from the URL)
3. Add to `config.yaml` under `campgrounds` with `name` and `url_slug`
