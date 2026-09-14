# WPOP — Windows Performance Optimizer

[![Windows](https://img.shields.io/badge/platform-Windows-blue)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/GUI-PySide6-green)]()
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**WPOP** scans your Windows PC, gives it a **0–100 health score**, and applies
**reversible one-click fixes**. Scanning is read-only by default — nothing
changes unless you say so, and every fix can be undone.

- 🖥️ **Desktop app** — double-click `wpop.exe`, accept the UAC prompt, get your score with per-category breakdowns.
- ⌨️ **Full CLI** — `scan`, `list`, `apply`, `undo`, `history` for scripting and headless runs.
- 📄 **Reports** — export results as HTML or JSON.
- ↩️ **Undo everything** — every applied fix snapshots to `%LOCALAPPDATA%\wpop\undo`.

## Quickstart

**No Python needed** — grab `wpop.exe` (and `wpop.bat`) and double-click:

1. Run **`wpop.exe`** → accept the UAC prompt (it needs admin for system-level checks like services and HKLM fixes).
2. Hit **Scan** → get your 0–100 score plus what's dragging it down.
3. Pick fixes → **Apply** → anything you don't like, **Undo**.

No exe handy? `wpop.bat` launches the same app, using `wpop.exe` when present or the bundled dev environment otherwise.

## What it checks

~23 built-in checks across six categories:

| Category | Examples |
|---|---|
| 🚀 Startup | Autorun entries, startup-folder clutter, slow scheduled tasks |
| 🗑️ Storage | Temp files, browser caches, Windows Update leftovers |
| 🧠 Memory | RAM pressure, pagefile config |
| ⚙️ Services | Telemetry services, unnecessary autostarts |
| 🖥️ System | Power plan, SMART drive status, Defender state |
| ❤️ Health | Event-log errors, battery wear |

Each finding carries a severity (`critical` / `warning` / `info`) and a risk tag, and the overall score is capped when any single category collapses — so one red zone can't hide behind a good average.

## CLI usage

From `dev\` with the virtualenv (see [Development](#development)):

```console
$ python -m wpop scan
Scan finished in 6.4s  score=82/100 (healthy)
  critical=0  warning=3  info=5
  startup        78
  storage        64
  ...

$ python -m wpop scan --json report.json --html report.html
Wrote JSON report to report.json
Wrote HTML report to report.html

$ python -m wpop list
startup.autoruns                     startup    Autorun entries
...

$ python -m wpop apply storage.browser_cache
About to apply 1 fix(es). Use --yes to confirm.

$ python -m wpop apply storage.browser_cache --yes
                 storage.browser_cache  OK  Cleared 412 MB  (undo: 15702eac6bbe95b1)

$ python -m wpop undo 15702eac6bbe95b1
                            15702eac6bbe95b1  OK  Restored
```

## Safety first

- **Read-only scanning.** The only writes on your system happen inside `Fix.apply()` — i.e. when *you* click Apply or run `apply --yes`.
- **Every fix is reversible.** Snapshots land in `%LOCALAPPDATA%\wpop\undo\{saved,quarantine}\`; `undo` / `history` manage them.
- **Elevation is explicit.** `wpop.exe` carries a `requireAdministrator` manifest so Windows prompts once up front. The CLI re-launches elevated only when a selected fix needs admin — otherwise it stays unelevated.
- **Dry by default.** `apply` without `--yes` just prints what *would* happen.

## Project layout

```
WPOP/
├── wpop.exe        # release build — PyInstaller onefile, auto-elevating GUI
├── wpop.bat        # launcher — prefers wpop.exe, falls back to dev venv
└── dev/            # all source + build tooling (see dev/AGENTS.md)
    ├── wpop/       # package: cli, report, core/, checks/, ui/
    │   ├── core/   # models, registry, scan, scoring, fixes, applier, safety
    │   ├── checks/ # one file per category — new checks auto-register
    │   └── ui/     # PySide6 desktop app
    ├── tests/      # pytest suite (scoring, fixes, report)
    └── launcher_gui.py  # PyInstaller entry point
```

## Development

```console
$ cd dev
$ python -m venv .venv
$ .\.venv\Scripts\python.exe -m pip install -r requirements.txt
$ .\.venv\Scripts\python.exe -m pytest -q
$ .\.venv\Scripts\python.exe -m wpop scan
```

Adding a check? Drop a `Check` subclass (`id` + `name` + `category` + `run(ctx)`) into `wpop/checks/` — it registers itself, no wiring needed.

Rebuild the exe:

```console
$ .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --windowed --name wpop --uac-admin launcher_gui.py
$ copy /Y dist\wpop.exe ..
```

## Troubleshooting

| Problem | Fix |
|---|---|
| UAC prompt on every launch | By design — system checks need admin; use CLI `scan` unelevated for a partial read-only pass |
| `pytest` import errors from repo root | Run pytest from `dev\`, not the repo root |
| A fix made things worse | `history` → grab the undo id → `undo <id>` |
| Missing scores for a category | That check likely needs elevation — rerun as admin |

## License

MIT — do what you want, no warranty. See [LICENSE](LICENSE).
