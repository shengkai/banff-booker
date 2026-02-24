"""Unit tests for booking.py.

Pure functions and selection logic are tested directly.
Playwright-dependent functions (find_sections, find_sites) are tested with
lightweight MagicMock objects that mimic the Angular DOM structure observed
in sites_example.html.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from auto_booker.booking import (
    SiteEntry,
    _is_section_label,
    find_sites,
    section_letter,
    select_section,
    select_site,
)


# ---------------------------------------------------------------------------
# _is_section_label
# ---------------------------------------------------------------------------

class TestIsSectionLabel:
    def test_lettered_section(self):
        assert _is_section_label("Site A  Available") is True

    def test_loops_section(self):
        assert _is_section_label("Loops 22-27  Available") is True

    def test_loop_section(self):
        assert _is_section_label("Loop B  Available") is True

    def test_individual_site_with_digit(self):
        # "Site A49  Available" — has digit after Site → NOT a section
        assert _is_section_label("Site A49  Available") is False

    def test_individual_site_plain_number(self):
        assert _is_section_label("Site 22  Available") is False

    def test_unrelated_label(self):
        assert _is_section_label("Reserve") is False

    def test_case_insensitive(self):
        assert _is_section_label("LOOPS 5-10  Available") is True
        assert _is_section_label("site b  Available") is True


# ---------------------------------------------------------------------------
# section_letter
# ---------------------------------------------------------------------------

def _make_locator(aria_label: str | None = None, text: str = "") -> MagicMock:
    """Return a mock Locator with controlled get_attribute / text_content."""
    loc = MagicMock()
    loc.get_attribute.return_value = aria_label
    loc.text_content.return_value = text
    loc.inner_text.return_value = text
    return loc


class TestSectionLetter:
    def test_lettered_section(self):
        loc = _make_locator(aria_label="Site A  Available")
        assert section_letter(loc) == "A"

    def test_loops_section(self):
        # Real site: aria-label is set, not just text_content
        loc = _make_locator(aria_label="Site Loops 22-27  Available")
        assert section_letter(loc) == "Loops 22-27"

    def test_no_aria_label_falls_back_to_text(self):
        loc = _make_locator(aria_label=None, text="Site B  Available")
        assert section_letter(loc) == "B"


# ---------------------------------------------------------------------------
# select_site
# ---------------------------------------------------------------------------

def _make_site(name: str) -> SiteEntry:
    return SiteEntry(name=name, locator=MagicMock())


class TestSelectSite:
    def test_preferred_site_matched(self):
        sites = [_make_site("22A"), _make_site("22B"), _make_site("22C")]
        result = select_site(MagicMock(), sites, preferred_sites=["22B"])
        assert result.name == "22B"

    def test_preferred_site_case_insensitive(self):
        sites = [_make_site("A49"), _make_site("A55")]
        result = select_site(MagicMock(), sites, preferred_sites=["a49"])
        assert result.name == "A49"

    def test_first_available_fallback(self):
        sites = [_make_site("22A"), _make_site("22B")]
        result = select_site(MagicMock(), sites, preferred_sites=["Z99"])
        assert result.name == "22A"

    def test_empty_preferred_returns_first(self):
        sites = [_make_site("A50")]
        result = select_site(MagicMock(), sites, preferred_sites=[])
        assert result.name == "A50"

    def test_no_sites_returns_none(self):
        result = select_site(MagicMock(), [], preferred_sites=["A49"])
        assert result is None


# ---------------------------------------------------------------------------
# select_section
# ---------------------------------------------------------------------------

def _make_section_locator(label: str) -> MagicMock:
    loc = MagicMock()
    loc.get_attribute.return_value = label
    loc.inner_text.return_value = label
    loc.text_content.return_value = label
    return loc


class TestSelectSection:
    def _sections(self, labels: list[str]) -> list[MagicMock]:
        return [_make_section_locator(lbl) for lbl in labels]

    def test_preferred_section_explicit_match(self):
        sections = self._sections(["Loops 22-27  Available", "Loops 5-10  Available"])
        result = select_section(
            MagicMock(), sections,
            preferred_sections=["Loops 22-27"],
            preferred_sites=[],
        )
        assert result is sections[0]

    def test_preferred_section_substring_match(self):
        # Use distinct labels that don't share substring via 'Available'
        sections = self._sections(["Loops 1-5  Available", "Loops 6-10  Available"])
        result = select_section(
            MagicMock(), sections,
            preferred_sections=["Loops 6"],
            preferred_sites=[],
        )
        assert result is sections[1]

    def test_derive_section_from_preferred_site(self):
        """'A21' → look for section 'A'."""
        sections = self._sections(["Site A  Available", "Site B  Available"])
        result = select_section(
            MagicMock(), sections,
            preferred_sections=[],
            preferred_sites=["A21"],
        )
        assert result is sections[0]

    def test_preferred_sections_take_priority_over_derived(self):
        # Explicit section "Loops 6" beats derived letter "1" from site "1A".
        sections = self._sections(["Loops 1-5  Available", "Loops 6-10  Available"])
        result = select_section(
            MagicMock(), sections,
            preferred_sections=["Loops 6"],  # explicit beats derived from "1A"
            preferred_sites=["1A"],
        )
        assert result is sections[1]

    def test_fallback_to_first_available(self):
        sections = self._sections(["Site A  Available", "Site B  Available"])
        result = select_section(
            MagicMock(), sections,
            preferred_sections=[],
            preferred_sites=[],
        )
        assert result is sections[0]

    def test_no_sections_returns_none(self):
        result = select_section(
            MagicMock(), [],
            preferred_sections=[],
            preferred_sites=[],
        )
        assert result is None


# ---------------------------------------------------------------------------
# find_sites — mocked Angular DOM (mat-expansion-panel structure)
# ---------------------------------------------------------------------------

def _make_panel(resource: str, available: bool) -> MagicMock:
    """Simulate a <mat-expansion-panel data-resource='A50'> with availability."""
    panel = MagicMock()
    panel.is_visible.return_value = True
    panel.get_attribute.side_effect = lambda attr: resource if attr == "data-resource" else None

    avail_label = MagicMock()
    avail_label.count.return_value = 1
    # Use the exact text the real site emits — must be exactly "Available" (not "Not Available")
    avail_label.nth.return_value.text_content.return_value = (
        "Available" if available else "Not Available"
    )
    panel.locator.side_effect = lambda selector: _panel_sub_locator(
        selector, resource, available, avail_label
    )
    return panel


def _panel_sub_locator(selector: str, resource: str, available: bool, avail_label: MagicMock):
    """Route sub-locator calls for a panel mock."""
    if selector == ".availability-label":
        return avail_label
    if selector == "mat-expansion-panel-header":
        header = MagicMock()
        header.count.return_value = 1
        header.first = MagicMock()
        return header
    if selector == "h3.resource-name":
        h3 = MagicMock()
        h3.count.return_value = 0  # prefer data-resource
        return h3
    return MagicMock()


def _make_page_with_panels(panels: list[MagicMock]) -> MagicMock:
    """Return a mock Page whose locator('mat-expansion-panel') returns the panels."""
    page = MagicMock()
    panel_collection = MagicMock()
    panel_collection.count.return_value = len(panels)
    panel_collection.nth.side_effect = lambda i: panels[i]

    def _locator(selector, **kwargs):
        if selector == "mat-expansion-panel":
            return panel_collection
        # For other selectors (Pattern A fallback), return empty collection
        empty = MagicMock()
        empty.count.return_value = 0
        return empty

    page.locator.side_effect = _locator
    return page


class TestFindSites:
    def test_finds_available_panels(self):
        panels = [
            _make_panel("22A", available=True),
            _make_panel("22B", available=True),
            _make_panel("22C", available=False),
        ]
        page = _make_page_with_panels(panels)
        sites = find_sites(page)
        assert len(sites) == 2
        assert sites[0].name == "22A"
        assert sites[1].name == "22B"

    def test_deduplicates_site_names(self):
        panels = [
            _make_panel("A50", available=True),
            _make_panel("A50", available=True),  # duplicate
        ]
        page = _make_page_with_panels(panels)
        sites = find_sites(page)
        assert len(sites) == 1

    def test_returns_empty_when_none_available(self):
        panels = [
            _make_panel("22A", available=False),
            _make_panel("22B", available=False),
        ]
        page = _make_page_with_panels(panels)
        sites = find_sites(page)
        assert sites == []

    def test_click_target_is_header(self):
        panels = [_make_panel("A55", available=True)]
        page = _make_page_with_panels(panels)
        sites = find_sites(page)
        assert len(sites) == 1
        # locator should be the mat-expansion-panel-header mock
        assert sites[0].locator is not None
