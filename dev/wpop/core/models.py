"""Core data model for wpop: categories, severities, findings, fixes, checks."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, List, Optional


class Category(str, Enum):
    STARTUP = "Startup"
    STORAGE = "Storage"
    MEMORY = "Memory"
    SERVICES = "Services"
    SYSTEM = "System"
    HEALTH = "Health"


CATEGORY_WEIGHTS: dict[Category, float] = {
    Category.STARTUP: 0.25,
    Category.MEMORY: 0.20,
    Category.STORAGE: 0.20,
    Category.SYSTEM: 0.15,
    Category.HEALTH: 0.10,
    Category.SERVICES: 0.10,
}


class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


SEVERITY_POINTS: dict[Severity, float] = {
    Severity.CRITICAL: 18.0,
    Severity.WARNING: 8.0,
    Severity.INFO: 2.0,
}


class RiskLevel(str, Enum):
    SAFE = "safe"
    MEDIUM = "medium"
    ADVANCED = "advanced"


@dataclass
class Fix:
    """A reversible remediation action.

    apply() performs the change; the matching undo() reverses it. undo_id links
    to a persistent snapshot when the fix was applied so undo works across
    processes. needs_admin marks fixes whose apply() requires elevation.
    """

    description: str
    apply: Callable[[], None]
    undo: Callable[[], None]
    undo_id: str = ""
    needs_admin: bool = False


@dataclass
class Finding:
    key: str
    check_id: str
    category: Category
    severity: Severity
    risk: RiskLevel
    title: str
    detail: str = ""
    impact: str = ""
    fix: Optional[Fix] = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "key": self.key,
            "check_id": self.check_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "risk": self.risk.value,
            "title": self.title,
            "detail": self.detail,
            "impact": self.impact,
        }
        if self.fix is not None:
            data["fix"] = {
                "description": self.fix.description,
                "risk": self.risk.value,
            }
        return data


@dataclass
class CheckResult:
    check: "Check"
    findings: List[Finding] = field(default_factory=list)
    duration: float = 0.0
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


class Check(ABC):
    """Base class for all checks. Subclasses live in wpop/checks and are
    discovered automatically (each module may define any number of them)."""

    id: str = ""
    name: str = ""
    category: Category = Category.SYSTEM

    def __init__(self) -> None:
        if not self.id:
            self.id = type(self).__name__

    @abstractmethod
    def run(self, ctx: Any) -> List[Finding]:
        """Inspect the system and return zero or more findings."""

    def __repr__(self) -> str:
        return f"<{type(self).__name__} id={self.id!r}>"


@dataclass
class ScanReport:
    started_at: str
    duration: float
    results: List[CheckResult]
    score: float = 0.0
    verdict: str = ""
    category_scores: dict[str, float] = field(default_factory=dict)

    @property
    def all_findings(self) -> List[Finding]:
        out: List[Finding] = []
        for r in self.results:
            out.extend(r.findings)
        return out

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.all_findings if f.severity == Severity.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.all_findings if f.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for f in self.all_findings if f.severity == Severity.INFO)