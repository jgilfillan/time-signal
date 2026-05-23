#!/usr/bin/env bash
# install.sh — set up the time-signal web interface as a systemd service.
#
# Run once on your Raspberry Pi:
#   sudo ./install.sh
#
# What it does:
#   1. Builds the time-signal binary if it has not been built yet.
#   2. Creates a Python virtual environment and installs Flask into it.
#   3. Installs and starts a systemd service (time-signal-web) so the
#      web interface is available immediately and survives reboots.

set -euo pipefail

# ── Colour helpers ──────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BOLD='\033[1m'; RESET='\033[0m'
info()  { echo -e "  ${GREEN}✓${RESET}  $*"; }
warn()  { echo -e "  ${YELLOW}!${RESET}  $*"; }
error() { echo -e "  ${RED}✗${RESET}  $*" >&2; exit 1; }

# ── Root check ───────────────────────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
  error "Please run as root:  sudo ./install.sh"
fi

# ── Resolve project root ─────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BINARY="$SCRIPT_DIR/time-signal"
WEB_DIR="$SCRIPT_DIR/web"
VENV_DIR="$WEB_DIR/.venv"
SERVICE_SRC="$SCRIPT_DIR/time-signal-web.service"
SERVICE_DST="/etc/systemd/system/time-signal-web.service"

echo -e "\n${BOLD}time-signal web interface installer${RESET}\n"

# ── 1. Build the binary if needed ────────────────────────────────────────────
if [ ! -f "$BINARY" ]; then
  echo "Building time-signal binary …"
  make -C "$SCRIPT_DIR"
  info "Build successful"
else
  info "Binary already built: $BINARY"
fi

# ── 2. Ensure Python 3 is available ──────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  error "python3 not found. Install it with: sudo apt install python3"
fi
PY_VER=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
info "Python $PY_VER found"

# ── 3. Create virtual environment ────────────────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating Python virtual environment …"
  python3 -m venv "$VENV_DIR"
  info "Virtual environment created: $VENV_DIR"
else
  info "Virtual environment already exists: $VENV_DIR"
fi

# ── 4. Install Flask ─────────────────────────────────────────────────────────
echo "Installing Python dependencies …"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$WEB_DIR/requirements.txt"
info "Flask installed"

# ── 5. Install systemd service ───────────────────────────────────────────────
echo "Installing systemd service …"
sed "s|INSTALL_DIR|$SCRIPT_DIR|g" "$SERVICE_SRC" > "$SERVICE_DST"
info "Service file written: $SERVICE_DST"

# ── 6. Enable and (re)start the service ──────────────────────────────────────
systemctl daemon-reload
systemctl enable time-signal-web
systemctl restart time-signal-web
info "Service enabled and started"

# ── Done ─────────────────────────────────────────────────────────────────────
echo
echo -e "${BOLD}Installation complete!${RESET}"
echo
# Try to find the Pi's local IP address
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -n "$LOCAL_IP" ]; then
  echo -e "  Web interface: ${BOLD}http://$LOCAL_IP:8080${RESET}"
else
  echo -e "  Web interface: ${BOLD}http://<raspberry-pi-ip>:8080${RESET}"
fi
echo
echo "  Useful commands:"
echo "    sudo systemctl status  time-signal-web    # check status"
echo "    sudo journalctl -u     time-signal-web -f # follow logs"
echo "    sudo systemctl stop    time-signal-web    # stop the web server"
echo "    sudo systemctl disable time-signal-web    # disable autostart"
echo
