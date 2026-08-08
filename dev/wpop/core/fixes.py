"""Fix factories with reversible undo. Every Fix carries apply()+undo(). When
applied, a JSON snapshot is written to the undo store so changes can be rolled
back even after the process exits (see restore_saved)."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import winreg
from typing import Any, Iterable, List, Optional

from wpop.core.models import Fix

UNDO_ROOT = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "wpop", "undo"
)
SAVED_DIR = os.path.join(UNDO_ROOT, "saved")
QUARANTINE_ROOT = os.path.join(UNDO_ROOT, "quarantine")


def undo_id(*parts: Any) -> str:
    """Stable id derived from the fix target so repeated fixes map to one snapshot."""
    seed = "|".join(str(p) for p in parts)
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


def _saved_path(uid: str) -> str:
    return os.path.join(SAVED_DIR, uid + ".json")


def _save(uid: str, payload: dict) -> None:
    os.makedirs(SAVED_DIR, exist_ok=True)
    with open(_saved_path(uid), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)


def saved_meta(uid: str) -> Optional[dict]:
    path = _saved_path(uid)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def list_saved() -> List[str]:
    if not os.path.isdir(SAVED_DIR):
        return []
    return sorted(
        name[:-5] for name in os.listdir(SAVED_DIR) if name.endswith(".json")
    )


def restore_saved(uid: str) -> bool:
    """Replay a saved snapshot to restore the original state."""
    data = saved_meta(uid)
    if data is None:
        return False
    kind = data.get("kind")
    if kind == "registry":
        _restore_registry(data)
    elif kind == "quarantine":
        _restore_quarantine(data)
    return True


# --- registry ----------------------------------------------------------------


_REG_TYPES = {
    "REG_SZ": winreg.REG_SZ,
    "REG_EXPAND_SZ": winreg.REG_EXPAND_SZ,
    "REG_DWORD": winreg.REG_DWORD,
    "REG_BINARY": winreg.REG_BINARY,
    "REG_MULTI_SZ": winreg.REG_MULTI_SZ,
}
_REG_TYPE_NAMES = {v: k for k, v in _REG_TYPES.items()}


def _capture(root: int, key_path: str, name: str) -> tuple[Any, int, bool]:
    try:
        with winreg.OpenKey(root, key_path) as key:
            value, typ = winreg.QueryValueEx(key, name)
            return value, typ, True
    except OSError:
        return None, winreg.REG_SZ, False


def registry_set(
    root: int,
    key_path: str,
    name: str,
    value: object,
    description: str,
) -> Fix:
    """Write a registry value; the previous value (or absence) is snapshotted."""
    previous_value, previous_type, had_previous = _capture(root, key_path, name)
    uid = undo_id(root, key_path, name)
    needs_admin = root == winreg.HKEY_LOCAL_MACHINE

    def apply() -> None:
        with winreg.CreateKeyEx(root, key_path) as key:
            winreg.SetValueEx(key, name, 0, previous_type, value)
        _save(uid, {
            "kind": "registry",
            "root": root,
            "key_path": key_path,
            "name": name,
            "had_previous": had_previous,
            "previous_type": _REG_TYPE_NAMES.get(previous_type, "REG_SZ"),
            "previous_value": previous_value if had_previous else None,
        })

    def undo() -> None:
        restore_saved(uid)

    return Fix(
        description=description, apply=apply, undo=undo, undo_id=uid,
        needs_admin=needs_admin,
    )


def registry_delete(
    root: int,
    key_path: str,
    name: str,
    description: str,
) -> Fix:
    """Delete a registry value; the previous value is snapshotted for undo."""
    previous_value, previous_type, had_previous = _capture(root, key_path, name)
    uid = undo_id(root, key_path, name)
    needs_admin = root == winreg.HKEY_LOCAL_MACHINE

    def apply() -> None:
        with winreg.OpenKey(root, key_path, 0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, name)
            except OSError:
                pass
        _save(uid, {
            "kind": "registry",
            "root": root,
            "key_path": key_path,
            "name": name,
            "had_previous": had_previous,
            "previous_type": _REG_TYPE_NAMES.get(previous_type, "REG_SZ"),
            "previous_value": previous_value,
        })

    def undo() -> None:
        restore_saved(uid)

    return Fix(
        description=description, apply=apply, undo=undo, undo_id=uid,
        needs_admin=needs_admin,
    )


def _restore_registry(data: dict) -> None:
    root = int(data["root"])
    path = data["key_path"]
    name = data["name"]
    with winreg.CreateKeyEx(root, path) as key:
        if data["had_previous"]:
            typ = _REG_TYPES.get(data["previous_type"], winreg.REG_SZ)
            winreg.SetValueEx(key, name, 0, typ, data["previous_value"])
        else:
            try:
                winreg.DeleteValue(key, name)
            except OSError:
                pass


# --- quarantine --------------------------------------------------------------


def move_to_quarantine(items: Iterable[str], description: str) -> Fix:
    """Move files/dirs into a quarantine folder; undo moves them back."""
    paths = [p for p in items if os.path.exists(p)]
    uid = undo_id(*sorted(paths))
    qdir = os.path.join(QUARANTINE_ROOT, uid)
    os.makedirs(qdir, exist_ok=True)

    def apply() -> None:
        moved = []
        for origin in paths:
            dest = os.path.join(qdir, os.path.basename(origin))
            try:
                shutil.move(origin, dest)
            except OSError:
                continue
            moved.append({"origin": origin, "dest": dest})
        _save(uid, {"kind": "quarantine", "entries": moved})

    def undo() -> None:
        restore_saved(uid)

    return Fix(description=description, apply=apply, undo=undo, undo_id=uid)


def _restore_quarantine(data: dict) -> None:
    for entry in reversed(data.get("entries", [])):
        origin = entry.get("origin")
        dest = entry.get("dest")
        if not origin or not dest or not os.path.exists(dest):
            continue
        try:
            shutil.move(dest, origin)
        except OSError:
            continue