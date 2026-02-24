# 🏕 Banff Campsite Auto-Booker

Semi-automated tool to help you book **frontcountry campsites** at Banff National Park
on Parks Canada's reservation system ([reservation.pc.gc.ca](https://reservation.pc.gc.ca)).

## What It Does

1. **Automatically navigates** to your target campground, selects dates, and picks an available site at maximum speed
2. **Pauses before payment** so you can log in via GCKey and confirm manually

> ⚠️ This tool does **not** skip the queue or bypass any anti-bot measures.
> It simply automates form navigation so you don't lose precious seconds clicking through menus.

## Setup

**Quick setup:**
```bash
# macOS / Linux
bash setup.sh

# Windows
setup.bat
```

**Manual setup:**
```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate.bat     # Windows

# 2. Install the package
pip install -e ".[dev]"

# 3. Install Playwright browsers
playwright install chromium

# 4. Copy and edit config
cp config.example.yaml config.yaml
# Edit config.yaml with your campground preferences
```

## Usage

```bash
# Run with default config.yaml
auto-booker

# Run with a custom config file
auto-booker -c my_config.yaml

# Adjust the virtual-queue wait timeout (default 120 min)
auto-booker --queue-timeout 180
```

## Configuration

See `config.example.yaml` for all options. Key fields:

```yaml
campgrounds:
  - name: "Two Jack Main"
    preferred_sections: ["Loops 22-27"]  # optional: target a specific loop/section
    preferred_sites: ["22B", "22C"]      # optional: preferred site numbers within the section

  - name: "Tunnel Mountain - Village 1"
    preferred_sites: ["A21", "A22"]      # no section needed for lettered campgrounds

dates:
  check_in: "2026-07-12"
  check_out: "2026-07-13"
  flexible_days: 2        # +/- days to try if exact dates are unavailable

party:
  size: 4
  equipment: "Medium Tent"

notifications:
  sound: true
  desktop: true
```

### Configuration options

| Field | Scope | Description |
|---|---|---|
| `campgrounds[].name` | per campground | Campground name as shown on Parks Canada |
| `campgrounds[].preferred_sections` | per campground | Section/loop names to target first (e.g. `["Loops 22-27"]`) |
| `campgrounds[].preferred_sites` | per campground | Site IDs to target first (e.g. `["A21", "22B"]`); falls back to first available |
| `dates.check_in` / `check_out` | global | Desired nights in `YYYY-MM-DD` format |
| `dates.flexible_days` | global | Shifts the window ±N days when exact dates are unavailable |
| `party.size` | global | Number of people |
| `party.equipment` | global | Equipment type shown in Parks Canada's dropdown |
| `notifications.sound` / `desktop` | global | Alert when booking is ready for payment |

## Launch Day Tips

1. **Create your GCKey account** well before launch day
2. **Test the tool** in advance — run it against the live site to verify the search flow
3. On launch day, start the tool **30+ minutes early** — the virtual queue opens ~30 min before reservations
4. Wait in the queue — the tool will alert you when you're through and take over automatically
5. **Log in and pay** manually when the browser pauses at the payment screen

## Architecture

```
src/auto_booker/
├── main.py      # CLI entry point (Click)
├── config.py    # YAML config loading (Campground, Dates, Party, Config)
├── browser.py   # Playwright browser session (persistent, stealth)
├── auth.py      # Login detection (kept for reference)
├── search.py    # Park selection, date picker, campground search, queue detection
├── booking.py   # Section/site selection (expansion-panel DOM), reserve flow
└── notify.py    # Sound & desktop notifications

tests/
├── test_config.py   # Config loading unit tests
└── test_booking.py  # Booking logic unit tests (mocked Playwright)
```

## Disclaimer

This tool is for **personal educational use**. Use responsibly and respect Parks Canada's
terms of service. The tool does not circumvent any queue or security measures.
