"""Health-score computation. Each category scores 0-100 from the penalties of
its findings; the overall score is a weighted average over categories."""
from __future__ import annotations

from typing import Dict

from wpop.core.models import (
    CATEGORY_WEIGHTS,
    SEVERITY_POINTS,
    Category,
    ScanReport,
    Severity,
)

VERDICTS = (
    (90, "Excellent"),
    (75, "Good"),
    (55, "Fair"),
    (0, "Poor"),
)


def category_score(category: Category, scan_report: ScanReport) -> float:
    points = sum(
        SEVERITY_POINTS[f.severity]
        for r in scan_report.results
        if r.check.category is category
        for f in r.findings
    )
    return round(max(0.0, min(100.0, 100.0 - points)), 1)


def compute(report: ScanReport) -> ScanReport:
    scores: Dict[str, float] = {}
    weighted = 0.0
    total_weight = 0.0
    for category in Category:
        if category not in CATEGORY_WEIGHTS:
            continue
        sc = category_score(category, report)
        scores[category.value] = sc
        weighted += sc * CATEGORY_WEIGHTS[category]
        total_weight += CATEGORY_WEIGHTS[category]

    report.category_scores = scores
    report.score = round(weighted / total_weight, 1) if total_weight else 0.0

    worst = min(scores.values()) if scores else 100.0
    if worst <= 40.0:
        # A collapsed category (worst case: critical storm) must drag the
        # overall score down hard; a plain weighted mean hides it.
        report.score = round((report.score + worst) / 2.0, 1)

    for threshold, verdict in VERDICTS:
        if report.score >= threshold:
            report.verdict = verdict
            break
    return report