"""Main window for the wpop desktop app: dashboard, findings list, apply/undo."""
from __future__ import annotations

import sys
from typing import List, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from wpop.core import fixes, wins
from wpop.core.applier import Applier
from wpop.core.elevation import is_admin, relaunch_elevated
from wpop.core.log import AuditLog
from wpop.core.models import ScanReport, Severity
from wpop.core.scan import ScanManager


class _ScanWorker(QThread):
    done = Signal(object)

    def run(self) -> None:
        report = ScanManager().run()
        self.done.emit(report)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("wpop - Windows Performance Optimizer")
        self.resize(880, 640)
        self.report: Optional[ScanReport] = None
        self.log = AuditLog()
        self._worker: Optional[_ScanWorker] = None

        self._build_ui()
        self.scan()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)

        head = QHBoxLayout()
        self.score_label = QLabel("--/100")
        self.score_label.setStyleSheet(
            "font-size:34px;font-weight:bold;padding:6px 14px;border-radius:8px;"
            "color:#fff;background:#888;"
        )
        self.verdict_label = QLabel("scanning...")
        self.verdict_label.setStyleSheet("font-size:18px;color:#57606a;")
        head.addWidget(self.score_label)
        head.addWidget(self.verdict_label)
        head.addStretch(1)
        self.scan_btn = QPushButton("Scan now")
        self.scan_btn.clicked.connect(self.scan)
        head.addWidget(self.scan_btn)
        self.undo_btn = QPushButton("Undo last fix")
        self.undo_btn.clicked.connect(self.undo_last)
        head.addWidget(self.undo_btn)
        root.addLayout(head)

        self.cats_label = QLabel("")
        self.cats_label.setWordWrap(True)
        root.addWidget(self.cats_label)

        self.findings = QListWidget()
        self.findings.itemClicked.connect(self._on_item_clicked)
        root.addWidget(self.findings, stretch=1)
        self.setCentralWidget(central)

    # --- scanning -----------------------------------------------------------

    def scan(self) -> None:
        self.scan_btn.setEnabled(False)
        self.verdict_label.setText("scanning system...")
        if self._worker and self._worker.isRunning():
            return
        self._worker = _ScanWorker()
        self._worker.done.connect(self._on_scan_done)
        self._worker.start()

    def _on_scan_done(self, report: ScanReport) -> None:
        self.report = report
        self.scan_btn.setEnabled(True)
        self._render(report)

    def _render(self, report: ScanReport) -> None:
        self.score_label.setText(f"{report.score:.0f}/100")
        color = "#cf222e" if report.score < 55 else (
            "#d99a06" if report.score < 80 else "#2ea44f"
        )
        self.score_label.setStyleSheet(
            "font-size:34px;font-weight:bold;padding:6px 14px;border-radius:8px;"
            f"color:#fff;background:{color};"
        )
        self.verdict_label.setText(f"{report.verdict}  "
                                   f"({report.critical_count} crit, "
                                   f"{report.warning_count} warn, "
                                   f"{report.info_count} info)")
        cats = "  |  ".join(
            f"{k}: {v:.0f}" for k, v in report.category_scores.items()
        )
        self.cats_label.setText(cats)

        self.findings.clear()
        for r in report.results:
            for f in r.findings:
                sev = f.severity.value
                text = (
                    f"[{sev.upper():>8}] [{f.risk.value:>8}] "
                    f"{f.title}"
                    + (f"\n      fix: {f.fix.description}" if f.fix else "")
                )
                item = QListWidgetItem(text)
                item.setData(Qt.UserRole, f.key)
                item.setToolTip(f.detail or f.impact or f.key)
                if sev == Severity.CRITICAL.value:
                    item.setForeground(Qt.red)
                elif sev == Severity.WARNING.value:
                    item.setForeground(Qt.darkYellow)
                self.findings.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        key = item.data(Qt.UserRole)
        finding = next(
            (f for f in (self.report.all_findings if self.report else [])
             if f.key == key and f.fix is not None),
            None,
        )
        if finding is None:
            return
        ret = QMessageBox.question(
            self, "Apply fix", f"{finding.fix.description}?\n\n"
            f"Risk: {finding.risk.value}. {finding.impact}",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ret == QMessageBox.Yes:
            self._apply(finding.key)

    def _apply(self, key: str) -> None:
        applier = Applier.from_report(self.report)
        if applier.needs_elevation([key]) and not is_admin():
            if not relaunch_elevated(["-m", "wpop", "apply", "--yes", key]):
                QMessageBox.warning(self, "Elevation", "Administrator approval cancelled.")
            else:
                QMessageBox.information(
                    self, "wpop", "Fix applied in an elevated window. Please scan to refresh."
                )
            return
        results = applier.apply([key])
        ok = all(success for _, success, _ in results)
        QMessageBox.information(
            self, "wpop apply",
            "\n".join(m for _, _, m in results),
        )
        self.scan()

    def undo_last(self) -> None:
        saved = fixes.list_saved()
        if not saved:
            QMessageBox.information(self, "wpop", "No applied fixes recorded.")
            return
        uid = saved[-1]
        meta = fixes.saved_meta(uid) or {}
        ret = QMessageBox.question(
            self, "Undo", f"Restore: {meta.get('key_path') or meta.get('kind', uid)}?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ret == QMessageBox.Yes:
            from wpop.core.applier import undo_by_ids

            undo_by_ids([uid])
            self.scan()


def main() -> int:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()