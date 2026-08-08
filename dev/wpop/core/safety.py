"""Safety-layer helpers: System Restore Points and registry key exports served
before applying risky batch changes."""
from __future__ import annotations

import os
import subprocess
import winreg
from typing import Optional

from wpop.core.elevation import CREATE_NO_WINDOW, is_admin

_HIVES = {
    winreg.HKEY_CURRENT_USER: "HKEY_CURRENT_USER",
    winreg.HKEY_LOCAL_MACHINE: "HKEY_LOCAL_MACHINE",
    winreg.HKEY_CLASSES_ROOT: "HKEY_CLASSES_ROOT",
    winreg.HKEY_USERS: "HKEY_USERS",
}


def create_restore_point(label: str) -> Optional[bool]:
    """Create a System Restore Point. Needs elevation and the feature enabled.

    Returns True on success, False if skipped (no admin / feature disabled),
    None if the shell call itself failed.
    """
    if not is_admin():
        return False
    safe_label = label.replace("'", "''")
    script = (
        "Checkpoint-Computer -Description '"
        + safe_label
        + "' -RestorePointType MODIFY_SETTINGS -ErrorAction SilentlyContinue; "
        "$out = 0; try { $r = Get-ComputerRestorePoint -ErrorAction Stop | "
        "Sort-Object -Descending | Select-Object -First 1; $out = 1 } catch {}; "
        "$out"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            timeout=120,
            creationflags=CREATE_NO_WINDOW,
        )
        out = proc.stdout.decode("utf-8", "replace").strip()
        return out.strip().endswith("1")
    except Exception:
        return None


def export_registry_key(root: int, key_path: str, destination: str) -> bool:
    """Export hive\\key_path to a .reg file via reg.exe. Returns success."""
    hive = _HIVES.get(root)
    if hive is None:
        return False
    full = f"{hive}\\{key_path}"
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    try:
        proc = subprocess.run(
            ["reg.exe", "export", full, destination, "/y"],
            capture_output=True,
            timeout=60,
            creationflags=CREATE_NO_WINDOW,
        )
        return proc.returncode == 0
    except OSError:
        return False