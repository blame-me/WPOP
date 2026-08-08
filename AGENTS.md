# AGENTS.md (distribution root)

This folder is a clean release point: `wpop.exe` (admin auto-elevating GUI) and
`wpop.bat` (launcher), plus this README.

**All source, the Python venv, and build tooling live in `dev\`.** Work there,
not here. Full dev guide: see `dev\AGENTS.md` (loaded automatically when you
operate inside `dev\`).

Quick facts for the root:
- Deliverable: `wpop.exe` (PyInstaller onefile, `--uac-admin` → runs as admin).
- To rebuild: run the PyInstaller build from `dev\`, then copy `dev\dist\wpop.exe` to `..\wpop.exe`.
- Tests: run from `dev\` (`dev\.venv\Scripts\python.exe -m pytest -q`). Import roots break if you run pytest from the repo root because `wpop/` sits under `dev\`.
- Env note: shell is PowerShell 5.1 (no `&&`; chain with `; if ($?) {...}`); `python3` is the broken Store alias.