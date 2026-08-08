"""Startup & boot-time checks: auto-run entries, startup folders, logon tasks,
auto-start services, fast startup, and system uptime."""
from __future__ import annotations

import os
from datetime import datetime
from typing import List

from wpop.core import wins
from wpop.core.fixes import registry_set
from wpop.core.models import (
    Category,
    Check,
    Finding,
    RiskLevel,
    Severity,
)

RUN_KEYS = [
    (wins.HKCU, r"Software\Microsoft\Windows\CurrentVersion\Run"),
    (wins.HKLM, r"Software\Microsoft\Windows\CurrentVersion\Run"),
    (wins.HKCU, r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
    (wins.HKLM, r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
]

KNOWN_BLOAT = (
    "Onedrive",
    "Adobe Creative Cloud",
    "Googleupdate",
    "Steam",
    "Spotify",
    "Discord",
    "Teams",
    "Dropbox",
    "Mcafee",
    "Norton",
    "Java Update",
)

_LAUNCHER_EXT = (".lnk", ".url", ".appref-ms", ".bat", ".cmd", ".exe")


class RunAutorunCheck(Check):
    id = "startup.run_autoruns"
    name = "Autostart registry entries"
    category = Category.STARTUP

    def run(self, ctx) -> List[Finding]:
        entries = []
        for root, path in RUN_KEYS:
            for name, value in wins.enum_values(root, path):
                if name:
                    entries.append((name, value))
        if not entries:
            return []

        bloat = [n for n, _ in entries if any(b.lower() in n.lower() for b in KNOWN_BLOAT)]
        if bloat:
            return [
                Finding(
                    key="startup.run_autoruns.bloat",
                    check_id=self.id,
                    category=self.category,
                    severity=Severity.WARNING,
                    risk=RiskLevel.MEDIUM,
                    title=f"{len(bloat)} known bloat apps auto-start at logon",
                    detail=f"Found: {', '.join(bloat)}",
                    impact="Disabled launchers speed boot and cut background RAM use.",
                )
            ]
        detail = "\n".join(f"{n} -> {v}" for n, v in entries[:8])
        return [
            Finding(
                key="startup.run_autoruns",
                check_id=self.id,
                category=self.category,
                severity=Severity.INFO,
                risk=RiskLevel.MEDIUM,
                title=f"{len(entries)} programs launch at logon",
                detail=detail,
                impact="Trim the list in Task Manager > Startup apps.",
            )
        ]


class StartupFolderCheck(Check):
    id = "startup.startup_folder"
    name = "Startup-folder shortcuts"
    category = Category.STARTUP

    def run(self, ctx) -> List[Finding]:
        start_dirs = [
            os.path.join(
                os.environ.get("APPDATA", ""),
                r"Microsoft\Windows\Start Menu\Programs\Startup",
            ),
            os.path.join(
                os.environ.get("PROGRAMDATA", ""),
                r"Microsoft\Windows\Start Menu\Programs\Startup",
            ),
        ]
        names: List[str] = []
        for d in start_dirs:
            if os.path.isdir(d):
                names.extend(n for n in os.listdir(d) if self._is_launcher(n))
        names = list(dict.fromkeys(sorted(names)))
        if not names:
            return []
        return [
            Finding(
                key="startup.folder",
                check_id=self.id,
                category=self.category,
                severity=Severity.WARNING,
                risk=RiskLevel.SAFE,
                title=f"{len(names)} shortcuts auto-launch from startup folders",
                detail=", ".join(names[:8]),
                impact="Remove unused shortcuts to speed up sign-in.",
            )
        ]

    @staticmethod
    def _is_launcher(name: str) -> bool:
        lower = name.lower()
        if lower == "desktop.ini":
            return False
        return lower.endswith(_LAUNCHER_EXT)


class LogonTasksCheck(Check):
    id = "startup.logon_tasks"
    name = "Scheduled tasks running at logon"
    category = Category.STARTUP

    def run(self, ctx) -> List[Finding]:
        count = ctx.ps_json(
            "@(Get-ScheduledTask -ErrorAction SilentlyContinue | "
            "Where-Object { $_.State -ne 'Disabled' -and "
            "($_.Triggers | Where-Object { $_.CimClass.CimClassName -eq "
            "'MSFT_TaskLogonTrigger' }) }).Count"
        )
        try:
            count = int(count or 0)
        except (TypeError, ValueError):
            return []
        if count == 0:
            return []
        sev = Severity.WARNING if count > 5 else Severity.INFO
        return [
            Finding(
                key="startup.logon_tasks",
                check_id=self.id,
                category=self.category,
                severity=sev,
                risk=RiskLevel.MEDIUM,
                title=f"{count} scheduled tasks are set to run at logon",
                impact="Disable the ones you do not need in Task Scheduler.",
            )
        ]


class AutoServicesCheck(Check):
    id = "startup.auto_services"
    name = "Services configured to start automatically"
    category = Category.STARTUP

    def run(self, ctx) -> List[Finding]:
        count = ctx.ps_json(
            "@(Get-CimInstance Win32_Service -Filter \"StartMode='Auto'\").Count"
        )
        try:
            count = int(count or 0)
        except (TypeError, ValueError):
            return []
        if count == 0:
            return []
        return [
            Finding(
                key="startup.auto_services",
                check_id=self.id,
                category=self.category,
                severity=Severity.INFO,
                risk=RiskLevel.ADVANCED,
                title=f"{count} services are set to start automatically",
                impact="Each one adds boot time; switch optional services to Manual.",
            )
        ]


class FastBootCheck(Check):
    id = "startup.fast_boot"
    name = "Fast Startup (hiberboot)"
    category = Category.STARTUP

    def run(self, ctx) -> List[Finding]:
        key_path = r"SYSTEM\CurrentControlSet\Control\Session Manager\Power"
        value = wins.get_value(wins.HKLM, key_path, "HiberbootEnabled")
        if str(value).lower() in ("1", "true"):
            return []
        return [
            Finding(
                key="startup.fast_boot",
                check_id=self.id,
                category=self.category,
                severity=Severity.WARNING,
                risk=RiskLevel.MEDIUM,
                title="Fast Startup is disabled",
                detail="Fast Startup shortens cold boots using a hybrid shutdown state.",
                impact="Re-enabling it usually saves seconds per boot.",
                fix=registry_set(
                    wins.HKLM, key_path, "HiberbootEnabled", 1, "Enable Fast Startup"
                ),
            )
        ]


class UptimeCheck(Check):
    id = "startup.uptime"
    name = "System uptime since last boot"
    category = Category.STARTUP

    def run(self, ctx) -> List[Finding]:
        boot = ctx.ps_json(
            "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToString('u')"
        )
        if not boot:
            return []
        try:
            boot_dt = datetime.fromisoformat(boot)
        except (TypeError, ValueError):
            return []
        days = (datetime.now() - boot_dt).days
        if days <= 14:
            return []
        return [
            Finding(
                key="startup.uptime",
                check_id=self.id,
                category=self.category,
                severity=Severity.INFO,
                risk=RiskLevel.SAFE,
                title=f"System has not restarted in {days} days",
                detail=f"Last boot: {boot}",
                impact="A restart clears background cruft and applies pending updates.",
            )
        ]