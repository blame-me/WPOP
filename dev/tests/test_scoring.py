"""Scoring-model tests: severity penalties, verdict thresholds, weighted mean."""
from __future__ import annotations

from wpop.core import scoring
from wpop.core.models import (
    Category,
    Check,
    CheckResult,
    Finding,
    RiskLevel,
    ScanReport,
    Severity,
)


class _FakeCheck(Check):
    id = "fake.check"
    name = "fake"
    category = Category.HEALTH

    def run(self, ctx):
        return []


def _report(severities):
    check = _FakeCheck()
    results = []
    for sev in severities:
        results.append(
            CheckResult(check=check, findings=[Finding(
                key=f"k{len(results)}", check_id="fake.check",
                category=Category.HEALTH, severity=sev, risk=RiskLevel.SAFE,
                title="t",
            )])
        )
    return ScanReport(started_at="x", duration=1.0, results=results)


def test_empty_report_scores_100():
    report = _report([])
    scoring.compute(report)
    assert report.score == 100.0
    assert report.verdict == "Excellent"


def test_each_severity_penalizes():
    info = _report([Severity.INFO])
    warn = _report([Severity.WARNING])
    crit = _report([Severity.CRITICAL])
    for r in (info, warn, crit):
        scoring.compute(r)
    assert info.score > warn.score > crit.score


def test_verdict_thresholds():
    perfect = _report([])
    scoring.compute(perfect)
    assert perfect.verdict == "Excellent"

    weak = _report([Severity.CRITICAL] * 6)
    scoring.compute(weak)
    assert weak.score < 55
    assert weak.verdict == "Poor"


def test_category_scores_isolated():
    check_a = _FakeCheck()
    check_a.category = Category.STARTUP
    results = [CheckResult(check=check_a, findings=[Finding(
        key="1", check_id="a", category=Category.STARTUP,
        severity=Severity.CRITICAL, risk=RiskLevel.SAFE, title="t",
    )])]
    report = ScanReport(started_at="x", duration=1.0, results=results)
    scoring.compute(report)
    # Startup 100-18 = 82; other categories untouched at 100.
    assert report.category_scores[Category.STARTUP.value] == 82.0
    assert report.category_scores[Category.MEMORY.value] == 100.0