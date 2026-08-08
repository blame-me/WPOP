"""Check discovery and report serialization tests."""
from __future__ import annotations

from wpop.core import registry
from wpop.core.models import (
    Category,
    Check,
    CheckResult,
    Finding,
    Fix,
    RiskLevel,
    ScanReport,
    Severity,
)
from wpop.report import to_dict, to_html, to_json


def test_discovery_finds_checks():
    classes = registry.discover()
    assert len(classes) >= 20


def test_discovery_ids_unique():
    checks = registry.instantiate_all()
    ids = [c.id for c in checks]
    assert len(ids) == len(set(ids))
    for c in checks:
        assert c.category in Category


def test_all_categories_present():
    checks = registry.instantiate_all()
    cats = {c.category for c in checks}
    for cat in (
        Category.STARTUP,
        Category.STORAGE,
        Category.MEMORY,
        Category.SYSTEM,
        Category.SERVICES,
        Category.HEALTH,
    ):
        assert cat in cats


def test_report_json_and_html_roundtrip():
    class StubCheck(Check):
        id = "stub.check"
        name = "stub"
        category = Category.HEALTH

        def run(self, ctx):
            return []

    report = ScanReport(
        started_at="now",
        duration=1.5,
        score=88.0,
        verdict="Good",
        category_scores={"Startup": 80.0},
        results=[CheckResult(check=StubCheck(), findings=[Finding(
            key="k", check_id="stub.check", category=Category.HEALTH,
            severity=Severity.WARNING, risk=RiskLevel.MEDIUM,
            title="t", fix=Fix("desc", lambda: None, lambda: None),
        )])],
    )
    data = to_dict(report)
    assert data["score"] == 88.0
    assert data["counts"]["warning"] == 1
    assert data["checks"][0]["findings"][0]["fix"]["description"] == "desc"
    assert "score" in to_json(report)

    html = to_html(report)
    assert "88/100" in html
    assert "WARNING" in html
    assert "desc" in html