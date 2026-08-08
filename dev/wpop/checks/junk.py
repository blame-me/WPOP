"""Storage / junk checks: temp files, recycle bin, browser caches, Windows
Update cache, and disk-free-space pressure."""
from __future__ import annotations

import os
from typing import List

import psutil

from wpop.core import wins
from wpop.core.fixes import move_to_quarantine
from wpop.core.models import (
    Category,
    Check,
    Finding,
    RiskLevel,
    Severity,
)


class TempFileCheck(Check):
    id = "storage.temp_files"
    name = "User temporary files"
    category = Category.STORAGE

    def run(self, ctx) -> List[Finding]:
        temp = os.environ.get("TEMP", "")
        if not temp or not os.path.isdir(temp):
            return []
        size = wins.dir_size(temp)
        if size < (512 * 1024 * 1024):
            return []
        sev = Severity.CRITICAL if size > (8 << 30) else Severity.WARNING
        return [
            Finding(
                key="storage.temp_files",
                check_id=self.id,
                category=self.category,
                severity=sev,
                risk=RiskLevel.SAFE,
                title=f"Temporary files are using {wins.human_bytes(size)}",
                detail=f"{temp}",
                impact="Clearing them frees disk space with no system impact.",
                fix=move_to_quarantine([temp], "Quarantine contents of temp folder"),
            )
        ]


class RecycleBinCheck(Check):
    id = "storage.recycle_bin"
    name = "Recycle Bin contents"
    category = Category.STORAGE

    def run(self, ctx) -> List[Finding]:
        raw = ctx.ps_raw(
            "$shell = New-Object -ComObject Shell.Application; "
            "$f = $shell.Namespace(0xA); "
            "$c = 0; $s = 0; foreach ($i in $f.Items()) { $c++; $s += [int]$i.Size }; "
            "\"$c|$s\""
        )
        if not raw or "|" not in raw:
            return []
        try:
            count_str, size_str = raw.split("|", 1)
            count = int(count_str)
            size = int(size_str)
        except ValueError:
            return []
        if count == 0:
            return []
        sev = Severity.WARNING if size > 200 * 1024 * 1024 else Severity.INFO
        return [
            Finding(
                key="storage.recycle_bin",
                check_id=self.id,
                category=self.category,
                severity=sev,
                risk=RiskLevel.MEDIUM,
                title=f"Recycle Bin holds {count} item(s), {wins.human_bytes(size)}",
                impact="Emptying it permanently deletes files that are already removed.",
            )
        ]


class BrowserCacheCheck(Check):
    id = "storage.browser_cache"
    name = "Browser cache folders"
    category = Category.STORAGE

    def run(self, ctx) -> List[Finding]:
        local = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            os.path.join(local, r"Google\Chrome\User Data\Default\Cache"),
            os.path.join(local, r"Microsoft\Edge\User Data\Default\Cache"),
            os.path.join(local, r"Chromium\User Data\Default\Cache"),
        ]
        present = [c for c in candidates if os.path.isdir(c)]
        if not present:
            return []
        total = sum(wins.dir_size(c) for c in present)
        if total <= 300 * 1024 * 1024:
            return []
        return [
            Finding(
                key="storage.browser_cache",
                check_id=self.id,
                category=self.category,
                severity=Severity.WARNING,
                risk=RiskLevel.SAFE,
                title=f"Browser cache is using {wins.human_bytes(total)}",
                detail="Chrome/Edge cache directories",
                impact="Clearing it frees space; pages will re-download once.",
                fix=move_to_quarantine(present, "Quarantine browser cache folders"),
            )
        ]


class WindowsUpdateCacheCheck(Check):
    id = "storage.windows_update_cache"
    name = "Windows Update download cache"
    category = Category.STORAGE

    def run(self, ctx) -> List[Finding]:
        paths = [
            r"C:\Windows\SoftwareDistribution\Download",
            r"C:\Windows\SoftwareDistribution\DeliveryOptimization",
        ]
        sizes = {}
        for p in paths:
            if os.path.isdir(p):
                sizes[p] = wins.dir_size(p)
        if not sizes:
            return []
        total = sum(sizes.values())
        if total <= 800 * 1024 * 1024:
            return []
        needs_admin = not ctx.has_admin()
        return [
            Finding(
                key="storage.windows_update_cache",
                check_id=self.id,
                category=self.category,
                severity=Severity.WARNING,
                risk=RiskLevel.ADVANCED if needs_admin else RiskLevel.MEDIUM,
                title=f"Windows Update cache is using {wins.human_bytes(total)}",
                detail="Cleared automatically by the next 'Disk Cleanup' run.",
                impact="Frees up to this much space once updates are installed.",
            )
        ]


class DiskPressureCheck(Check):
    id = "storage.disk_pressure"
    name = "Free disk space on the system drive"
    category = Category.STORAGE

    def run(self, ctx) -> List[Finding]:
        try:
            usage = psutil.disk_usage("C:\\")
        except OSError:
            return []
        free = usage.free / (1024 ** 3)
        total = usage.total / (1024 ** 3)
        if usage.percent >= 92:
            sev = Severity.CRITICAL
            summary = f"only {free:.1f} GB free of {total:.0f} GB"
        elif usage.percent >= 85:
            sev = Severity.WARNING
            summary = f"{free:.1f} GiB free of {total:.0f} GiB"
        else:
            return []
        return [
            Finding(
                key="storage.disk_pressure",
                check_id=self.id,
                category=self.category,
                severity=sev,
                risk=RiskLevel.SAFE,
                title=f"Low disk space: {summary}",
                impact="Fencing more free space avoids slowdowns and update failures.",
            )
        ]