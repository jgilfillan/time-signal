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

yes_no_prompt() {
  local prompt="$1"
  local answer
  while true; do
    read -r -p "$prompt [y/N]: " answer
    case "${answer,,}" in
      y|yes) return 0 ;;
      n|no|"") return 1 ;;
      *) warn "Please answer y or n." ;;
    esac
  done
}

is_ipv4() {
  local ip="$1"
  local IFS=.
  local octets
  read -r -a octets <<< "$ip"
  [ "${#octets[@]}" -eq 4 ] || return 1
  for octet in "${octets[@]}"; do
    [[ "$octet" =~ ^[0-9]+$ ]] || return 1
    [ "$octet" -ge 0 ] 2>/dev/null || return 1
    [ "$octet" -le 255 ] 2>/dev/null || return 1
  done
}

is_cidr() {
  local cidr="$1"
  [[ "$cidr" =~ ^[0-9]+$ ]] || return 1
  [ "$cidr" -ge 0 ] 2>/dev/null || return 1
  [ "$cidr" -le 32 ] 2>/dev/null || return 1
}

configure_static_ip() {
  if ! command -v ip &>/dev/null; then
    warn "'ip' command not found; skipping static IP assistant."
    return
  fi

  echo
  echo "Optional network setup"
  if ! yes_no_prompt "Do you want to configure a static IP now?"; then
    info "Static IP setup skipped"
    return
  fi

  local interfaces iface
  mapfile -t interfaces < <(ip -o link show | awk -F': ' '{print $2}' | grep -v '^lo$')

  if [ "${#interfaces[@]}" -eq 0 ]; then
    warn "No network interfaces found; skipping static IP assistant."
    return
  fi

  echo
  echo "Available interfaces:"
  for iface in "${interfaces[@]}"; do
    echo "  - $iface"
  done

  local default_iface="${interfaces[0]}"
  local default_ip
  default_ip=$(hostname -I 2>/dev/null | awk '{print $1}')
  local iface_choice ip_addr cidr gateway dns_servers

  while true; do
    read -r -p "Interface to configure [$default_iface]: " iface_choice
    iface_choice=${iface_choice:-$default_iface}
    if printf '%s\n' "${interfaces[@]}" | grep -Fxq "$iface_choice"; then
      break
    fi
    warn "Unknown interface '$iface_choice'."
  done

  while true; do
    read -r -p "Static IPv4 address${default_ip:+ [$default_ip]}: " ip_addr
    ip_addr=${ip_addr:-$default_ip}
    if [ -n "$ip_addr" ] && is_ipv4 "$ip_addr"; then
      break
    fi
    warn "Invalid IPv4 address. Example: 192.168.1.50"
  done

  while true; do
    read -r -p "CIDR prefix [24]: " cidr
    cidr=${cidr:-24}
    if is_cidr "$cidr"; then
      break
    fi
    warn "Invalid CIDR prefix. Example: 24"
  done

  while true; do
    read -r -p "Router / gateway IPv4 [192.168.1.1]: " gateway
    gateway=${gateway:-192.168.1.1}
    if is_ipv4 "$gateway"; then
      break
    fi
    warn "Invalid gateway IPv4 address."
  done

  while true; do
    read -r -p "DNS servers (space-separated) [1.1.1.1 8.8.8.8]: " dns_servers
    dns_servers=${dns_servers:-1.1.1.1 8.8.8.8}
    local dns_ok=1 dns
    for dns in $dns_servers; do
      if ! is_ipv4 "$dns"; then
        dns_ok=0
        break
      fi
    done
    if [ "$dns_ok" -eq 1 ]; then
      break
    fi
    warn "One or more DNS server IPs are invalid."
  done

  echo
  echo "Static IP summary:"
  echo "  Interface : $iface_choice"
  echo "  Address   : $ip_addr/$cidr"
  echo "  Gateway   : $gateway"
  echo "  DNS       : $dns_servers"

  if ! yes_no_prompt "Apply these settings to /etc/dhcpcd.conf?"; then
    info "Static IP setup cancelled"
    return
  fi

  local dhcpcd_conf="/etc/dhcpcd.conf"
  local backup_file="/etc/dhcpcd.conf.time-signal.bak.$(date +%Y%m%d%H%M%S)"

  if [ ! -f "$dhcpcd_conf" ]; then
    warn "$dhcpcd_conf was not found."
    warn "On your OS, static IP may be managed by NetworkManager instead."
    warn "Skipping static IP automatic setup."
    return
  fi

  cp "$dhcpcd_conf" "$backup_file"

  sed -i '/^# >>> time-signal static ip >>>$/,/^# <<< time-signal static ip <<</d' "$dhcpcd_conf"

  {
    echo
    echo "# >>> time-signal static ip >>>"
    echo "interface $iface_choice"
    echo "static ip_address=$ip_addr/$cidr"
    echo "static routers=$gateway"
    echo "static domain_name_servers=$dns_servers"
    echo "# <<< time-signal static ip <<<"
  } >> "$dhcpcd_conf"

  info "Updated $dhcpcd_conf"
  info "Backup saved to $backup_file"

  if systemctl list-unit-files | grep -q '^dhcpcd\.service'; then
    if systemctl restart dhcpcd; then
      info "dhcpcd restarted; static IP should be active now."
    else
      warn "Could not restart dhcpcd automatically. Reboot may be required."
    fi
  else
    warn "dhcpcd service not found. Reboot or reconfigure your network manager manually."
  fi
}

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

# ── Optional. Configure static IP ────────────────────────────────────────────
configure_static_ip

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
