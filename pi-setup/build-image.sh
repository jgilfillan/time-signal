#!/usr/bin/env bash
# build-image.sh — turn an image of your set-up master card into the image
# you write to every give-away card.
#
# Run on a Linux PC (not the Pi), as root:
#   sudo ./pi-setup/build-image.sh master.img time-signal-appliance.img
#
# Make master.img by reading the master Pi's SD card, e.g.
#   sudo dd if=/dev/sdX of=master.img bs=4M status=progress conv=fsync
#
# What it does to the copy (master.img itself is never modified):
#   1. shrinks the root filesystem to its contents plus some free space
#      (--root-free-mb, default 600)
#   2. adds a small ext4 partition labelled "tsdata" (--data-mb, default 64)
#      that pi-setup/setup-appliance.sh mounts at /data for Wi-Fi settings
#      and the app config
#   3. removes things that must not be shared between devices or that hold
#      your own details: saved Wi-Fi networks, machine-id, shell history,
#      logs, the app config used while testing
#   4. trims the image so it fits any SD card of the same size or larger
#
# Options:
#   --data-mb N        size of the data partition in MiB (default 64)
#   --root-free-mb N   free space left on the root filesystem (default 600)
#
# Needs: losetup, sfdisk, e2fsck, resize2fs, mkfs.ext4 (util-linux + e2fsprogs).

set -euo pipefail

DATA_MB=64
ROOT_FREE_MB=600
ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --data-mb) DATA_MB="$2"; shift 2 ;;
    --root-free-mb) ROOT_FREE_MB="$2"; shift 2 ;;
    -h|--help) sed -n '2,28p' "$0"; exit 0 ;;
    -*) echo "Unknown option: $1" >&2; exit 1 ;;
    *) ARGS+=("$1"); shift ;;
  esac
done
[ "${#ARGS[@]}" -eq 2 ] || { echo "Usage: sudo $0 master.img output.img [--data-mb N] [--root-free-mb N]" >&2; exit 1; }
SRC="${ARGS[0]}"; OUT="${ARGS[1]}"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; RESET='\033[0m'
info() { echo -e "  ${GREEN}✓${RESET}  $*"; }
warn() { echo -e "  ${YELLOW}!${RESET}  $*"; }
die()  { echo -e "  ${RED}✗${RESET}  $*" >&2; exit 1; }

[ "$EUID" -eq 0 ] || die "Run as root: sudo $0 ..."
for t in losetup sfdisk e2fsck resize2fs dumpe2fs mkfs.ext4 blkid; do
  command -v "$t" >/dev/null || die "Missing tool: $t (install util-linux and e2fsprogs)"
done
[ -f "$SRC" ] || die "No such image: $SRC"
[ ! -e "$OUT" ] || die "$OUT already exists — choose another name or delete it"
if ! [[ "$DATA_MB" =~ ^[0-9]+$ ]] || [ "$DATA_MB" -lt 16 ]; then die "--data-mb must be at least 16"; fi
[[ "$ROOT_FREE_MB" =~ ^[0-9]+$ ]] || die "--root-free-mb must be a number"

LOOPS=(); MNT=""
cleanup() {
  set +e
  [ -n "$MNT" ] && mountpoint -q "$MNT" && umount "$MNT"
  [ -n "$MNT" ] && rmdir "$MNT" 2>/dev/null
  for l in "${LOOPS[@]}"; do losetup -d "$l" 2>/dev/null; done
}
trap cleanup EXIT

# Attach one partition of the image as its own loop device, by byte offset.
# (Avoids relying on udev partition scanning, so it also works in WSL and
# containers.) Stores the loop device path in the variable named by $2.
part_field() {  # part_field N start|size
  sfdisk -d "$OUT" | awk -v d="${OUT}$1" '$1==d' | sed -E "s/.*$2= *([0-9]+).*/\1/"
}
attach_part() {  # attach_part N VARNAME
  local start size dev
  start=$(part_field "$1" start); size=$(part_field "$1" size)
  [[ "$start" =~ ^[0-9]+$ && "$size" =~ ^[0-9]+$ ]] || die "Couldn't read partition $1 of $OUT"
  dev=$(losetup --find --show --offset $(( start * 512 )) --sizelimit $(( size * 512 )) "$OUT")
  LOOPS+=("$dev")
  printf -v "$2" '%s' "$dev"
}
detach_all() { for l in "${LOOPS[@]}"; do losetup -d "$l"; done; LOOPS=(); }

# ── Check layout before copying ──────────────────────────────────────────────
nparts=$(sfdisk -d "$SRC" 2>/dev/null | grep -c "^${SRC}[0-9]* *:" || true)
[ "$nparts" -eq 2 ] || die "Expected 2 partitions (boot + root) in $SRC, found $nparts. Already processed?"

echo -e "\nBuilding $OUT from $SRC\n"
cp --sparse=always "$SRC" "$OUT"
info "Copied image"
p2_start=$(part_field 2 start)
[[ "$p2_start" =~ ^[0-9]+$ ]] || die "Couldn't read the root partition start"

attach_part 2 P2
[ "$(blkid -o value -s TYPE "$P2")" = "ext4" ] || die "Partition 2 is not ext4 — is this a Raspberry Pi OS image?"

# ── 1. Shrink the root filesystem ────────────────────────────────────────────
e2fsck -f -y "$P2" >/dev/null || [ $? -le 1 ] || die "e2fsck found errors on the root filesystem"
bs=$(dumpe2fs -h "$P2" 2>/dev/null | awk -F: '/^Block size/{gsub(/ /,"",$2); print $2}')
min_blocks=$(resize2fs -P "$P2" 2>/dev/null | awk -F: '/Estimated minimum size/{gsub(/ /,"",$2); print $2}')
cur_blocks=$(dumpe2fs -h "$P2" 2>/dev/null | awk -F: '/^Block count/{gsub(/ /,"",$2); print $2}')
target_bytes=$(( min_blocks * bs + ROOT_FREE_MB * 1024 * 1024 ))
align=$(( 4 * 1024 * 1024 ))
target_bytes=$(( (target_bytes + align - 1) / align * align ))
cur_bytes=$(( cur_blocks * bs ))
if [ "$target_bytes" -lt "$cur_bytes" ]; then
  resize2fs "$P2" "$(( target_bytes / 1024 ))K" >/dev/null
  info "Root filesystem shrunk from $(( cur_bytes / 1048576 )) MiB to $(( target_bytes / 1048576 )) MiB"
else
  target_bytes=$cur_bytes
  info "Root filesystem already small ($(( cur_bytes / 1048576 )) MiB); not shrinking"
fi
detach_all

# ── 2. Repartition: shrink p2, add p3 ────────────────────────────────────────
p2_sectors=$(( target_bytes / 512 ))
p3_start=$(( (p2_start + p2_sectors + 8191) / 8192 * 8192 ))
p3_sectors=$(( DATA_MB * 2048 ))
end_bytes=$(( (p3_start + p3_sectors) * 512 + 1024 * 1024 ))
img_bytes=$(stat -c %s "$OUT")
[ "$img_bytes" -ge "$end_bytes" ] || truncate -s "$end_bytes" "$OUT"
echo ",$p2_sectors" | sfdisk --no-reread --no-tell-kernel -N 2 "$OUT" >/dev/null 2>&1
echo "$p3_start,$p3_sectors,L" | sfdisk --no-reread --no-tell-kernel --append "$OUT" >/dev/null 2>&1
info "Root partition resized; data partition of $DATA_MB MiB added"

attach_part 2 P2; attach_part 3 P3
mkfs.ext4 -q -F -L tsdata -m 0 "$P3"
MNT=$(mktemp -d)
mount "$P3" "$MNT"
install -d -m 700 "$MNT/NetworkManager/system-connections"
install -d -m 755 "$MNT/time-signal"
umount "$MNT"
info "Data partition formatted (label tsdata) with empty Wi-Fi and config folders"

# ── 3. Scrub per-device and personal data from the root filesystem ───────────
mount "$P2" "$MNT"
grep -q 'LABEL=tsdata' "$MNT/etc/fstab" || warn "/etc/fstab has no tsdata entry — did setup-appliance.sh run on the master?"
removed=0
for f in "$MNT"/etc/NetworkManager/system-connections/*; do
  [ -e "$f" ] || continue
  rm -f "$f"; removed=$((removed + 1))
done
info "Removed $removed saved Wi-Fi network(s) from the root filesystem"
: > "$MNT/etc/machine-id"
rm -f "$MNT"/root/.bash_history "$MNT"/home/*/.bash_history
rm -rf "$MNT"/var/log/journal/* 2>/dev/null || true
find "$MNT/var/log" -type f \( -name '*.gz' -o -name '*.[0-9]' \) -delete 2>/dev/null || true
find "$MNT/var/log" -type f -exec truncate -s 0 {} + 2>/dev/null || true
find "$MNT" -xdev -path '*/web/config.json' -type f -print -delete | sed "s|^$MNT|  removed test config: |" || true
if ls "$MNT"/etc/systemd/system/multi-user.target.wants/ssh*.service >/dev/null 2>&1; then
  warn "SSH is enabled in this image; every card will share the same SSH host keys and password."
fi
sync
umount "$MNT"
info "Cleared machine-id, shell history and logs"

e2fsck -f -y "$P2" >/dev/null || [ $? -le 1 ] || die "e2fsck reported problems on root after cleanup"
e2fsck -f -y "$P3" >/dev/null || [ $? -le 1 ] || die "e2fsck reported problems on the data partition"
detach_all

# ── 4. Trim the image ────────────────────────────────────────────────────────
truncate -s "$end_bytes" "$OUT"
info "Image trimmed to $(( end_bytes / 1048576 )) MiB"

echo
sfdisk -l "$OUT" | sed -n '/^Device/,$p'
echo
echo "Done: $OUT"
echo "Write it to each card with Raspberry Pi Imager (Use custom) or:"
echo "  sudo dd if=$OUT of=/dev/sdX bs=4M status=progress conv=fsync"
