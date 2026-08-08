# AGENTS.md

Windows-native **PC performance optimizer** (Python 3.10, Windows). Scans the
system read-only, scores health, and offers reversible one-click fixes and a
PySide6 GUI. No Node/compilers anywhere.

## Commands (PowerShell — `& .venv\Scripts\python.exe`)

- Set up: `python -m venv .venv; & .venv\Scripts\python.exe -m pip install -r requirements.txt`
- Full scan: `& .venv\Scripts\python.exe -m wpop scan`
  - `scan --json report.json --html report.html` for exports
- CLI subcommands: `list`, `apply <key> [--yes]`, `undo <key>`, `history`, `gui`
- Tests: `& .venv\Scripts\python.exe -m pytest -q`
- Dev layout: this `dev\` folder holds everything (source, venv `dev\.venv`, build
  tooling). The repo root `..\` is only a distribution point: `wpop.exe` +
  `wpop.bat` + README. The exe can be rebuilt here, then copied back up to
  `..\wpop.exe`.
- Rebuild the exe: `& .venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile
  --windowed --name wpop --uac-admin launcher_gui.py`; then
  `copy /Y dist\wpop.exe ..` (outputs a self-elevating `requireAdministrator` exe).

## Architecture

- `wpop/core/` is GUI-free and must stay that way: `models.py` (Finding/Fix/severity/risk),
  `registry.py` (auto-detects check classes), `scan.py` (concurrent runs + cached
  PowerShell via `ScanContext.ps_json`), `scoring.py` (weighted 0-100), `fixes.py`
  (reversible fixes + JSON snapshots), `applier.py` (elevation, restore point,
  audit log), `elevation.py`, `safety.py`, `log.py`, `wins.py` (winreg/fs helpers).
- `wpop/checks/` — one file per category (startup, junk, memory, services, system,
  health). Each check is a `Check` subclass with `id`/`name`/`category` + `run(ctx)`.
  **Adding a new check class auto-registers it** — no wiring needed.
- `wpop/report.py` serializes to JSON/HTML; `wpop/cli.py` argparse; `wpop/ui/app.py`
  PySide6 window.

## Non-obvious rules

- **Scanning is read-only.** The only writes happen inside `Fix.apply()`, invoked
  from `apply`/GUI. Fixes are reversible: every apply writes a snapshot under
  `%LOCALAPPDATA%\wpop\undo\{saved,quarantine}\`.
- **HKLM registry fixes need elevation.** `Applier.apply` relaunches the process
  elevated when any selected fix has `needs_admin=True`; the unelevated process exits.
- Scoring caps the overall score when any category collapses below 40 (weighted
  mean hides a critical storm) — keep that guard.
- PowerShell is the telemetry pipe. `ScanContext.ps_json()` wraps output in
  `ConvertTo-Json` and caches by script string. Prefer psutil for live process/
  memory/disk data; registry via `wins` (stdlib `winreg`) never touches PowerShell.
- PowerShell `Get-ScheduledTask` and `Get-WinEvent` are slow (1-2s) but run in
  parallel threads, so they are acceptable. `Get-CimInstance` scans cheap.
- Encoding: `ps_raw` forces `[Console]::OutputEncoding` UTF-8; PowerShell wrapper
  also prefixs that because subprocess isn't given an encoding.

## Gotchas seen in the field

- Startup-folder check must filter `desktop.ini` and count only `.lnk/.url/.exe/...`
- Case-insensitive bloat matching (`b.lower() in n.lower()`).
- Pagefile default is `?:\pagefile.sys` — only flag "custom" when entries contain
  size numbers.
- `powercfg /getactivescheme` prints `GUID (Name)`.
- "PowerShell 5.1" shell here has no `&&`; chain with `; if ($?) { ... }`.
- `python3` is the broken Store alias; use `python`/`py` or the venv exe.

## Environment

Windows PowerShell 5.1. Git present (repo initialized; commit identity set
locally). Python 3.10 (`python`) + `py` 3.14. No Node/cargo/go/dotnet/gcc/make.
Temp workspace: `C:\Users\eden\AppData\Local\Temp\opencode`.