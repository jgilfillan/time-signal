# CLAUDE.md — project context

Fork of harlock974/time-signal: a Raspberry Pi transmitter for radio-clock time
signals (JJY/MSF/WWVB/DCF77). The owner (Josh, Brisbane, Australia) uses it to
set JJY60 watches and plans to give assembled units to fellow watch enthusiasts.
This file records the decisions made so far so a new session can carry on.

## Repository map

- `time-signal.c`, `time-services.c`, `clock-control.c` — upstream C transmitter.
  Generates the carrier on GPIO4 (GPCLK0) and keys it per second. Needs root.
  Encodes JJY/DCF77/MSF time with `localtime()`, WWVB with `gmtime()`
  (but `localtime()` for its DST bits).
- `web/server.py` + `web/templates/index.html` — Flask control panel (port 8080)
  that starts/stops the binary. `install.sh` installs it as `time-signal-web`.
- `tests/test_server.py` — unittest suite; stubs the binary and `timedatectl`.
  Run `python3 -m unittest discover -s tests -v`.
- `pi-setup/` — turning a Pi into a plug-and-play give-away (see below).
- `docs/QUICKSTART.md` — one-page guide for people receiving a unit.
- `hardware/` — one folder per topic, each with a README: `schematic/`
  (circuit diagram, KiCad schematic render/PDF), `breadboard/` (layout PNG +
  interactive HTML), `antenna/`, `pcb/` (KiCad project, JLCPCB files,
  generator scripts), `enclosure/` (OpenSCAD, STLs). `hardware/README.md`
  is the index. The top-level README is the front page; its `#software`
  anchor is linked from hardware READMEs.

## Web server behaviour (changed in this fork)

- **Time-sync gate:** never transmit until `timedatectl show -p NTPSynchronized`
  is `yes` (the Pi has no RTC; before sync it starts at the last shutdown or
  image-build time). Autostart waits in a background thread; `/api/start`
  returns 409 unless `{"force": true}`. Disable with
  `TIMESIGNAL_REQUIRE_TIME_SYNC=0`.
- **Per-station time zone:** the binary is launched with `TZ` set from
  `SERVICE_TZ` (JJY → Asia/Tokyo, DCF77 → Europe/Berlin, MSF → Europe/London,
  WWVB → America/New_York for DST bits). The Pi's own zone is irrelevant.
- Config path and defaults come from env: `TIMESIGNAL_CONFIG`,
  `TIMESIGNAL_DEFAULT_SERVICE`, `TIMESIGNAL_DEFAULT_AUTOSTART`.
- **Config persistence:** `save_config` fsyncs the file and folder (units get
  unplugged without shutdown). `config_persistent()` checks `/proc/mounts`
  for the config folder's filesystem; overlay/tmpfs means it'd be lost at
  reboot (e.g. `/data` didn't mount), which is logged and shown as a warning
  row in the UI (`config_persistent` in `/api/status`). Save failures return
  500 with a message. The appliance drop-in orders the service
  `Wants=`/`After=data.mount`.
- `/api/status` also returns `time_synced`, `waiting_for_sync`,
  `station_time`/`station_tz`, `hostname`, `addresses`, `port`.
- Needs Python ≥ 3.9 (`zoneinfo`).

## Appliance design (pi-setup/)

Goal: recipient plugs in, picks Wi-Fi on a phone, done.
- **OS:** Raspberry Pi OS Lite **32-bit** so one image runs on Pi Zero W and
  Zero 2 W. NetworkManager (Bookworm+).
- **Wi-Fi onboarding:** Comitup (hotspot + captive portal when no known
  network). `ap_name: <hostname>`. Bluetooth onboarding was considered and
  rejected as more work and less reliable (BerryLan is unmaintained since 2024).
- **Hostname:** `timesignal-hostname.service` sets `<prefix>-<last 4 hex of
  CPU serial>` at every boot (stable per device, works with read-only root).
- **Storage:** read-only overlay root (`raspi-config nonint do_overlayfs 0`)
  plus a 64 MB ext4 partition labelled `tsdata` mounted at `/data`.
  `/data/NetworkManager/system-connections` is bind-mounted over NM's folder;
  the app config is `/data/time-signal/config.json`. fstab entries use `nofail`
  so the master (which has no data partition) still boots. NetworkManager has
  an ordering drop-in to start after those mounts.
- Journald `Storage=volatile`; NM `ipv4.dhcp-client-id=mac` because copied
  cards share a machine-id; SSH disabled by default.
- `setup-appliance.sh` runs on the master Pi. `build-image.sh` runs on a Linux
  PC: shrinks root, adds the data partition, scrubs Wi-Fi/machine-id/history/
  logs/test config, trims. It attaches partitions by offset (no udev needed).
  Tested on a synthetic image only; **not yet tested on a real Pi**.

## Hardware (hardware/)

- **pHAT v1.2** (KiCad 7, 65 × 30 mm, Pi Zero footprint). Parallel LC tank —
  this matches the breadboard the owner built and confirmed works:
  5V → R1 220 Ω → node B; coil (J2 screw terminal) ∥ C1 10 nF ∥ C2 1.5 nF
  (C0G) between node B and node A; Q1 AO3400A drain on node A, source GND;
  gate from GPIO4 via R2 470 Ω, R3 100 kΩ pull-down; C6 10 µF on 5 V.
  C3/C4 (1206) and C5 (leaded) are empty tuning spots.
  Note: harlock974's original has the cap in *series* with the coil; we kept
  the parallel version because it's what was tested.
- Both GND pours have a keep-out over the Pi Zero W/2W PCB antenna (port edge,
  x 16–39 mm, y 22.4–30 mm) so Wi-Fi isn't shielded. Zero 2 W antenna position
  is inferred, not confirmed from a drawing.
- JLCPCB: Standard assembly, both sides (J1 40-pin socket C2977589 on the
  bottom, J2 screw terminal C8465). BOM/CPL in `hardware/pcb/`. CPL rotations
  still need checking in JLC's preview. Not yet ordered.
- **Antenna:** 3 × 9 × 180 mm ferrite rods (Jaycar LF1012) in a triangle,
  ~55 turns 0.25 mm enamelled wire, tight single layer at the centre.
  ~610 µH needed for 11.5 nF at 60 kHz.
- **Enclosure:** OpenSCAD, 194 × 70 × 36 mm, Pi stack front-left on M2.5 ×
  11 mm male-female standoffs, antenna in four saddles along the back wall (cable-tie tunnels under the middle two, open both ends; 3 mm gap to the back wall),
  M3 lid screws. Checked for collisions with modelled parts; not yet printed.

## Open items

- Test `setup-appliance.sh` and `build-image.sh` on a real Pi and card.
- Confirm the breadboard's final capacitor total (owner to check); if it
  differs from 11.5 nF, change C1/C2 on the board.
- Order PCBs; print the enclosure; check port cut-outs with real cables.
- Upstream tested on Pi Zero W, Pi 3 B and Pi 4 B; Zero 2 W untested.

## Conventions

- Owner is in Australia: Jaycar part numbers, AUD, ACMA LIPD class licence.
- Keep the web UI dependency-free (vanilla JS, single template).
