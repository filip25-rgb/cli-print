#!/usr/bin/env bash
# Easy installer for print-cli (Linux / macOS).
# Needs only: python3 (>=3.9) + CUPS client (lp/lpstat, preinstalled on most distros).
# Zero pip dependencies — print_cli.py is stdlib-only.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python3}"

if ! command -v "$PY" >/dev/null 2>&1; then
  echo "error: python3 not found. Install it first:" >&2
  echo "  Ubuntu/Debian: sudo apt install python3" >&2
  echo "  macOS:         brew install python3" >&2
  exit 1
fi

"$PY" --version
chmod +x "$HERE/print_cli.py"

# 1) Fastest: zero-install check
"$PY" "$HERE/print_cli.py" --help >/dev/null && echo "OK: runs with: $PY $HERE/print_cli.py"

# 2) Optional: put `print-cli` on PATH via ~/.local/bin shim (no venv, no pip needed)
BIN_DIR="${HOME}/.local/bin"
mkdir -p "$BIN_DIR"
SHIM="$BIN_DIR/print-cli"
cat > "$SHIM" <<EOF
#!/usr/bin/env sh
exec "$PY" "$HERE/print_cli.py" "\$@"
EOF
chmod +x "$SHIM"
echo "Installed shim: $SHIM"
echo "Make sure ~/.local/bin is on PATH (restart terminal or: export PATH=\"\$HOME/.local/bin:\$PATH\")"

# 3) Optional full pip install (entry-point `print-cli` via pyproject):
#    Uses pipx if present (handles venv for you on PEP 668 systems like Ubuntu 24.04),
#    else a local venv. Uncomment to enable:
# if command -v pipx >/dev/null 2>&1; then
#   pipx install "$HERE"
# else
#   "$PY" -m venv "$HERE/.venv" && "$HERE/.venv/bin/pip" install -e "$HERE"
# fi

print-cli --help 2>/dev/null || "$SHIM" --help
echo "Done. Try: print-cli list"
