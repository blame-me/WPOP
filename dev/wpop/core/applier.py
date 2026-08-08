"""High-level application of fixes: elevation, restore point, apply, audit."""
from __future__ import annotations

import sys
from typing import Dict, List, Optional, Tuple

from wpop.core import safety
from wpop.core.elevation import is_admin, relaunch_elevated
from wpop.core.fixes import restore_saved
from wpop.core.log import AuditLog
from wpop.core.models import Finding, ScanReport


class Applier:
    def __init__(
        self,
        findings_by_key: Dict[str, List[Finding]],
        log: Optional[AuditLog] = None,
    ) -> None:
        self._by_key = findings_by_key
        self.log = log or AuditLog()

    @classmethod
    def from_report(cls, report: ScanReport, **kwargs) -> "Applier":
        mapping: Dict[str, List[Finding]] = {}
        for finding in report.all_findings:
            mapping.setdefault(finding.key, []).append(finding)
        return cls(mapping, **kwargs)

    def _collect(self, keys: List[str]) -> List[Finding]:
        out = []
        for key in keys:
            for finding in self._by_key.get(key, []):
                if finding.fix is not None:
                    out.append(finding)
        return out

    def needs_elevation(self, keys: List[str]) -> bool:
        return any(f.fix.needs_admin for f in self._collect(keys))

    def apply(self, keys: List[str]) -> List[Tuple[str, bool, str]]:
        """Apply fixes for the given findings. Returns (key, ok, message)."""
        targets = self._collect(keys)
        if not targets:
            return [(key, False, "no matching fix available") for key in keys]

        if not is_admin() and self.needs_elevation(keys):
            return self._relaunch_elevated(keys, targets)

        if is_admin():
            safety.create_restore_point("wpop optimization apply")

        results = []
        for finding in targets:
            fix = finding.fix
            try:
                fix.apply()
            except Exception as exc:  # noqa: BLE001
                results.append((finding.key, False, f"{type(exc).__name__}: {exc}"))
            else:
                self.log.applied([finding.key], fix.description, finding.risk.value)
                results.append((finding.key, True, fix.description))
        return results

    def _relaunch_elevated(
        self, keys: List[str], targets: List[Finding]
    ) -> List[Tuple[str, bool, str]]:
        argv = [sys.argv[0], "apply", "--yes", *keys]
        launched = relaunch_elevated(argv)
        return [
            (f.key, False, "deferred to elevated process" if launched else "elevation cancelled")
            for f in targets
        ]


def undo_by_ids(undo_ids: List[str]) -> List[Tuple[str, bool, str]]:
    results = []
    for uid in undo_ids:
        try:
            ok = restore_saved(uid)
        except Exception as exc:  # noqa: BLE001
            results.append((uid, False, f"{type(exc).__name__}: {exc}"))
            continue
        results.append((uid, bool(ok), "restored" if ok else "no snapshot"))
    return results