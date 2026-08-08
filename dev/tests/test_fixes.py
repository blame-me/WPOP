"""Fix factories and undo persistence: registry set/delete round-trips and
quarantine move/restore. Uses only the current user's hive (no admin needed)."""
from __future__ import annotations

import uuid
import winreg

import pytest

from wpop.core import wins


@pytest.fixture()
def test_key():
    """Create and clean up an isolated HKCU test key."""
    path = rf"Software\wpop_tests\{uuid.uuid4().hex}"
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path) as key:
        pass
    yield path
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
    except OSError:
        pass


@pytest.fixture()
def fresh_fixes(tmp_path, monkeypatch):
    """Point undo storage at a temp dir before importing the module."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    from wpop.core import fixes as fx
    fx.UNDO_ROOT = str(tmp_path / "undo")
    fx.SAVED_DIR = str(tmp_path / "undo" / "saved")
    fx.QUARANTINE_ROOT = str(tmp_path / "undo" / "quarantine")
    return fx


def test_registry_set_and_restore(fresh_fixes, test_key):
    fixes = fresh_fixes
    value_name = "wpoptest"
    fixes.registry_set(
        winreg.HKEY_CURRENT_USER, test_key, value_name, "old", "test set"
    ).apply()
    assert wins.get_value(winreg.HKEY_CURRENT_USER, test_key, value_name) == "old"

    undo_id = fixes.undo_id(winreg.HKEY_CURRENT_USER, test_key, value_name)
    assert fixes.saved_meta(undo_id)["had_previous"] is False
    fixes.restore_saved(undo_id)
    assert wins.get_value(winreg.HKEY_CURRENT_USER, test_key, value_name) is None


def test_registry_delete_and_restore(fresh_fixes, test_key):
    fixes = fresh_fixes
    value_name = "wpoptest2"
    # pre-seed a value so Delete has something to restore
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, test_key) as key:
        winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, "before")
    fixes.registry_delete(
        winreg.HKEY_CURRENT_USER, test_key, value_name, "test delete"
    ).apply()
    assert wins.get_value(winreg.HKEY_CURRENT_USER, test_key, value_name) is None
    undo_id = fixes.undo_id(winreg.HKEY_CURRENT_USER, test_key, value_name)
    fixes.restore_saved(undo_id)
    assert wins.get_value(winreg.HKEY_CURRENT_USER, test_key, value_name) == "before"


def test_move_to_quarantine_restores(fresh_fixes, tmp_path):
    fixes = fresh_fixes
    src = tmp_path / "junk"
    src.mkdir()
    (src / "a.txt").write_text("hello", encoding="utf-8")

    fix = fixes.move_to_quarantine([str(src)], "quarantine test")
    fix.apply()
    assert not src.exists()

    fix.undo()
    assert (src / "a.txt").read_text(encoding="utf-8") == "hello"