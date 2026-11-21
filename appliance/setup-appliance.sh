#!/usr/bin/env bash
# setup-appliance.sh — turn a fresh Raspberry Pi OS Lite install into a
# plug-and-play time-signal transmitter you can give away.
#
# Run on the MASTER Pi (the one whose SD card you'll copy), from the repo:
#   sudo ./appliance/setup-appliance.sh [options]
#
# Options:
#   --service SVC      station to transmit by default (default: JJY60)
#   --prefix NAME      hostname / hotspot prefix (default: jjy)  → jjy-1a2b
#   --country CC       Wi-Fi country code (default: AU)
#   --keep-ssh         leave SSH enabled (default: SSH is turned off)
#   --enable-overlay   also switch on the read-only root filesystem.
#                      Do this LAST, after you've tested the master.
#
# What it sets up:
#   * builds time-signal and installs the web service (port 8080), with
#     autostart on and the default station preset
#   * Comitup: if no known Wi-Fi is found, the Pi opens a hotspot named after
#     its hostname; joining it from a phone shows a page to pick the home Wi-Fi
#   * a unique, stable hostname per Pi from its serial number (jjy-1a2b.local)
#   * mounts for a small writable data partition labelled "tsdata" at /data,
#     holding Wi-Fi settings and the app config (appliance/build-image.sh
#     adds that partition to the image)
#   * logs kept in RAM, DHCP identity tied to the Wi-Fi MAC address
#
# Tested target: Raspberry Pi OS Lite (32-bit) Bookworm or later, which runs on
# both the Pi Zero W and Pi Zero 2 W, so one image covers both.

set -euo pipefail

SERVICE=JJY60
PREFIX=jjy
COUNTRY=AU
KEEP_SSH=0
ENABLE_OVERLAY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --service) SERVICE="${2^^}"; shift 2 ;;
    --prefix) PREFIX="$2"; shift 2 ;;
    --country) COUNTRY="${2^^}"; shift 2 ;;
    --keep-ssh) KEEP_SSH=1; shift ;;
    --enable-overlay) ENABLE_OVERLAY=1; shift ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; RESET='\033[0m'
info() { echo -e "  ${GREEN}✓${RESET}  $*"; }
warn() { echo -e "  ${YELLOW}!${RESET}  $*"; }
die()  { echo -e "  ${RED}✗${RESET}  $*" >&2; exit 1; }

[ "$EUID" -eq 0 ] || die "Run as root: sudo $0"
case "$SERVICE" in DCF77|WWVB|JJY40|JJY60|MSF) ;; *) die "Unknown --service $SERVICE" ;; esac
[[ "$PREFIX" =~ ^[a-z][a-z0-9-]{0,20}$ ]] || die "--prefix must be lowercase letters/digits/hyphens"
[[ "$COUNTRY" =~ ^[A-Z]{2}$ ]] || die "--country must be a 2-letter code, e.g. AU"
command -v raspi-config >/dev/null || die "raspi-config not found — run this on Raspberry Pi OS"
command -v nmcli >/dev/null || die "NetworkManager not found — use Raspberry Pi OS Bookworm or later"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo -e "\ntime-signal appliance setup  (repo: $REPO_DIR)\n"

# ── 1. Packages ──────────────────────────────────────────────────────────────
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q build-essential python3-venv avahi-daemon
info "Build tools, Python venv and mDNS (avahi) installed"

if ! apt-get install -y -q comitup; then
  die "Couldn't install comitup from the package archive.
     Install it by hand (see https://davesteele.github.io/comitup/), then re-run this script."
fi
info "Comitup installed"

# ── 2. Wi-Fi country (Wi-Fi stays disabled without one) ──────────────────────
raspi-config nonint do_wifi_country "$COUNTRY"
info "Wi-Fi country set to $COUNTRY"

# ── 3. The transmitter and its web service ───────────────────────────────────
"$REPO_DIR/install.sh" --non-interactive
mkdir -p /etc/systemd/system/time-signal-web.service.d
cat > /etc/systemd/system/time-signal-web.service.d/appliance.conf <<EOF
[Service]
Environment=TIMESIGNAL_CONFIG=/data/time-signal/config.json
Environment=TIMESIGNAL_DEFAULT_SERVICE=$SERVICE
Environment=TIMESIGNAL_DEFAULT_AUTOSTART=1
Environment=TIMESIGNAL_REQUIRE_TIME_SYNC=1
Restart=always
EOF
# a config left on the master by testing would override the defaults
rm -f "$REPO_DIR/web/config.json"
info "Web service set to autostart $SERVICE once the clock is synchronised"

# ── 4. Unique hostname from the Pi's serial number, set at every boot ────────
cat > /usr/local/sbin/timesignal-hostname <<EOF
#!/bin/sh
# Sets a stable per-device hostname (${PREFIX}-XXXX from the CPU serial).
serial=\$(tr -d '\\000' < /proc/device-tree/serial-number 2>/dev/null)
[ -n "\$serial" ] || serial=\$(awk '/^Serial/{print \$3}' /proc/cpuinfo)
suffix=\$(printf '%s' "\$serial" | tail -c 4 | tr 'A-F' 'a-f')
[ -n "\$suffix" ] || suffix=0000
name="${PREFIX}-\$suffix"
[ "\$(hostname)" = "\$name" ] && exit 0
echo "\$name" > /etc/hostname
hostname "\$name"
if grep -q '^127\.0\.1\.1' /etc/hosts; then
  sed -i "s/^127\.0\.1\.1.*/127.0.1.1\t\$name/" /etc/hosts
else
  printf '127.0.1.1\t%s\n' "\$name" >> /etc/hosts
fi
EOF
chmod 755 /usr/local/sbin/timesignal-hostname
cat > /etc/systemd/system/timesignal-hostname.service <<'EOF'
[Unit]
Description=Set a unique time-signal hostname from the Pi serial number
DefaultDependencies=no
After=local-fs.target
Before=network-pre.target NetworkManager.service avahi-daemon.service comitup.service
Wants=network-pre.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/timesignal-hostname
RemainAfterExit=yes

[Install]
WantedBy=sysinit.target
EOF
systemctl enable timesignal-hostname.service
/usr/local/sbin/timesignal-hostname
info "Hostname is now $(hostname) (each Pi gets its own)"

# ── 5. Comitup: hotspot named after the hostname ─────────────────────────────
if [ -f /etc/comitup.conf ] && [ ! -f /etc/comitup.conf.orig ]; then
  cp /etc/comitup.conf /etc/comitup.conf.orig
fi
cat > /etc/comitup.conf <<'EOF'
# time-signal appliance settings (original kept in comitup.conf.orig)
ap_name: <hostname>
enable_appliance_mode: true
EOF
systemctl enable comitup.service
info "Comitup hotspot will be called $(hostname)"

# ── 6. Writable data partition for Wi-Fi settings and app config ─────────────
mkdir -p /data
if ! grep -q 'LABEL=tsdata' /etc/fstab; then
  cat >> /etc/fstab <<'EOF'
# time-signal appliance: writable data partition (added by build-image.sh)
LABEL=tsdata  /data  ext4  defaults,noatime,nofail,x-systemd.device-timeout=10s  0  2
/data/NetworkManager/system-connections  /etc/NetworkManager/system-connections  none  bind,nofail,x-systemd.requires-mounts-for=/data  0  0
EOF
fi
# NetworkManager must read its saved networks only after the bind mount is up
bind_unit=$(systemd-escape --path --suffix=mount /etc/NetworkManager/system-connections)
mkdir -p /etc/systemd/system/NetworkManager.service.d
cat > /etc/systemd/system/NetworkManager.service.d/timesignal-data.conf <<EOF
[Unit]
After=data.mount $bind_unit
EOF
info "/data and Wi-Fi settings bind-mount added to /etc/fstab"

# Stable DHCP identity per device (machine-id is shared across copied cards)
cat > /etc/NetworkManager/conf.d/90-timesignal.conf <<'EOF'
[connection]
ipv4.dhcp-client-id=mac
ipv6.dhcp-duid=ll
EOF
info "DHCP identity tied to each Pi's Wi-Fi MAC address"

# ── 7. Logs in RAM ───────────────────────────────────────────────────────────
mkdir -p /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/90-timesignal-volatile.conf <<'EOF'
[Journal]
Storage=volatile
RuntimeMaxUse=16M
EOF
info "System logs kept in RAM"

# ── 8. SSH ───────────────────────────────────────────────────────────────────
if [ "$KEEP_SSH" -eq 1 ]; then
  warn "SSH left enabled. Change the default password before you copy this card."
else
  systemctl disable --now ssh.service 2>/dev/null || true
  info "SSH disabled (use --keep-ssh to keep it)"
fi

systemctl daemon-reload

# ── 9. Optional read-only root ───────────────────────────────────────────────
if [ "$ENABLE_OVERLAY" -eq 1 ]; then
  raspi-config nonint do_overlayfs 0
  info "Read-only overlay root enabled (takes effect after reboot)"
else
  warn "Read-only root not enabled yet. When everything works, re-run with --enable-overlay."
fi

echo
echo "Done. Next:"
echo "  1. Reboot and test: join the '$(hostname)' hotspot, pick your Wi-Fi,"
echo "     then open http://$(hostname).local:8080"
echo "  2. Re-run with --enable-overlay once you're happy."
echo "  3. Shut down, copy the card to an image on a Linux PC and run"
echo "     appliance/build-image.sh on it to add the data partition."
