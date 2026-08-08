"""ScanContext: shared per-scan PowerShell cache + elevation status.
ScanManager: executes every registered check concurrently and builds a report."""
from __future__ import annotations

import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from wpop.core import models, registry as _registry, scoring
from wpop.core.elevation import CREATE_NO_WINDOW, is_admin
from wpop.core.models import Check, CheckResult, ScanReport


class ScanContext:
    """Shared per-scan state. Caches PowerShell output so several checks can
    reuse a single WMI query."""

    def __init__(self) -> None:
        self._cache: Dict[str, str] = {}
        self.elevated = is_admin()

    def ps_raw(self, script: str, timeout: int = 30) -> str:
        key = script
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        full = (
            "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false); "
            + script
        )
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", full],
                capture_output=True,
                timeout=timeout,
                creationflags=CREATE_NO_WINDOW,
            )
            out = proc.stdout.decode("utf-8", "replace").strip()
        except Exception:
            out = ""
        self._cache[key] = out
        return out

    def ps_json(self, script: str, timeout: int = 30) -> Optional[Any]:
        raw = self.ps_raw(script + " | ConvertTo-Json -Depth 6 -Compress", timeout)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def has_admin(self) -> bool:
        return self.elevated


def _run_check(check: Check, ctx: ScanContext) -> CheckResult:
    t0 = time.perf_counter()
    error = None
    findings: List[models.Finding] = []
    try:
        result = check.run(ctx)
        if result:
            findings = list(result)
    except Exception as exc:  # noqa: BLE001 - one bad check must not kill the scan
        error = f"{type(exc).__name__}: {exc}"
    return CheckResult(
        check=check, findings=findings, duration=time.perf_counter() - t0, error=error
    )


class ScanManager:
    def __init__(
        self,
        checks: Optional[List[Check]] = None,
        ctx: Optional[ScanContext] = None,
    ) -> None:
        self.checks = checks if checks is not None else _registry.instantiate_all()
        self.ctx = ctx if ctx is not None else ScanContext()

    def run(
        self, progress: Optional[Callable[[int, int, Check], None]] = None
    ) -> ScanReport:
        started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        t0 = time.perf_counter()
        total = len(self.checks)

        if total == 0:
            return ScanReport(
                started_at=started,
                duration=0.0,
                results=[],
            )

        with ThreadPoolExecutor(max_workers=max(4, min(8, total))) as pool:
            futures = {pool.submit(_run_check, c, self.ctx): c for c in self.checks}
            results: List[CheckResult] = []
            done = 0
            for fut in as_completed(futures):
                results.append(fut.result())
                done += 1
                if progress:
                    progress(done, total, futures[fut])

        results.sort(key=lambda r: (r.check.category.value, r.check.id))
        duration = time.perf_counter() - t0
        report = ScanReport(
            started_at=started, duration=duration, results=results
        )
        scoring.compute(report)
        return report