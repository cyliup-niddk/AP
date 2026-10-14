#!/usr/bin/env bash
# Install missing dependencies locally, prepare the library, and run in foreground.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
export PIP_CACHE_DIR="$VENV_DIR/.cache/pip"
NO_IMPORT=false
WITH_OCR=false
SETUP_ONLY=false
APP_ARGS=()
PDF_DIR="$SCRIPT_DIR"

usage() {
  cat <<'EOF'
Usage: ./start.sh [--setup-only] [app options]

Installs missing system tools using sudo (or Homebrew on macOS), prepares
.venv and questions.json if needed, then starts the local question library.
Existing PDFs, SQLite assignments, and JSON exports are preserved.

  ./start.sh
  ./start.sh --database /path/to/library.sqlite3 --no-import
  ./start.sh --port 8080
  ./start.sh --pdf-dir /path/to/pdfs
  ./start.sh --with-ocr
  ./start.sh --setup-only

Stop the foreground service with Ctrl+C. The Gemini extension must be loaded
manually in Chrome/Edge; instructions are printed after setup.
EOF
}
while (($#)); do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --setup-only) SETUP_ONLY=true; shift ;;
    --no-import) NO_IMPORT=true; APP_ARGS+=("$1"); shift ;;
    --with-ocr) WITH_OCR=true; shift ;;
    --pdf-dir)
      if (($# < 2)); then echo 'Missing value after --pdf-dir.' >&2; exit 2; fi
      PDF_DIR="$2"; APP_ARGS+=("$1" "$2"); shift 2 ;;
    --pdf-dir=*) PDF_DIR="${1#*=}"; APP_ARGS+=("$1"); shift ;;
    *) APP_ARGS+=("$1"); shift ;;
  esac
done
if [[ ! -d "$PDF_DIR" ]]; then echo "PDF directory does not exist: $PDF_DIR" >&2; exit 2; fi
PDF_DIR="$(cd -- "$PDF_DIR" && pwd)"

as_admin() {
  if [[ "$EUID" -eq 0 ]]; then "$@";
  elif command -v sudo >/dev/null 2>&1; then sudo "$@";
  else echo 'Installing system dependencies requires sudo or an administrator.' >&2; exit 1;
  fi
}
install_system() {
  echo 'Installing missing Python/Poppler system dependencies…'
  if command -v apt-get >/dev/null 2>&1; then
    as_admin apt-get update
    as_admin apt-get install -y python3 python3-pip python3-venv poppler-utils
  elif command -v dnf >/dev/null 2>&1; then
    as_admin dnf install -y python3 python3-pip poppler-utils
  elif command -v pacman >/dev/null 2>&1; then
    as_admin pacman -S --needed --noconfirm python python-pip poppler
  elif command -v brew >/dev/null 2>&1; then
    brew install python poppler
  else
    echo 'Install Python 3.10+, pip/venv, and Poppler (pdftotext, pdftoppm), then rerun.' >&2
    exit 1
  fi
}
if ! command -v python3 >/dev/null 2>&1 || { ! "$NO_IMPORT" && { ! command -v pdftotext >/dev/null 2>&1 || ! command -v pdftoppm >/dev/null 2>&1; }; }; then
  install_system
fi
if "$WITH_OCR" && ! command -v tesseract >/dev/null 2>&1; then
  if command -v dnf >/dev/null 2>&1; then as_admin dnf install -y tesseract tesseract-langpack-eng
  elif command -v apt-get >/dev/null 2>&1; then as_admin apt-get update; as_admin apt-get install -y tesseract-ocr tesseract-ocr-eng
  elif command -v pacman >/dev/null 2>&1; then as_admin pacman -S --needed --noconfirm tesseract tesseract-data-eng
  elif command -v brew >/dev/null 2>&1; then brew install tesseract
  else echo 'Install Tesseract and English language data, then rerun.' >&2; exit 1
  fi
fi
python3 - <<'PY'
import sys
if sys.version_info < (3,10):
    raise SystemExit('Python 3.10 or later is required. Upgrade Python and rerun start.sh.')
PY
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo 'Creating .venv (reusing compatible installed Python packages)…'
  if ! python3 -m venv --system-site-packages "$VENV_DIR"; then
    install_system
    python3 -m venv --system-site-packages "$VENV_DIR"
  fi
fi
# Avoid unnecessary network access when the dependency is already available.
if ! "$VENV_DIR/bin/python" - <<'PY' 2>/dev/null
import PIL
from PIL import Image, ImageDraw, ImageFont
version = tuple(int(part) for part in PIL.__version__.split('.')[:2])
assert version >= (10,1)
ImageFont.load_default(size=25)
PY
then
  if ! "$VENV_DIR/bin/python" -m pip --version >/dev/null 2>&1; then
    "$VENV_DIR/bin/python" -m ensurepip --upgrade
  fi
  "$VENV_DIR/bin/python" -m pip install -r "$SCRIPT_DIR/requirements.txt"
fi
"$VENV_DIR/bin/python" -m pip check
if ! "$NO_IMPORT" && [[ ! -f "$SCRIPT_DIR/questions.json" ]]; then
  echo 'Preparing questions.json for the Gemini extension…'
  "$VENV_DIR/bin/python" "$SCRIPT_DIR/pdf_to_json.py" "$PDF_DIR" -o "$SCRIPT_DIR/questions.json"
fi
cat <<EOF

Setup ready.
Gemini extension (one-time manual browser setup):
  Open chrome://extensions or edge://extensions, enable Developer mode,
  select Load unpacked, then choose:
  $SCRIPT_DIR/gemini-extension
  Open Gemini and sign in. Click the extension icon to use the classifier.

EOF
if "$SETUP_ONLY"; then exit 0; fi
# exec keeps Python in the foreground so Ctrl+C terminates the service.
exec "$VENV_DIR/bin/python" -u "$SCRIPT_DIR/app.py" "${APP_ARGS[@]}"
