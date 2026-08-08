"""Health checks: event-log errors, SMART drive health, battery capacity, and
Windows Defender real-time protection."""
from __future__ import annotations

from typing import List

from wpop.core.models import (
    Category,
    Check,
    Finding,
    RiskLevel,
    Severity,
)


class EventLogCheck(Check):
    id = "health.event_log"
    name = "Recent system errors"
    category = Category.HEALTH

    def run(self, ctx) -> List[Finding]:
        count = ctx.ps_json(
            "@(Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2;"
            "StartTime=(Get-Date).AddDays(-7)} -ErrorAction SilentlyContinue).Count"
        )
        count = int(count or 0)
        if count <= 0:
            return []
        sev = Severity.CRITICAL if count > 50 else Severity.WARNING
        return [
            Finding(
                key="health.event_log",
                check_id=self.id,
                category=self.category,
                severity=sev,
                risk=RiskLevel.SAFE,
                title=f"{count} critical/error events in the System log in the last 7 days",
                detail="Review Event Viewer for crashes or failing drivers.",
                impact="Fixing the underlying driver/app reduces future errors.",
            )
        ]


class DiskSmartCheck(Check):
    id = "health.smart"
    name = "Drive health (SMART)"
    category = Category.HEALTH

    def run(self, ctx) -> List[Finding]:
        data = ctx.ps_json(
            "Get-CimInstance -Namespace root\\wmi -ClassName "
            "MSStorageDriver_FailurePredictStatus -ErrorAction SilentlyContinue | "
            "Select-Object PredictFailure"
        )
        rows = data or []
        if isinstance(rows, dict):
            rows = [rows]
        failing = any(bool(r.get("PredictFailure")) for r in rows)
        if failing:
            return [
                Finding(
                    key="health.smart.predict_fail",
                    check_id=self.id,
                    category=self.category,
                    severity=Severity.CRITICAL,
                    risk=RiskLevel.SAFE,
                    title="A drive's SMART data indicates imminent failure",
                    impact="Back up now and plan to replace the affected disk.",
                )
            ]
        return []


class BatteryHealthCheck(Check):
    id = "health.battery"
    name = "Battery capacity"
    category = Category.HEALTH

    def run(self, ctx) -> List[Finding]:
        design = ctx.ps_json(
            "Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue | "
            "Select-Object -ExpandProperty DesignCapacity"
        )
        if not design:
            return []
        full = ctx.ps_json(
            "Get-CimInstance -Namespace root\\wmi -ClassName BatteryFullChargedCapacity "
            "-ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullChargedCapacity"
        )
        try:
            ratio = int(full) / int(design) * 100
        except (TypeError, ValueError):
            return []
        if ratio >= 75:
            return []
        return [
            Finding(
                key="health.battery",
                check_id=self.id,
                category=self.category,
                severity=Severity.WARNING,
                risk=RiskLevel.SAFE,
                title=f"Battery maximum charge has degraded to {ratio:.0f}% of design capacity",
                impact="High wear shortens runtime; consider replacing for long battery life.",
            )
        ]


class DefenderCheck(Check):
    id = "health.defender"
    name = "Windows Defender real-time protection"
    category = Category.HEALTH

    def run(self, ctx) -> List[Finding]:
        enabled = ctx.ps_json(
            "(Get-MpComputerStatus -ErrorAction SilentlyContinue).RealTimeProtectionEnabled"
        )
        if enabled is None:
            return []
        if enabled:
            return []
        return [
            Finding(
                key="health.defender",
                check_id=self.id,
                category=self.category,
                severity=Severity.CRITICAL,
                risk=RiskLevel.SAFE,
                title="Windows Defender real-time protection is not enabled",
                detail="Confirm a trusted third-party antivirus is active in its place.",
                impact="Ensures live malware protection is on.",
            )
        ]