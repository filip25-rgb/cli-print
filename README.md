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

`install.sh` / `install.bat` detect your distro and install Python + CUPS client if absent, then give you a `print-cli` command. Nothing else needed (stdlib-only).

```bash
# Linux / macOS — fresh laptop? just run:
bash install.sh --yes
print-cli            # guided wizard (easiest)

# Windows — double-click install.bat (uses winget for Python if missing)
install.bat
```

Manual equivalents if you prefer: `sudo apt install python3 cups-client`, macOS `brew install python3 cups`, Windows Python from [python.org](https://www.python.org/downloads/).

Check health anytime (verifies python, lp/lpstat, printers, default):

```bash
print-cli doctor          # report + manual fix hints
print-cli doctor --fix    # auto-install missing pieces (may ask for sudo)
```

---

## Usage — easiest first

```bash
# 1) guided wizard: pick file -> pick printer -> copies -> done (no popups)
print-cli

# 2) direct commands
print-cli list
print-cli list --json

# print anything (PDF, txt, md, png, jpg, ...) — no popup
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

- `command not found: lpstat` (Linux) → `sudo apt install cups-client`
- `externally-managed-environment` on `pip install` (Ubuntu 24.04) → don't fight it: use **Option 0 / A** (no pip needed), or `pipx install .`
- `No printers found` → check CUPS (`lpstat -p`) on Linux, `Get-Printer` in PowerShell on Windows; USB/network printer must be added at OS level first
- Windows prints via wrong app → change the file extension's default app in Settings; `print-cli` uses that handler silently
- Nothing prints, no error → run `print-cli queue` to see if the job is held, and `print-cli print ... --dry-run` to inspect the exact spool command

---

## License

MIT — do what you want, no warranty.
