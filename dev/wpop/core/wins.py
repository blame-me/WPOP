"""Low-level win32 helpers used across checks: registry traversal, file sizes,
size formatting, key env paths, scheduled-task / service queries via CIM."""
from __future__ import annotations

import os
import time
import winreg
from typing import Any, Iterator, List, Optional, Tuple, Union

HKCU = winreg.HKEY_CURRENT_USER
HKLM = winreg.HKEY_LOCAL_MACHINE


def human_bytes(num: float, suffix: str = "B") -> str:
    for unit in ["", "Ki", "Mi", "Gi", "Ti"]:
        if abs(num) < 1024.0 or unit == "Ti":
            return f"{num:.1f} {unit}{suffix}" if unit else f"{num:.0f} {suffix}"
        num /= 1024.0
    return f"{num:.1f} {suffix}"  # pragma: no cover


def dir_size(path: str, followlinks: bool = False) -> int:
    """Recursively sum file sizes under path, skipping unreadable trees."""
    total = 0
    for root, _dirs, files in os.walk(path, followlinks=followlinks):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                continue
    return total


def path_age_days(path: str) -> float:
    """Age in days of the newest mtime in the tree, 0.0 if missing."""
    newest = 0.0
    if not os.path.exists(path):
        return 0.0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                newest = max(newest, os.path.getmtime(os.path.join(root, name)))
            except OSError:
                continue
    return (time.time() - (newest or os.path.getmtime(path))) / 86400.0


def enum_values(root: int, path: str) -> List[Tuple[str, Any]]:
    """Yield (name, value) pairs for every value under a registry key."""
    out: List[Tuple[str, Any]] = []
    try:
        with winreg.OpenKey(root, path) as key:
            i = 0
            while True:
                try:
                    name, value, _typ = winreg.EnumValue(key, i)
                except OSError:
                    break
                out.append((name, value))
                i += 1
    except OSError:
        pass
    return out


def enum_subkeys(root: int, path: str) -> List[str]:
    out: List[str] = []
    try:
        with winreg.OpenKey(root, path) as key:
            i = 0
            while True:
                try:
                    name = winreg.EnumKey(key, i)
                except OSError:
                    break
                out.append(name)
                i += 1
    except OSError:
        pass
    return out


def get_value(root: int, path: str, name: str) -> Union[Any, None]:
    try:
        with winreg.OpenKey(root, path) as key:
            value, _typ = winreg.QueryValueEx(key, name)
            return value
    except OSError:
        return None


def key_exists(root: int, path: str) -> bool:
    try:
        with winreg.OpenKey(root, path):
            return True
    except OSError:
        return False