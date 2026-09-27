#!/usr/bin/env python3
"""print-cli: easily print any file to any printer from the terminal.

Cross-platform (Linux + Windows, macOS via CUPS), stdlib-only, no
proprietary deps. Never opens a GUI print dialog -- everything goes
straight to the OS spooler (CUPS `lp` on Unix, PowerShell spooler on
Windows), so it stays silent/headless when possible.

Usage:
    print-cli                       # guided wizard (easiest: pick file + printer)
    print-cli print FILE [-p PRINTER] [-n COPIES] [-o OPTS] [--job-name NAME] [--dry-run]
    print-cli list [--json]
    print-cli queue [-p PRINTER]
    print-cli cancel JOB_ID [-p PRINTER]
    print-cli cancel-all [-p PRINTER]
    print-cli default [PRINTER_NAME]
    print-cli doctor [--fix]        # check + auto-install what's missing
"""
from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

VERSION = "0.1.0"

SYSTEM = platform.system()  # Linux, Windows, Darwin


# ---------------------------------------------------------------- helpers

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def run(cmd: list[str], dry_run: bool = False, capture: bool = True) -> subprocess.CompletedProcess | None:
    """Run cmd, or just print it in dry-run mode."""
    if dry_run:
        print("[dry-run] " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
        return None
    try:
        return subprocess.run(cmd, capture_output=capture, text=True, check=False)
    except FileNotFoundError:
        eprint(f"error: command not found: {cmd[0]}")
        sys.exit(1)


def need(prog: str) -> str:
    p = shutil.which(prog)
    if not p:
        eprint(f"error: required tool '{prog}' not found on PATH.")
        sys.exit(1)
    return p


def is_windows() -> bool:
    return SYSTEM == "Windows"


def is_unix_cups() -> bool:
    return SYSTEM in ("Linux", "Darwin")


# ------------------------------------------------- doctor / auto-install

def _pkg_manager() -> list[str] | None:
    """Return install command prefix for CUPS client, e.g. ['sudo','apt','install','-y']."""
    if SYSTEM == "Darwin":
        if shutil.which("brew"):
            return ["brew", "install"]
        return None
    if SYSTEM != "Linux":
        return None
    if shutil.which("apt"):
        return ["sudo", "apt", "install", "-y"]
    if shutil.which("dnf"):
        return ["sudo", "dnf", "install", "-y"]
    if shutil.which("pacman"):
        return ["sudo", "pacman", "-S", "--noconfirm"]
    if shutil.which("zypper"):
        return ["sudo", "zypper", "install", "-y"]
    if shutil.which("apk"):
        return ["sudo", "apk", "add"]
    return None


def doctor_report() -> tuple[list[tuple[str, bool, str]], list[str]]:
    """Return ([(name, ok, detail)], fix_hints). Pure check, no changes."""
    checks: list[tuple[str, bool, str]] = []
    hints: list[str] = []

    ok_py = sys.version_info >= (3, 9)
    checks.append(("python>=3.9", ok_py, platform.python_version()))
    if not ok_py:
        hints.append("Install Python 3.9+: Ubuntu `sudo apt install python3`, "
                     "macOS `brew install python3`, Windows https://www.python.org/downloads/")

    if is_unix_cups():
        for tool in ("lpstat", "lp", "lpoptions"):
            found = shutil.which(tool) is not None
            checks.append((tool, found, shutil.which(tool) or "missing"))
        if not shutil.which("lpstat"):
            mgr = _pkg_manager()
            if mgr:
                hints.append(f"Install CUPS client: `{' '.join(mgr)} cups-client`"
                             + (" `cups`" if SYSTEM == "Darwin" else ""))
            else:
                hints.append("Install your distro's cups-client package (provides lp/lpstat).")
        try:
            printers = cups_list_printers() if shutil.which("lpstat") else []
        except SystemExit:
            printers = []
        checks.append(("printers-found", len(printers) > 0, f"{len(printers)} found"))
        if not printers:
            hints.append("No printers found: add one in OS Settings first, then re-run `print-cli doctor`.")
        else:
            d = cups_default_printer()
            checks.append(("default-printer", d is not None, d or "none (use -p or `print-cli default NAME`)"))
    elif is_windows():
        pwsh = _pwsh()
        checks.append(("powershell", pwsh is not None, pwsh or "missing"))
        if not pwsh:
            hints.append("PowerShell is built into Windows 10/11 — repair via Windows Update.")
        try:
            import win32print  # type: ignore  # noqa
            checks.append(("pywin32 (optional)", True, "installed (most silent path)"))
        except ImportError:
            checks.append(("pywin32 (optional)", False, "not installed (PowerShell fallback still works, no dialog)"))
            hints.append("Optional, quieter PDFs: `py -m pip install pywin32`.")
        try:
            printers = win_list_printers() if pwsh else []
        except SystemExit:
            printers = []
        checks.append(("printers-found", len(printers) > 0, f"{len(printers)} found"))
        if not printers:
            hints.append("No printers found: add one in Settings > Printers first.")
    else:
        checks.append(("os", False, f"unsupported: {SYSTEM}"))
        hints.append("Supported: Linux, Windows, macOS.")
    return checks, hints


def cmd_doctor(args) -> int:
    checks, hints = doctor_report()
    print(f"print-cli doctor — {SYSTEM} / Python {platform.python_version()}")
    bad = 0
    for name, ok, detail in checks:
        print(f"  [{'OK ' if ok else 'FAIL'}] {name}: {detail}")
        if not ok and "(optional)" not in name and name != "default-printer":
            bad += 1
    if bad == 0 and not hints:
        print("\nAll good. Try: print-cli list")
        return 0
    if hints:
        print("\nFixes:")
        for h in hints:
            print(f"  - {h}")
    if getattr(args, "fix", False):
        return cmd_fix()
    if bad:
        print("\nRe-run with --fix to auto-install what's possible: print-cli doctor --fix")
        return 1
    return 0


def cmd_fix() -> int:
    """Auto-install missing system deps. Returns 0 if everything now OK."""
    print("Attempting auto-fix (may ask for sudo/admin)...")
    if is_unix_cups():
        if not shutil.which("lpstat"):
            mgr = _pkg_manager()
            if not mgr:
                eprint("error: no supported package manager found (apt/dnf/pacman/zypper/apk/brew). "
                       "Install cups-client manually.")
                return 1
            pkg = "cups" if SYSTEM == "Darwin" else "cups-client"
            print(f"$ {' '.join(mgr)} {pkg}")
            r = subprocess.run([*mgr, pkg])
            if r.returncode != 0:
                eprint("auto-install failed; try manually (see `print-cli doctor`).")
                return r.returncode
        # re-check
        checks, _ = doctor_report()
        hard_fail = [n for n, ok, _ in checks if not ok and "(optional)" not in n and n != "default-printer"]
        if hard_fail:
            eprint(f"still missing: {', '.join(hard_fail)}")
            return 1
        print("Fixed. Try: print-cli list")
        return 0
    if is_windows():
        try:
            import win32print  # type: ignore  # noqa
            print("pywin32 already installed.")
        except ImportError:
            print("Installing optional pywin32 for the most silent path...")
            r = subprocess.run([sys.executable, "-m", "pip", "install", "pywin32"])
            if r.returncode != 0:
                eprint("pywin32 install failed; PowerShell fallback still works (no dialog).")
                return 0  # not fatal
        print("Done. Try: print-cli list")
        return 0
    eprint(f"auto-fix not supported on {SYSTEM}.")
    return 1


# ------------------------------------------------------------------ wizard

def _prompt(msg: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"{msg}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(130)
    return val or (default or "")


def cmd_wizard(_args=None) -> int:
    """Guided mode: pick file -> pick printer -> copies -> print. Easiest path."""
    print("print-cli wizard — guided printing (no dialog windows pop up)\n")
    # 1) deps first: offer auto-fix if broken
    checks, _ = doctor_report()
    hard_fail = [n for n, ok, _ in checks if not ok and "(optional)" not in n
                 and n not in ("default-printer",)]
    if hard_fail:
        print(f"Missing: {', '.join(hard_fail)}")
        if _prompt("Auto-install what's missing? (y/n)", "y").lower() in ("y", "yes"):
            if cmd_fix() != 0:
                return 1
        else:
            eprint("Run `print-cli doctor` for manual steps.")
            return 1
    # 2) file
    while True:
        f = _prompt("File to print (drag-drop or type path, e.g. doc.pdf)")
        p = Path(f.strip().strip('"').strip("'")).expanduser()
        if p.exists() and p.is_file():
            break
        eprint(f"  not found: {p} — try again.")
    # 3) printer
    printers = win_list_printers() if is_windows() else cups_list_printers()
    if not printers:
        eprint("No printers found. Add one in OS Settings, then retry.")
        return 1
    print("\nPrinters:")
    for i, pr in enumerate(printers, 1):
        star = " (default)" if pr.get("default") else ""
        print(f"  {i}) {pr.get('name')}{star}")
    default_idx = next((str(i) for i, pr in enumerate(printers, 1) if pr.get("default")), "1")
    while True:
        sel = _prompt(f"Pick printer [1-{len(printers)}]", default_idx)
        if sel.isdigit() and 1 <= int(sel) <= len(printers):
            printer = printers[int(sel) - 1]["name"]
            break
        # also accept a name directly
        names = [pr["name"] for pr in printers]
        if sel in names:
            printer = sel
            break
        eprint("  invalid choice — enter the number or exact name.")
    copies = _prompt("Copies", "1")
    copies_n = int(copies) if copies.isdigit() and int(copies) >= 1 else 1
    print(f'\nWill print "{p.name}" to "{printer}" x{copies_n} (silent, no popup).')
    if _prompt("Print now? (y/n)", "y").lower() not in ("y", "yes"):
        print("Cancelled. Preview with: "
              f'print-cli print "{p}" -p "{printer}" -n {copies_n} --dry-run')
        return 0
    if is_windows():
        return win_print(p, printer, copies_n, dry_run=False)
    return cups_print(p, printer, copies_n, [], p.stem, dry_run=False)


# ------------------------------------------------------- Linux/macOS (CUPS)

def cups_default_printer() -> str | None:
    lpstat = shutil.which("lpstat")
    if not lpstat:
        return None
    r = subprocess.run([lpstat, "-d"], capture_output=True, text=True)
    # e.g. "system default destination: HP_LaserJet"
    out = (r.stdout or "").strip()
    if "default destination:" in out:
        return out.split("default destination:")[-1].strip() or None
    if "no system default destination" in out.lower():
        return None
    return None


def cups_list_printers() -> list[dict]:
    need("lpstat")
    r = subprocess.run(["lpstat", "-p", "-d"], capture_output=True, text=True)
    printers: list[dict] = []
    default = None
    for line in (r.stdout or "").splitlines():
        if "system default destination:" in line:
            default = line.split("system default destination:")[-1].strip()
        if line.startswith("printer "):
            # "printer NAME is idle. enabled since ..."
            parts = line.split()
            name = parts[1]
            state = "idle" if " is idle" in line else ("disabled" if "disabled" in line else "unknown")
            printers.append({"name": name, "status": state, "default": False})
    if default:
        for p in printers:
            p["default"] = (p["name"] == default)
    # device URIs via lpstat -v
    rv = subprocess.run(["lpstat", "-v"], capture_output=True, text=True)
    uris = {}
    for line in (rv.stdout or "").splitlines():
        # "device for NAME: uri..."
        if line.startswith("device for "):
            try:
                rest = line[len("device for "):]
                name, uri = rest.split(":", 1)
                uris[name.strip()] = uri.strip()
            except ValueError:
                pass
    for p in printers:
        if p["name"] in uris:
            p["device_uri"] = uris[p["name"]]
    return printers


def cups_print(path: Path, printer: str | None, copies: int,
               options: list[str], job_name: str | None, dry_run: bool) -> int:
    need("lp")
    if not path.exists():
        eprint(f"error: file not found: {path}")
        return 2
    cmd = ["lp"]
    if printer:
        cmd += ["-d", printer]
    if copies and copies != 1:
        cmd += ["-n", str(copies)]
    if job_name:
        cmd += ["-t", job_name]
    for o in options:
        cmd += ["-o", o]
    cmd.append(str(path))
    r = run(cmd, dry_run=dry_run, capture=False if not dry_run else True)
    if dry_run:
        return 0
    assert r is not None
    if r.returncode != 0:
        eprint((r.stderr or r.stdout or "lp failed").strip())
        return r.returncode
    # lp prints "request id is PRINTER-JOBID (N file(s))"
    print((r.stdout or "").strip())
    return 0


def cups_queue(printer: str | None) -> int:
    # lpstat -o shows all queued jobs; lpq shows nicely per-printer
    if shutil.which("lpstat"):
        cmd = ["lpstat", "-o"]
        if printer:
            cmd = ["lpstat", "-o", printer]
        r = run(cmd, dry_run=False)
        assert r is not None
        out = (r.stdout or "").strip()
        print(out if out else "(queue empty)")
        return r.returncode
    need("lpq")
    cmd = ["lpq"] + (["-P", printer] if printer else [])
    r = run(cmd, dry_run=False)
    assert r is not None
    print((r.stdout or "").strip() or "(queue empty)")
    return r.returncode


def cups_cancel(job_id: str, dry_run: bool = False) -> int:
    # job id forms: "PRINTER-123", "123", "printer/123"
    prog = shutil.which("cancel") or shutil.which("lprm")
    if not prog:
        eprint("error: neither 'cancel' nor 'lprm' found (cups-client missing?).")
        return 1
    r = run([prog, job_id], dry_run=dry_run, capture=False if not dry_run else True)
    if dry_run:
        return 0
    assert r is not None
    if r.returncode != 0:
        eprint((r.stderr or r.stdout or "cancel failed").strip())
    return r.returncode


def cups_cancel_all(printer: str | None, dry_run: bool = False) -> int:
    # cancel -a [printer]
    if shutil.which("cancel"):
        cmd = ["cancel", "-a"] + ([printer] if printer else [])
        r = run(cmd, dry_run=dry_run, capture=False if not dry_run else True)
        if dry_run:
            return 0
        assert r is not None
        return r.returncode
    # lprm -P printer -  (remove all for printer) / lprm -a all
    need("lprm")
    if printer:
        cmd = ["lprm", "-P", printer, "-"]
    else:
        cmd = ["lprm", "-a", "all"]
    r = run(cmd, dry_run=dry_run, capture=False if not dry_run else True)
    if dry_run:
        return 0
    assert r is not None
    return r.returncode


def cups_set_default(printer: str, dry_run: bool = False) -> int:
    need("lpoptions")
    r = run(["lpoptions", "-d", printer], dry_run=dry_run, capture=False if not dry_run else True)
    if dry_run:
        return 0
    assert r is not None
    if r.returncode != 0:
        eprint((r.stderr or r.stdout or "").strip())
    else:
        print(f"default printer -> {printer}")
    return r.returncode


# ------------------------------------------------------------- Windows

def _pwsh() -> str | None:
    for c in ("pwsh", "powershell"):
        if shutil.which(c):
            return c
    return None


def win_list_printers() -> list[dict]:
    pwsh = _pwsh()
    if pwsh:
        # Silent, no dialog: pure spooler query.
        ps = ("Get-Printer | Select-Object Name,DriverName,PortName,PrinterStatus,Default,Shared "
              "| ConvertTo-Json -Compress")
        r = subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-Command", ps],
                           capture_output=True, text=True)
        out = (r.stdout or "").strip()
        if out:
            try:
                data = json.loads(out)
                if isinstance(data, dict):
                    data = [data]
                result = []
                for d in data or []:
                    result.append({
                        "name": d.get("Name"),
                        "driver": d.get("DriverName"),
                        "port": d.get("PortName"),
                        "status": str(d.get("PrinterStatus")),
                        "default": bool(d.get("Default")),
                    })
                return result
            except json.JSONDecodeError:
                pass
    # Fallback: wmic (deprecated but present on Win10/11)
    wmic = shutil.which("wmic")
    if wmic:
        r = subprocess.run([wmic, "printer", "get", "name,default,printerstatus,portname", "/format:list"],
                           capture_output=True, text=True)
        printers, cur = [], {}
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if not line:
                if cur.get("name"):
                    printers.append(cur)
                cur = {}
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip().lower(), v.strip()
                if k == "name":
                    cur["name"] = v
                elif k == "default":
                    cur["default"] = v.upper() == "TRUE"
                elif k == "printerstatus":
                    cur["status"] = v
                elif k == "portname":
                    cur["port"] = v
        if cur.get("name"):
            printers.append(cur)
        return printers
    eprint("error: no printer query tool found (need PowerShell or wmic).")
    sys.exit(1)


def win_print(path: Path, printer: str | None, copies: int,
              dry_run: bool, job_name: str | None = None) -> int:
    """Silent print on Windows. No print dialog is ever shown.

    Strategy (in order):
    1. pywin32 (win32print + ShellExecute PRINTTO) if installed -- fully silent.
    2. PowerShell Start-Process -Verb PrintTo -- uses default file handler, no dialog.
    Copies are emulated by repeating the spool N times (Windows has no
    generic copies flag for arbitrary files).
    """
    if not path.exists():
        eprint(f"error: file not found: {path}")
        return 2
    abspath = str(path.resolve())

    if dry_run:
        print(f'[dry-run] Windows print "{abspath}"'
              + (f' to printer "{printer}"' if printer else " to default printer")
              + (f" x{copies}" if copies != 1 else ""))
        # show the actual fallback command that would run
        pwsh = _pwsh()
        if pwsh:
            verb = "PrintTo" if printer else "Print"
            arg = f' -ArgumentList \'"\'{printer}\'"\'"' if printer else ""
            print(f'[dry-run] {pwsh} -NoProfile -NonInteractive -Command '
                  f'Start-Process -FilePath "{abspath}" -Verb {verb}{arg} -WindowStyle Hidden')
        return 0

    # 1) pywin32 fast path (optional dep, still no dialog)
    try:
        import win32print  # type: ignore
        import win32api  # type: ignore
        use_pywin32 = True
    except ImportError:
        use_pywin32 = False

    if use_pywin32:
        import win32print  # type: ignore
        import win32api  # type: ignore
        for _ in range(max(1, copies)):
            if printer:
                # ShellExecute PRINTTO sends directly to named printer, no dialog
                win32api.ShellExecute(0, "printto", abspath, f'"{printer}"', ".", 0)
            else:
                win32api.ShellExecute(0, "print", abspath, "", ".", 0)
        print(f"sent {copies} copie(s) of {path.name}"
              + (f" to {printer}" if printer else " to default printer"))
        return 0

    # 2) PowerShell fallback
    pwsh = _pwsh()
    if not pwsh:
        eprint("error: on Windows need PowerShell or 'pip install pywin32' for silent printing.")
        return 1
    for _ in range(max(1, copies)):
        if printer:
            ps = (f'Start-Process -FilePath "{abspath}" -Verb PrintTo '
                  f'-ArgumentList \'"\'{printer}\'"\'" -WindowStyle Hidden')
        else:
            ps = f'Start-Process -FilePath "{abspath}" -Verb Print -WindowStyle Hidden'
        r = subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-Command", ps],
                           capture_output=True, text=True)
        if r.returncode != 0:
            eprint((r.stderr or r.stdout or "print failed").strip())
            return r.returncode
    print(f"sent {copies} copie(s) of {path.name}"
          + (f" to {printer}" if printer else " to default printer"))
    return 0


def win_queue(printer: str | None) -> int:
    pwsh = _pwsh()
    if not pwsh:
        eprint("error: need PowerShell to inspect the print queue on Windows.")
        return 1
    if printer:
        ps = (f"Get-PrintJob -PrinterName '{printer}' | "
              "Select-Object Id,DocumentName,JobStatus,SubmittedTime,Owner | Format-Table -AutoSize | Out-String -Width 200")
    else:
        ps = ("Get-Printer | ForEach-Object { $pn=$_.Name; Get-PrintJob -PrinterName $pn | "
              "Select-Object @{n='Printer';e={$pn}},Id,DocumentName,JobStatus,SubmittedTime } "
              "| Format-Table -AutoSize | Out-String -Width 200")
    r = subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-Command", ps],
                       capture_output=True, text=True)
    print((r.stdout or "").strip() or "(queue empty)")
    return r.returncode


def win_cancel(job_id: str, printer: str | None) -> int:
    pwsh = _pwsh()
    if not pwsh:
        eprint("error: need PowerShell to cancel jobs on Windows.")
        return 1
    if not printer:
        eprint("error: Windows cancel needs -p PRINTER plus the job Id. See 'queue' output.")
        return 2
    ps = f"Remove-PrintJob -PrinterName '{printer}' -ID {job_id}"
    r = subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-Command", ps],
                       capture_output=True, text=True)
    if r.returncode != 0:
        eprint((r.stderr or r.stdout or "cancel failed").strip())
    else:
        print(f"cancelled job {job_id} on {printer}")
    return r.returncode


# ------------------------------------------------------------------- CLI

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="print-cli",
        description="Print any file to any printer from the terminal. "
                    "Silent by design: never opens a GUI print dialog; "
                    "spools directly via CUPS (Linux/macOS) or the Windows spooler.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    sub = p.add_subparsers(dest="cmd", required=False)

    s = sub.add_parser("wizard", help="Guided mode: pick file + printer step by step (easiest)")
    s.set_defaults(cmd="wizard")

    s = sub.add_parser("doctor", help="Check dependencies/printers and show (or --fix) install steps")
    s.add_argument("--fix", action="store_true", help="Auto-install missing system packages (may ask for sudo)")

    s = sub.add_parser("setup", help="Alias for 'doctor --fix'")
    s.set_defaults(cmd="setup")

    s = sub.add_parser("list", aliases=["printers"], help="List available printers")
    s.add_argument("--json", action="store_true", help="Machine-readable JSON output")

    s = sub.add_parser("print", help="Print a file (PDF, text, image, ...) to a printer")
    s.add_argument("file", nargs="?", type=Path, default=None, help="File to print (omit for guided prompt)")
    s.add_argument("-p", "--printer", default=None, help="Printer name (default: system default)")
    s.add_argument("-n", "--copies", type=int, default=1, help="Number of copies (default: 1)")
    s.add_argument("-o", "--options", action="append", default=[],
                   help="CUPS -o option, repeatable (Linux/macOS only), e.g. -o sides=two-sided-long-edge -o fit-to-page")
    s.add_argument("--job-name", default=None, help="Job title shown in the queue")
    s.add_argument("--dry-run", action="store_true", help="Show the spool command without printing")

    s = sub.add_parser("queue", aliases=["jobs", "status"], help="Show pending print jobs")
    s.add_argument("-p", "--printer", default=None, help="Only this printer")

    s = sub.add_parser("cancel", help="Cancel one print job")
    s.add_argument("job_id", help="Job id (CUPS: 'Printer-123' or '123'; Windows: numeric Id, needs -p)")
    s.add_argument("-p", "--printer", default=None, help="Printer name (required on Windows)")
    s.add_argument("--dry-run", action="store_true", help="Show what would be cancelled")

    s = sub.add_parser("cancel-all", help="Cancel all jobs (optionally for one printer)")
    s.add_argument("-p", "--printer", default=None, help="Only this printer")
    s.add_argument("--dry-run", action="store_true", help="Show what would be cancelled")

    s = sub.add_parser("default", help="Show or set the default printer")
    s.add_argument("printer", nargs="?", default=None, help="If given, set as default (Linux/macOS via lpoptions)")

    return p


def cmd_list(args) -> int:
    printers = win_list_printers() if is_windows() else cups_list_printers()
    if args.json:
        print(json.dumps(printers, indent=2))
        return 0
    if not printers:
        print("(no printers found)")
        return 0
    for pr in printers:
        star = "*" if pr.get("default") else " "
        extra = ""
        if pr.get("status"):
            extra += f" [{pr['status']}]"
        if pr.get("device_uri"):
            extra += f" {pr['device_uri']}"
        elif pr.get("driver"):
            extra += f" ({pr['driver']})"
        print(f"{star} {pr.get('name')}{extra}")
    return 0


def cmd_print(args) -> int:
    if args.copies < 1:
        eprint("error: --copies must be >= 1")
        return 2
    if args.file is None:
        # `print-cli print` with no file -> guide instead of cryptic error
        eprint("no file given — launching guided mode.")
        return cmd_wizard()
    if is_windows():
        if args.options:
            eprint("warning: -o/--options is CUPS-only; ignored on Windows.")
        return win_print(args.file, args.printer, args.copies, args.dry_run, args.job_name)
    return cups_print(args.file, args.printer, args.copies, args.options, args.job_name, args.dry_run)


def cmd_queue(args) -> int:
    if is_windows():
        return win_queue(args.printer)
    return cups_queue(args.printer)


def cmd_cancel(args) -> int:
    if is_windows():
        return win_cancel(args.job_id, args.printer)
    return cups_cancel(args.job_id, dry_run=args.dry_run)


def cmd_cancel_all(args) -> int:
    if is_windows():
        eprint("error: cancel-all on Windows: cancel jobs one by one via 'queue' + 'cancel -p PRINTER ID'.")
        return 1
    return cups_cancel_all(args.printer, dry_run=args.dry_run)


def cmd_default(args) -> int:
    if is_windows():
        printers = win_list_printers()
        for pr in printers:
            if pr.get("default"):
                if args.printer:
                    eprint("note: setting default on Windows: use Settings > Printers or "
                           "PowerShell: (Get-WmiObject Win32_Printer ...). Showing current:")
                print(pr.get("name"))
                return 0
        print("(no default printer)")
        return 0
    if args.printer:
        return cups_set_default(args.printer, dry_run=False)
    d = cups_default_printer()
    print(d if d else "(no system default destination)")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.cmd:
        # bare `print-cli` -> easiest path, not an error
        return cmd_wizard(args)
    if args.cmd == "wizard":
        return cmd_wizard(args)
    if args.cmd == "doctor":
        return cmd_doctor(args)
    if args.cmd == "setup":
        eprint("running setup = doctor --fix")
        return cmd_fix()
    if args.cmd in ("list", "printers"):
        return cmd_list(args)
    if args.cmd == "print":
        return cmd_print(args)
    if args.cmd in ("queue", "jobs", "status"):
        return cmd_queue(args)
    if args.cmd == "cancel":
        return cmd_cancel(args)
    if args.cmd == "cancel-all":
        return cmd_cancel_all(args)
    if args.cmd == "default":
        return cmd_default(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
