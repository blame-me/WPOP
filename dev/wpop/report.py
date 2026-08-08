"""Serialization of a ScanReport to JSON and a standalone HTML page."""
from __future__ import annotations

import html
import json
from typing import Any, Dict

from wpop.core.models import ScanReport


def score_class(score: float) -> str:
    if score < 55:
        return "low"
    if score < 80:
        return "mid"
    return "good"


def to_dict(report: ScanReport) -> Dict[str, Any]:
    return {
        "started_at": report.started_at,
        "duration_seconds": round(report.duration, 2),
        "score": report.score,
        "verdict": report.verdict,
        "category_scores": report.category_scores,
        "counts": {
            "critical": report.critical_count,
            "warning": report.warning_count,
            "info": report.info_count,
        },
        "checks": [
            {
                "id": r.check.id,
                "name": r.check.name,
                "category": r.check.category.value,
                "duration_ms": round(r.duration * 1000, 1),
                "error": r.error,
                "findings": [f.to_dict() for f in r.findings],
            }
            for r in report.results
        ],
    }


def to_json(report: ScanReport) -> str:
    return json.dumps(to_dict(report), indent=2, ensure_ascii=False)


def _cat_block(name: str, value: float) -> str:
    tone = "#cf222e" if value < 55 else ("#d99a06" if value < 80 else "#2ea44f")
    return (
        f'<div style="background:{tone};color:#fff;padding:.3rem .6rem;'
        f'border-radius:6px"><strong>{html.escape(name)}</strong> {value:.0f}/100</div>'
    )


def _finding_line(f: Dict[str, Any]) -> str:
    sev = f["severity"]
    classes = {"critical": "sev-critical", "warning": "sev-warning", "info": "sev-info"}
    body = (
        f'<span class="{classes[sev]}">{sev.upper()}</span> '
        f'<span class="risk">{f["risk"]}</span> '
        f"<strong>{html.escape(f['title'])}</strong>"
    )
    if f.get("detail"):
        body += f"<br><small>{html.escape(f['detail'])}</small>"
    if f.get("impact"):
        body += f"<br><small>{html.escape(f['impact'])}</small>"
    fix = f.get("fix")
    if fix:
        body += f'<br><small class="fix">Fix: {html.escape(fix["description"])}</small>'
    return f"<div>{body}</div>"


def to_html(report: ScanReport) -> str:
    findings_html = []
    for r in report.results:
        if not r.findings and not r.error:
            continue
        parts = []
        if r.error:
            parts.append(
                f'<div class="error"><strong>{html.escape(r.check.name)}</strong> '
                f"failed: {html.escape(r.error)}</div>"
            )
        for f in r.findings:
            parts.append(_finding_line(f.to_dict()))
        heading = (
            f"{html.escape(r.check.name)} "
            f"<small>({html.escape(r.check.category.value)})</small>"
        )
        findings_html.append(f"<details><summary>{heading}</summary>{''.join(parts)}</details>")

    cats = "".join(
        _cat_block(cat, score)
        for cat, score in sorted(report.category_scores.items(), key=lambda kv: kv[1])
    )

    values = {
        "VERDICT": html.escape(report.verdict or ""),
        "SCORE_CLASS": score_class(report.score),
        "SCORE_NUM": f"{report.score:.0f}",
        "STARTED": html.escape(report.started_at),
        "DURATION": f"{report.duration:.1f}",
        "CRITICAL": str(report.critical_count),
        "WARNING": str(report.warning_count),
        "INFO": str(report.info_count),
        "CATS": cats or "<p>no data</p>",
        "FINDINGS": "".join(findings_html) or "<p>All checks passed.</p>",
    }
    out = _HTML_TEMPLATE
    for key, val in values.items():
        out = out.replace("@@%s@@" % key, val)
    return out


_HTML_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>wpop report</title>
<style>
  body{font-family:Segoe UI,system-ui,sans-serif;margin:2rem;color:#1b1f23;background:#fff}
  h1{display:flex;align-items:baseline;gap:1rem;flex-wrap:wrap}
  .score-badge{font-size:1.9rem;font-weight:700;padding:.15rem .6rem;border-radius:8px;color:#fff}
  .score-good,.badge-good{background:#2ea44f}
  .score-mid,.badge-mid{background:#d99a06}
  .score-low,.badge-low{background:#cf222e}
  .sev-critical{color:#cf222e;font-weight:600}.sev-warning{color:#9a6700}.sev-info{color:#57606a}
  .risk{font-size:.75rem;padding:.1rem .4rem;border:1px solid #d0d7de;border-radius:10px;white-space:nowrap}
  .fix{font-size:.8rem;color:#0969da}.error{color:#cf222e}
  .grid{display:grid;gap:.6rem;max-width:900px}
  @media(min-width:700px){.grid{grid-template-columns:repeat(3,1fr)}}
  details{background:#f6f8fa;padding:.5rem .8rem;border-radius:6px;margin-bottom:.6rem}
  details summary small{color:#57606a}
  details summary{cursor:pointer;font-weight:600}
</style></head><body>
<h1>Windows Performance Optimizer <span style="color:#57606a;font-size:1.2rem">@@VERDICT@@</span></h1>
<p style="color:#57606a">Scanned @@STARTED@@ in @@DURATION@@s &middot;
   @@CRITICAL@@ critical, @@WARNING@@ warning, @@INFO@@ info findings</p>
<div class="score-badge badge-@@SCORE_CLASS@@">@@SCORE_NUM@@/100</div>
<h2>Category scores</h2>
<div class="grid">@@CATS@@</div>
<h2>Findings</h2>
@@FINDINGS@@
</body></html>"""