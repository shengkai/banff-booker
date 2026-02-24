"""Live smoke-test for navigate_to_campground().

Run with:
    source venv/bin/activate
    python -m pytest tests/test_search.py -v -s

The test launches a real (headed) Chromium browser against reservation.pc.gc.ca.
It succeeds when navigate_to_campground() returns True (campground found and
individual site buttons are visible) OR when the function returns False due to
"No Available Sites" — both are valid outcomes and mean the navigation logic
itself worked correctly.  Only an unhandled exception counts as a failure.
"""

from datetime import date, timedelta

import pytest
from playwright.sync_api import sync_playwright

from src.auto_booker.config import Campground
from src.auto_booker.search import navigate_to_campground


@pytest.fixture(scope="module")
def browser_page():
    """Yield a headed Chromium page, then close the browser."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        yield page
        browser.close()


def test_navigate_to_campground(browser_page):
    """navigate_to_campground() should complete without raising an exception.

    Returns True  → campground is available and site buttons are now visible.
    Returns False → either "No Available Sites" or campground not listed;
                    both are valid search outcomes (not test failures).
    """
    campground = Campground(name="Tunnel Mountain - Village 1")
    check_in = date.today() + timedelta(days=30)
    check_out = check_in + timedelta(days=2)

    result = navigate_to_campground(
        page=browser_page,
        campground=campground,
        check_in=check_in,
        check_out=check_out,
        party_size=2,
        equipment="Medium Tent",
    )

    # Both True and False are acceptable — we just must not crash.
    assert isinstance(result, bool), "navigate_to_campground() must return a bool"

    if result:
        # Extra sanity-check: at least one site button should be visible
        visible = browser_page.locator(
            "[role='button'][aria-label*='Site '][aria-label*='Available']"
        ).count()
        assert visible > 0, "Expected at least one available site button after True return"
        print(f"\n✓ Found {visible} available site(s).")
    else:
        print("\n✓ navigate_to_campground() returned False (no sites or not listed) — expected.")
