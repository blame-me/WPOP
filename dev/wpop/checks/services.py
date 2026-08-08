"""Service checks: telemetry / bloat services most users do not need."""
from __future__ import annotations

import subprocess
from typing import Dict, List

from wpop.core.elevation import CREATE_NO_WINDOW
from wpop.core.models import Category, Check, Fix, Finding, RiskLevel, Severity

# (service key name, display name)
_TELEMETRY_SERVICES = [
    ("DiagTrack", "Connected User Experiences and Telemetry"),
    ("dmwappushservice", "WDM Push / telemetry"),
]


def _run_sc(*args: str) -> None:
    try:
        subprocess.run(
            ["sc.exe", *args],
            capture_output=True,
            creationflags=CREATE_NO_WINDOW,
        )
    except OSError:
        pass


def _service_fix(name: str, display: str) -> Fix:
    description = f"Stop and disable {display}"

    def apply() -> None:
        _run_sc("stop", name)
        _run_sc("config", name, "start=", "disabled")

    def undo() -> None:
        _run_sc("config", name, "start=", "demand")
        _run_sc("start", name)

    return Fix(description=description, apply=apply, undo=undo)


class TelemetryServicesCheck(Check):
    id = "services.telemetry"
    name = "Telemetry services"
    category = Category.SERVICES

    def run(self, ctx) -> List[Finding]:
        names = ",".join(n for n, _ in _TELEMETRY_SERVICES)
        raw = ctx.ps_raw(
            f"Get-Service {names} -ErrorAction SilentlyContinue | "
            "ForEach-Object { \"$($_.Name)=$($_.Status)\" }"
        )
        statuses = self._parse_status(raw)

        findings: List[Finding] = []
        for name, display in _TELEMETRY_SERVICES:
            state = statuses.get(name)
            if state != "Running":
                continue
            findings.append(
                Finding(
                    key=f"services.telemetry.{name.lower()}",
                    check_id=self.id,
                    category=self.category,
                    severity=Severity.WARNING,
                    risk=RiskLevel.ADVANCED,
                    title=f"{display} telemetry service is running",
                    detail="Collection of usage/telemetry data that most users do not need.",
                    impact="Disabling it reduces background activity and data sent to Microsoft.",
                    fix=_service_fix(name, display),
                )
            )
        return findings

    @staticmethod
    def _parse_status(raw: str) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for line in raw.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
        return out