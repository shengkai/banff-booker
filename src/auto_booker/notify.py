"""Notification helpers — sound alerts and desktop notifications."""

from __future__ import annotations

import sys
import subprocess
from pathlib import Path


def beep(times: int = 3) -> None:
    """Play a terminal bell / system beep."""
    for _ in range(times):
        sys.stdout.write("\a")
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
