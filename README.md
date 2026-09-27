# print-cli 🖨️

Print **any file to any printer** from the terminal. Works on **Linux + Windows** (macOS via CUPS too).

**Silent by design:** never opens a GUI print dialog or extra window. It spools directly —
CUPS (`lp`) on Linux/macOS, PowerShell spooler / `pywin32` on Windows.

**Zero-dependency install:** Python standard library only. No `pip install` wall of packages, no proprietary tools.

---

## Requirements

| OS | Need | Usually preinstalled? |
|----|------|------------------------|
| Linux | Python 3.9+ + CUPS client (`lp`, `lpstat`) | Yes (`sudo apt install cups-client python3` if missing) |
| Windows | Python 3.9+ from [python.org](https://www.python.org/downloads/) (tick **Add to PATH**) | PowerShell is built-in |
| macOS | Python 3.9+ + CUPS | Yes |

Check yours:

```bash
python3 --version   # or `py --version` on Windows
which lp lpstat     # Linux/macOS
```

Optional on Windows for extra-silent PDFs: `pip install pywin32`. Without it, printing falls back to PowerShell — still no dialog.

---

## Install — auto-installs what's missing

### Step 0 — get the code (fresh laptop)

```bash
git clone https://github.com/filip25-rgb/cli-print.git
cd cli-print
```

No git? Download the ZIP from GitHub and unzip, then `cd` into it.

### Step 1 — run the installer

```bash
# Linux / macOS — installs python3 + cups-client if absent, then shims `print-cli`:
bash install.sh --yes
# flags: --yes = don't ask, --no-deps = skip system packages, shim only

# Windows — double-click install.bat (installs Python via winget if missing):
install.bat
```

### Step 2 — make `print-cli` visible (Linux/macOS)

The shim lives at `~/.local/bin/print-cli`. If your shell says `print-cli: command not found`, do once:

```bash
export PATH="$HOME/.local/bin:$PATH"   # then restart the terminal
# fallback without PATH (always works):
~/.local/bin/print-cli list
python3 print_cli.py list
```

On Windows `install.bat` creates `print-cli.cmd` in this folder — either run `py print_cli.py ...` here, or add this folder to PATH (Settings > System > About > Advanced > Environment Variables), then `print-cli list`.

### Step 3 — verify (any OS)

```bash
print-cli doctor          # report + manual fix hints
print-cli doctor --fix    # auto-install missing pieces (may ask for sudo)
print-cli list            # you should see your printers
print-cli                 # guided wizard (easiest first print)
```

No installer needed if you prefer: `python3 print_cli.py ...` (Linux/macOS) or `py print_cli.py ...` (Windows) works directly — stdlib-only, zero pip packages. Optional full package install: `pipx install .` (needs `sudo apt install pipx python3-venv` on Ubuntu 24.04).

Manual equivalents: `sudo apt install python3 cups-client`, macOS `brew install python3 cups`, Windows Python from [python.org](https://www.python.org/downloads/).

---

## Usage — easiest first

```bash
# 1) guided wizard: pick file -> pick printer -> copies -> done (no popups)
print-cli

# 2) direct commands
print-cli list
print-cli list --json

# print anything (PDF, txt, md, png, jpg, ...) — no popup
# NOTE: you must give the file's path — print-cli does NOT search for files.
# Relative (document.pdf, docs/a.pdf), absolute (/home/you/docs/a.pdf),
# and ~/... forms all work. Tab-completion works. Wizard accepts drag-drop
# from the file manager (quotes are stripped) and re-prompts if not found.
# Only know part of the name? Find it first (ls / find / file manager),
# then paste the path.
print-cli print document.pdf
print-cli print document.pdf -p MyPrinter
print-cli print notes.txt -p hp_smart_printing -n 2 --job-name "my-job"

# CUPS options (Linux/macOS only, repeatable)
print-cli print doc.pdf -o sides=two-sided-long-edge -o fit-to-page -o media=A4

# preview what would run, without printing
print-cli print doc.pdf -p MyPrinter --dry-run

# queue / cancel
print-cli queue
print-cli queue -p MyPrinter
print-cli cancel MyPrinter-42     # CUPS id form
print-cli cancel 42 -p MyPrinter  # Windows needs -p
print-cli cancel-all -p MyPrinter # CUPS only

# default printer
print-cli default
print-cli default MyPrinter       # Linux/macOS (lpoptions -d)
```

Exit codes: `0` = ok, `1` = spooler error, `2` = usage/file error.

---

## How it works

| OS | list | print (silent) | queue | cancel |
|----|------|----------------|-------|--------|
| Linux/macOS | `lpstat -p -d -v` | `lp -d PRINTER -n N -o ... FILE` | `lpstat -o` | `cancel` / `lprm` |
| Windows | `Get-Printer` (wmic fallback) | `ShellExecute printto` (pywin32) else `Start-Process -Verb PrintTo` | `Get-PrintJob` | `Remove-PrintJob` |

"Any file" = whatever the OS spooler accepts. CUPS filters handle PDF/PS/TXT/PNG/JPEG out of the box; Windows uses the registered app for the extension, still without showing a dialog. Copies on Windows are emulated by spooling N times (no generic copies flag for arbitrary files).

---

## Project layout

```text
print_cli.py      # the whole CLI — stdlib only (argparse, subprocess, shutil, platform)
pyproject.toml    # `pip install -e .` / pipx packaging, exposes `print-cli`
requirements.txt  # empty on purpose (documents zero-dep)
install.sh        # Linux/macOS shim installer, no venv needed
install.bat       # Windows shim installer
README.md
.gitignore
```

---

## Troubleshooting

- `print-cli: command not found` → PATH step missed: `export PATH="$HOME/.local/bin:$PATH"`, restart terminal, or use `~/.local/bin/print-cli` / `python3 print_cli.py` directly
- `command not found: lpstat` (Linux) → `bash install.sh --yes`, or manually `sudo apt install cups-client` (dnf/pacman/zypper equivalents in `install.sh`)
- `externally-managed-environment` on `pip install` (Ubuntu 24.04) → don't fight it: no pip needed — use `python3 print_cli.py` or the shim; only for package installs use `pipx install .`
- `No printers found` → check CUPS (`lpstat -p`) on Linux, `Get-Printer` in PowerShell on Windows; USB/network printer must be added at OS level first
- Windows prints via wrong app → change the file extension's default app in Settings; `print-cli` uses that handler silently
- Nothing prints, no error → run `print-cli queue` to see if the job is held, and `print-cli print ... --dry-run` to inspect the exact spool command

---

## License

MIT — do what you want, no warranty.
