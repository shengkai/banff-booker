"""CLI entry point for the Banff auto-booker."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from .config import load_config
from .browser import BrowserSession
from .search import wait_through_queue, navigate_to_campground
from .booking import (
    book_site,
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
    "--queue-timeout",
    default=120,
    type=int,
    help="Minutes to wait in virtual queue (default 120).",
)
def cli(config: str, queue_timeout: int) -> None:
    """Banff National Park campsite auto-booker.

    Semi-automated tool that helps you book frontcountry campsites
    on Parks Canada's reservation system (reservation.pc.gc.ca).
    """
    console.print(Panel(
        "[bold cyan]🏕  Banff Campsite Auto-Booker[/]\n"
        "[dim]Semi-automated · You handle login & payment · Bot handles speed[/]",
        border_style="cyan",
    ))

    cfg = load_config(config)
    console.print(f"[dim]Config loaded: {len(cfg.campgrounds)} campground(s), "
                   f"{cfg.dates.check_in} → {cfg.dates.check_out}[/]\n")

    session = BrowserSession()
    try:
        page = session.launch()

        # ── Step 1: Queue ──────────────────────────────────────────────
        if not wait_through_queue(page, timeout_minutes=queue_timeout):
            session.close()
            sys.exit(1)

        # ── Step 2: Search & Book ───────────────────────────────────────
        console.rule("[bold cyan]Step 2 · Search & Book[/]")

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

                if book_site(page, campground.preferred_sections, campground.preferred_sites):
                    booked = True
                    break

        if not booked:
            console.print("\n[bold red]✗ Could not book any campsite. All options exhausted.[/]")
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
        console.print("\n[dim]Interrupted.[/]")
    finally:
        session.close()


if __name__ == "__main__":
    cli()
