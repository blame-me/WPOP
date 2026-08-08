# wpop — Windows Performance Optimizer

Scan your Windows PC, get a 0–100 health score, and apply reversible one-click
fixes. Read-only by default; every fix can be undone.

## Get started

- **`wpop.exe`** — the recommended way to run it. Double-click, accept the UAC
  prompt, and the optimizer opens **with full administrator access** (the exe's
  manifest requests elevation, so all HKLM/service/telemetry fixes work
  immediately). This is the more powerful launcher.
- **`wpop.bat`** — fallback launcher that uses `wpop.exe` if present, otherwise
  runs the GUI elevated via the bundled Python environment in `dev\.venv`.

The `.exe` vs `.bat` — **the .exe wins**:
- `.exe` carries a `requireAdministrator` manifest → Windows auto-prompts UAC
  and grants a true elevated token (no `runas`/launcher workaround, no console).
- `.bat` must re-launch itself through PowerShell `Start-Process -Verb RunAs`,
  which depends on the script path and needs the venv present.

## What it does

- ~23 built-in checks across Startup, Storage, Memory, Services, System, Health
  (autoruns, temp/browser/update caches, RAM pressure, telemetry services,
  power plan, SMART drive status, event-log errors, battery wear, Defender).
- Weighted health score + per-category breakdown + HTML/JSON reports.
- Reversible fixes: every apply snapshots under `%LOCALAPPDATA%\wpop\undo`, so
  anything can be rolled back (`undo` in the CLI/GUI).

## CLI (headless)

From `dev\`:

```
.\.venv\Scripts\python.exe -m wpop scan --html ..\report.html
.\.venv\Scripts\python.exe -m wpop apply storage.browser_cache --yes
.\.venv\Scripts\python.exe -m wpop undo 15702eac6bbe95b1
.\.venv\Scripts\python.exe -m wpop gui
```

Rebuild the exe:

```
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --windowed
    --name wpop --uac-admin launcher_gui.py
copy /Y dist\wpop.exe ..
```

Source, venv, and build tooling live in `dev\` to keep this folder a clean
distribution point.