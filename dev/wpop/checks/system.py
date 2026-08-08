"""System-settings checks: active power plan, visual effects, hibernation, and
Windows Update cadence."""
from __future__ import annotations

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


class PowerPlanCheck(Check):
    id = "system.power_plan"
    name = "Active power plan"
    category = Category.SYSTEM

    def run(self, ctx) -> List[Finding]:
        raw = ctx.ps_raw("powercfg /getactivescheme")
        if ":" not in raw:
            return []
        parts = raw.split(":", 1)[1].strip().split("(", 1)
        # parts[1] ends with ')' -> plan name in parentheses
        plan = parts[1].rstrip(")").strip() if len(parts) > 1 else parts[0].strip()
        if not plan:
            return []
        return [
            Finding(
                key="system.power_plan",
                check_id=self.id,
                category=self.category,
                severity=Severity.INFO,
                risk=RiskLevel.MEDIUM,
                title=f"Active power plan: {plan}",
                detail="Balanced is fine for laptops; desktops get a slight edge from 'High performance'.",
                impact="Power plans trade a little responsiveness against battery life.",
            )
        ]


class VisualEffectsCheck(Check):
    id = "system.visual_effects"
    name = "Visual effects settings"
    category = Category.SYSTEM

    def run(self, ctx) -> List[Finding]:
        value = wins.get_value(
            wins.HKCU,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects",
            "VisualFxSetting",
        )
        if value is None:
            return []
        value = int(value)
        labels = {0: "Let Windows choose", 1: "Best appearance", 2: "Best performance", 3: "Custom"}
        label = labels.get(value, str(value))
        if value != 2:
            return []
        return [
            Finding(
                key="system.visual_effects",
                check_id=self.id,
                category=self.category,
                severity=Severity.INFO,
                risk=RiskLevel.MEDIUM,
                title="Visual effects are set to 'Best performance'",
                detail="Animations and transparency are turned off for speed.",
                impact="Switching back to 'Let Windows choose' restores smoother animations.",
                fix=registry_set(
                    wins.HKCU,
                    r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects",
                    "VisualFxSetting",
                    0,
                    "Restore visual effects to 'Let Windows choose'",
                ),
            )
        ]


class HibernationCheck(Check):
    id = "system.hibernation"
    name = "Hibernation file"
    category = Category.SYSTEM

    def run(self, ctx) -> List[Finding]:
        hibernate = wins.get_value(
            wins.HKLM,
            r"SYSTEM\CurrentControlSet\Control\Power",
            "HibernateEnabled",
        )
        enabled = str(hibernate).lower() in ("1", "true")
        if not enabled:
            return []
        return [
            Finding(
                key="system.hibernation",
                check_id=self.id,
                category=self.category,
                severity=Severity.INFO,
                risk=RiskLevel.ADVANCED,
                title="Hibernation is enabled",
                detail="hiberfil.sys typically reserves 40%+ of installed RAM on C:.",
                impact="Disabling it frees that space but removes fast resume-on-battery use.",
            )
        ]


class UpdateStatusCheck(Check):
    id = "system.updates"
    name = "Windows Update cadence"
    category = Category.SYSTEM

    def run(self, ctx) -> List[Finding]:
        last = ctx.ps_json(
            "(Get-HotFix -ErrorAction SilentlyContinue | "
            "Sort-Object InstalledOn -Descending | Select-Object -First 1).InstalledOn.ToString('u')"
        )
        if not last:
            return []
        from datetime import datetime

        try:
            last_dt = datetime.fromisoformat(last)
        except (TypeError, ValueError):
            return []
        days = (datetime.now() - last_dt).days
        if days < 60:
            return []
        return [
            Finding(
                key="system.updates",
                check_id=self.id,
                category=self.category,
                severity=Severity.WARNING,
                risk=RiskLevel.SAFE,
                title=f"No system updates installed in the last {days} days (since {last})",
                impact="Older builds miss security fixes; run Windows Update.",
            )
        ]