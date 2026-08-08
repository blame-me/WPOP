"""Headless command-line interface: scan, list checks, apply fixes, undo."""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from wpop import __version__
from wpop.core import registry
from wpop.core.applier import Applier, undo_by_ids
from wpop.core.models import ScanReport
from wpop.core.scan import ScanManager
from wpop.report import to_html, to_json


def _print_summary(report: ScanReport) -> None:
    print(f"Scan finished in {report.duration:.1f}s  score={report.score:.0f}/100 "
          f"({report.verdict})")
    print(f"  critical={report.critical_count}  warning={report.warning_count}  "
          f"info={report.info_count}")
    for cat, score in sorted(report.category_scores.items(), key=lambda kv: kv[1]):
        print(f"  {cat:<12} {score:>5.0f}")
    print("  ---")
    for r in report.results:
        for f in r.findings:
            flag = "!" if f.severity.value == "critical" else (
                "+" if f.severity.value == "warning" else "-"
            )
            print(f"  {flag} [{f.risk.value}] {f.title}")
            if f.detail:
                print(f"       {f.detail.splitlines()[0]}")
            if f.fix:
                print(f"       fix: {f.fix.description}  (undo: {f.fix.undo_id})")


def cmd_scan(args: argparse.Namespace) -> int:
    manager = ScanManager()
    report = manager.run()
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            fh.write(to_json(report))
        print(f"Wrote JSON report to {args.json}")
    if args.html:
        with open(args.html, "w", encoding="utf-8") as fh:
            fh.write(to_html(report))
        print(f"Wrote HTML report to {args.html}")
    if not args.json and not args.html:
        _print_summary(report)
    return 0


def cmd_list(_args: argparse.Namespace) -> int:
    for check in registry.instantiate_all():
        print(f"{check.id:<36} {check.category.value:<10} {check.name}")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    manager = ScanManager()
    report = manager.run()
    applier = Applier.from_report(report)
    keys = args.keys

    if not args.yes:
        fixes = []
        for key in keys:
            for f in report.all_findings:
                if f.key == key and f.fix:
                    fixes.append(f)
        if not fixes:
            print("No fixable finding matched; nothing to apply.")
            return 1
        print(f"About to apply {len(fixes)} fix(es). Use --yes to confirm.")
        for f in fixes:
            print(f"  - {f.fix.description}")
        return 0

    results = applier.apply(keys)
    by_key = {f.key: f for f in report.all_findings}
    ok = True
    for key, success, message in results:
        fix = by_key.get(key).fix if by_key.get(key) else None
        hint = f"  (undo: {fix.undo_id})" if success and fix and fix.undo_id else ""
        print(f"  {key:>40}  {'OK' if success else 'ERR'}  {message}{hint}")
        ok = ok and success
    return 0 if ok else 1


def cmd_undo(args: argparse.Namespace) -> int:
    results = undo_by_ids(args.ids)
    ok = True
    for uid, success, message in results:
        print(f"  {uid:>40}  {'OK' if success else 'ERR'}  {message}")
        ok = ok and success
    return 0 if ok else 1


def cmd_history(_args: argparse.Namespace) -> int:
    from wpop.core import fixes

    entries = fixes.list_saved()
    if not entries:
        print("No applied fixes recorded.")
        return 0
    for uid in entries:
        meta = fixes.saved_meta(uid) or {}
        print(f"  {uid}  {meta.get('kind', '?')}  {meta.get('key_path', '')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wpop", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="run a full system scan")
    scan.add_argument("--json", metavar="FILE", help="write JSON report to FILE")
    scan.add_argument("--html", metavar="FILE", help="write HTML report to FILE")
    scan.set_defaults(func=cmd_scan)

    ls = sub.add_parser("list", help="list registered checks")
    ls.set_defaults(func=cmd_list)

    apply = sub.add_parser("apply", help="apply fixes for findings by key")
    apply.add_argument("keys", nargs="+", help="finding keys to fix")
    apply.add_argument("--yes", action="store_true", help="confirm without prompt")
    apply.set_defaults(func=cmd_apply)

    undo = sub.add_parser("undo", help="restore a previously applied fix")
    undo.add_argument("ids", nargs="+", help="undo ids (from history)")
    undo.set_defaults(func=cmd_undo)

    hist = sub.add_parser("history", help="list recorded fix snapshots")
    hist.set_defaults(func=cmd_history)

    gui = sub.add_parser("gui", help="launch the desktop app")
    gui.set_defaults(func=cmd_gui)
    return parser


def cmd_gui(_args: argparse.Namespace) -> int:
    from wpop.ui.app import main

    return main()


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())