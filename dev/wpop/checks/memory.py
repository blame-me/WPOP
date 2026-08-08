"""Memory checks: RAM pressure, top consumers, and pagefile configuration."""
from __future__ import annotations

from typing import List

import psutil

from wpop.core import wins
from wpop.core.models import Category, Check, Finding, RiskLevel, Severity


class MemoryPressureCheck(Check):
    id = "memory.pressure"
    name = "RAM pressure"
    category = Category.MEMORY

    def run(self, ctx) -> List[Finding]:
        vm = psutil.virtual_memory()
        percent = vm.percent
        if percent < 75:
            return []
        sev = Severity.CRITICAL if percent >= 92 else Severity.WARNING
        label = (
            f"{percent:.0f}% of {psutil.virtual_memory().total / (1024**3):.0f} GB RAM in use"
        )
        return [
            Finding(
                key="memory.pressure",
                check_id=self.id,
                category=self.category,
                severity=sev,
                risk=RiskLevel.SAFE,
                title=f"High memory pressure: {label}",
                impact="Closing background apps releases RAM and reduces swap file churn.",
            )
        ]


class TopMemoryProcessesCheck(Check):
    id = "memory.top_processes"
    name = "Largest memory consumers"
    category = Category.MEMORY

    def run(self, ctx) -> List[Finding]:
        try:
            procs = sorted(
                psutil.process_iter(["name", "memory_info"]),
                key=lambda p: p.info.get("memory_info").rss
                if p.info.get("memory_info")
                else 0,
                reverse=True,
            )[:6]
        except Exception:
            return []
        big = []
        for p in procs:
            try:
                rss = p.info["memory_info"].rss
            except AttributeError:
                continue
            if rss > 1024 * 1024 * 1024:
                big.append((p.info.get("name") or "?", rss))
        if len(big) < 2:
            return []
        detail = "\n".join(f"- {n}: {wins.human_bytes(r)}" for n, r in big)
        return [
            Finding(
                key="memory.top_processes",
                check_id=self.id,
                category=self.category,
                severity=Severity.WARNING,
                risk=RiskLevel.MEDIUM,
                title=f"{len(big)} programs are each using over 1 GiB of RAM",
                detail=detail,
                impact="Quitting the least-needed ones frees memory immediately.",
            )
        ]


class PagefileCheck(Check):
    id = "memory.pagefile"
    name = "Pagefile (virtual memory)"
    category = Category.MEMORY

    def run(self, ctx) -> List[Finding]:
        setting = wins.get_value(
            wins.HKLM,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management",
            "PagingFiles",
        )
        if setting is None:
            return []
        if isinstance(setting, str):
            setting = [_s for _s in setting.split(";") if _s]
        if not setting:
            return []
        # Default is "X:\pagefile.sys" with no size params. Custom entries carry
        # two numbers (min/max MB) after the path.
        custom = any(
            len(value.split()) > 1 for value in setting if isinstance(value, str)
        )
        if not custom:
            return []
        return [
            Finding(
                key="memory.pagefile.custom",
                check_id=self.id,
                category=self.category,
                severity=Severity.INFO,
                risk=RiskLevel.ADVANCED,
                title="Custom pagefile size configured",
                detail=f"Value: {setting}",
                impact="System-managed sizing adapts to load and is usually best.",
            )
        ]