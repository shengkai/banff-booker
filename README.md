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

**Quick setup (recommended):**
```bash
setup.bat
```

**Manual setup:**
```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate.bat

# 2. Install the package
pip install -e ".[dev]"

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
