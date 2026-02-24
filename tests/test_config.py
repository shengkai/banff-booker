"""Tests for configuration loading."""

import tempfile
from pathlib import Path

import pytest
from auto_booker.config import load_config


SAMPLE_YAML = """
campgrounds:
  - name: "Two Jack Lakeside"
  - name: "Tunnel Mountain Village I"
    preferred_sections: ["A"]
    preferred_sites: ["A21", "A22"]

dates:
  check_in: "2026-07-12"
  check_out: "2026-07-13"
  flexible_days: 2

party:
  size: 4
  equipment: tent

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
    assert str(cfg.dates.check_in) == "2026-07-12"
    assert str(cfg.dates.check_out) == "2026-07-13"
    assert cfg.dates.flexible_days == 2
    assert cfg.party.size == 4
    assert cfg.party.equipment == "tent"
    assert cfg.campgrounds[1].preferred_sections == ["A"]
    assert cfg.campgrounds[1].preferred_sites == ["A21", "A22"]
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
