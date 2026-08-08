"""Admin/elevation helpers. Scanning never requires admin; applying fixes does,
and elevation is requested lazily at apply time."""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from typing import Optional

try:
    _shell32 = ctypes.windll.shell32  # type: ignore[attr-defined]
except AttributeError:  # non-Windows (tests)
    _shell32 = None

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def is_admin() -> bool:
    """True if the current process has an elevated token."""
    if _shell32 is None:
        return False
    try:
        return bool(_shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_elevated(argv: Optional[list[str]] = None) -> bool:
    """Relaunch the current invocation elevated via UAC.

    Returns True if the elevation prompt was accepted (a new process was
    spawned); the caller should exit immediately after a True return when
    orchestrating admin-only work. Returns False when using an elevated child
    does not apply (already admin or prompt cancelled).
    """
    if _shell32 is None or is_admin():
        return False
    argv = argv if argv is not None else [sys.argv[0], *sys.argv[1:]]
    command = pass_through_command(argv)
    result = _shell32.ShellExecuteW(None, "runas", sys.executable, command, None, 1)
    cancelled = result <= 32
    return not cancelled


def pass_through_command(argv: list[str]) -> str:
    """Build a quoted command line suitable for ShellExecuteW."""
    import shlex

    return " ".join(shlex.quote(a) for a in argv)


def _self_exe() -> str:
    """Return the python interpreter that should be re-run for commands."""
    return sys.executable


def open_external(path_or_url: str) -> None:
    if _shell32 is None:
        return
    _shell32.ShellExecuteW(None, "open", path_or_url, None, None, 1)