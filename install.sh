#!/usr/bin/env bash
# print-cli installer (Linux / macOS) — installs everything that's missing.
# Usage: bash install.sh [--yes] [--no-deps]
#   --yes      don't ask, assume yes (good for fresh laptops)
#   --no-deps  skip system package installs, just create the shim
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python3}"
YES=0; NO_DEPS=0
for a in "$@"; do case "$a" in --yes) YES=1;; --no-deps) NO_DEPS=1;; esac; done

ask() { # ask "msg" -> 0=yes
  if [ "$YES" = 1 ]; then return 0; fi
  read -r -p "$1 [Y/n] " r || true
  [[ "${r:-Y}" =~ ^[Yy]?$ ]]
}

have() { command -v "$1" >/dev/null 2>&1; }

echo "== print-cli setup =="

# 1) Python
if ! have "$PY"; then
  echo "python3 not found — installing..."
  if have apt; then sudo apt update && sudo apt install -y python3
  elif have dnf; then sudo dnf install -y python3
  elif have pacman; then sudo pacman -S --noconfirm python
  elif have zypper; then sudo zypper install -y python3
  elif have apk; then sudo apk add python3
  elif have brew; then brew install python3
  else echo "ERROR: install Python 3.9+ manually: https://www.python.org/downloads/"; exit 1; fi
fi
"$PY" --version

# 2) CUPS client (provides lp/lpstat/lpoptions) — the only system dep
if [ "$NO_DEPS" = 0 ] && ! have lpstat; then
  echo "'lpstat' not found (CUPS client missing)."
  if ask "Install it now?"; then
    if have apt; then sudo apt update && sudo apt install -y cups-client
    elif have dnf; then sudo dnf install -y cups-client
    elif have pacman; then sudo pacman -S --noconfirm libcups cups-client
    elif have zypper; then sudo zypper install -y cups-client
    elif have apk; then sudo apk add cups-client
    elif have brew; then brew install cups
    else echo "WARNING: no known package manager; install cups-client manually."; fi
  fi
fi

chmod +x "$HERE/print_cli.py"

# 3) Sanity: zero-install run + doctor (auto-fix anything left)
"$PY" "$HERE/print_cli.py" doctor || {
  echo "--- attempting auto-fix ---"
  "$PY" "$HERE/print_cli.py" doctor --fix || true
}

# 4) Put `print-cli` on PATH via ~/.local/bin shim (no venv/pip needed)
BIN_DIR="${HOME}/.local/bin"
mkdir -p "$BIN_DIR"
SHIM="$BIN_DIR/print-cli"
cat > "$SHIM" <<EOF
#!/usr/bin/env sh
exec "$PY" "$HERE/print_cli.py" "\$@"
EOF
chmod +x "$SHIM"
echo "Installed: $SHIM"
case ":$PATH:" in *":$BIN_DIR:"*) :;; *) echo "NOTE: add to PATH once: export PATH=\"\$HOME/.local/bin:\$PATH\" (then restart terminal)";; esac

"$SHIM" list || "$SHIM" doctor
echo "Done. Easiest: print-cli   (guided wizard)  |  print-cli list  |  print-cli doctor"
