#!/usr/bin/env python3
"""
time-signal web server
Provides a browser-based UI to control the time-signal radio transmitter
from any device on the local network.

Run directly:
    sudo python3 web/server.py

Or via systemd after running install.sh.
"""

import json
import logging
import os
import socket
import subprocess
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, render_template, request

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

def _env_flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
BINARY_PATH = os.path.join(BASE_DIR, '..', 'time-signal')
PORT        = int(os.environ.get('TIMESIGNAL_PORT', 8080))

VALID_SERVICES = ('DCF77', 'WWVB', 'JJY40', 'JJY60', 'MSF')
SERVICE_INFO = {
    'DCF77': {'freq': '77.5 kHz', 'region': 'Europe'},
    'WWVB':  {'freq': '60 kHz',   'region': 'USA'},
    'JJY40': {'freq': '40 kHz',   'region': 'Japan'},
    'JJY60': {'freq': '60 kHz',   'region': 'Japan'},
    'MSF':   {'freq': '60 kHz',   'region': 'UK'},
}

# Each station broadcasts its own country's time. The transmitter binary
# encodes the time with localtime(), so it is started with TZ set to the
# station's zone. This keeps the signal correct whatever time zone the Pi
# itself is set to (e.g. a Pi in Brisbane still sends Japan time for JJY).
# WWVB sends UTC but uses the zone for its US daylight-saving bits.
SERVICE_TZ = {
    'DCF77': 'Europe/Berlin',
    'WWVB':  'America/New_York',
    'JJY40': 'Asia/Tokyo',
    'JJY60': 'Asia/Tokyo',
    'MSF':   'Europe/London',
}

_default_service = os.environ.get('TIMESIGNAL_DEFAULT_SERVICE', 'DCF77').upper()
if _default_service not in VALID_SERVICES:
    _default_service = 'DCF77'
DEFAULT_CONFIG: Dict = {
    'service':   _default_service,
    'autostart': _env_flag('TIMESIGNAL_DEFAULT_AUTOSTART', False),
}

# Refuse to transmit until the system clock has been set from the internet.
# A Pi has no battery-backed clock, so before NTP sync it can be hours or
# days out and would set every watch in range to the wrong time.
REQUIRE_TIME_SYNC = _env_flag('TIMESIGNAL_REQUIRE_TIME_SYNC', True)
MAX_LOG_LINES = 200


def _resolve_config_path() -> str:
    """Use TIMESIGNAL_CONFIG if its folder is writable, else web/config.json.

    On an appliance image the config lives on the writable data partition
    (/data), so it survives reboots even when the root filesystem is
    read-only.
    """
    fallback = os.path.join(BASE_DIR, 'config.json')
    wanted = os.environ.get('TIMESIGNAL_CONFIG')
    if not wanted:
        return fallback
    folder = os.path.dirname(wanted) or '.'
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        pass
    if os.path.isdir(folder) and os.access(folder, os.W_OK):
        return wanted
    logging.warning("Config folder %s not writable; using %s", folder, fallback)
    return fallback


CONFIG_PATH = _resolve_config_path()

# Filesystems whose contents vanish at reboot. With the read-only overlay
# enabled, "/" is an overlay backed by RAM, so a config written anywhere on
# it (including an empty /data folder when the data partition didn't mount)
# would look saved but be lost at the next restart.
VOLATILE_FS = {'overlay', 'tmpfs', 'ramfs'}
MOUNTS_FILE = '/proc/mounts'


def _mount_for(path: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (mount point, filesystem type) holding *path*, or (None, None)."""
    path = os.path.realpath(path)
    best: Tuple[Optional[str], Optional[str]] = (None, None)
    try:
        with open(MOUNTS_FILE) as fh:
            for line in fh:
                parts = line.split()
                if len(parts) < 3:
                    continue
                mnt = parts[1].replace('\\040', ' ')
                fstype = parts[2]
                inside = path == mnt or path.startswith(mnt.rstrip('/') + '/')
                if inside and (best[0] is None or len(mnt) >= len(best[0])):
                    best = (mnt, fstype)
    except OSError:
        pass
    return best


def config_persistent() -> Optional[bool]:
    """True if settings survive a reboot, False if not, None if unknown."""
    _, fstype = _mount_for(os.path.dirname(CONFIG_PATH))
    if fstype is None:
        return None
    return fstype not in VOLATILE_FS


class ConfigSaveError(Exception):
    pass

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config() -> Dict:
    """Load config from disk, merging with defaults."""
    try:
        with open(CONFIG_PATH) as fh:
            data = json.load(fh)
        return {**DEFAULT_CONFIG, **data}
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(DEFAULT_CONFIG)


def save_config(cfg: Dict) -> None:
    """Persist config to disk atomically.

    The file and its folder are fsync'd so a setting survives the plug being
    pulled straight afterwards, which is how most people will turn it off.
    """
    tmp = CONFIG_PATH + '.tmp'
    try:
        with open(tmp, 'w') as fh:
            json.dump(cfg, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, CONFIG_PATH)
        dir_fd = os.open(os.path.dirname(CONFIG_PATH), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError as exc:
        logging.error("Could not save settings to %s: %s", CONFIG_PATH, exc)
        raise ConfigSaveError("Couldn't save the settings on this device.") from exc
    if config_persistent() is False:
        logging.warning("Settings saved to %s, which is not on persistent "
                        "storage; they will be lost at the next restart.",
                        CONFIG_PATH)

# ---------------------------------------------------------------------------
# Transmitter process management
# ---------------------------------------------------------------------------

_proc: Optional[subprocess.Popen] = None
_proc_lock: threading.Lock = threading.Lock()
_log_lines: List[str] = []
_log_lock: threading.Lock = threading.Lock()


def _capture_output(proc: subprocess.Popen) -> None:
    """Background thread: drain subprocess stdout/stderr into the log buffer."""
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.rstrip()
        with _log_lock:
            _log_lines.append(line)
            if len(_log_lines) > MAX_LOG_LINES:
                _log_lines.pop(0)


def _stop_locked() -> None:
    """Stop the transmitter process. Must be called with _proc_lock held."""
    global _proc
    if _proc is not None and _proc.poll() is None:
        _proc.terminate()
        try:
            _proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _proc.kill()
            _proc.wait()
    _proc = None


def start_transmitter(service: str) -> Tuple[bool, Optional[str]]:
    """Start the time-signal binary for the given service.

    Returns (success, error_message).
    """
    global _proc
    with _proc_lock:
        _stop_locked()

        binary = os.path.realpath(BINARY_PATH)
        if not os.path.isfile(binary):
            return False, (
                f"Binary not found: {binary}. "
                "Please run 'make' in the project root first."
            )
        if not os.access(binary, os.X_OK):
            return False, f"Binary is not executable: {binary}"

        with _log_lock:
            _log_lines.clear()
            _log_lines.append(f"▶ Starting {service} transmission …")

        env = dict(os.environ, TZ=SERVICE_TZ[service])
        try:
            proc = subprocess.Popen(
                [binary, '-s', service],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )
        except OSError as exc:
            logging.error("Failed to start transmitter: %s", exc)
            return False, "Failed to launch the time-signal binary. Check server logs for details."

        _proc = proc
        threading.Thread(
            target=_capture_output, args=(proc,), daemon=True
        ).start()
        return True, None


def stop_transmitter() -> None:
    """Stop the transmitter process (and cancel a pending autostart)."""
    _autostart_cancel.set()
    with _proc_lock:
        _stop_locked()
    with _log_lock:
        _log_lines.append("■ Transmission stopped.")


def is_running() -> bool:
    """Return True if the transmitter process is currently running."""
    return _proc is not None and _proc.poll() is None


def _log(line: str) -> None:
    with _log_lock:
        _log_lines.append(line)
        if len(_log_lines) > MAX_LOG_LINES:
            _log_lines.pop(0)

# ---------------------------------------------------------------------------
# System clock synchronisation
# ---------------------------------------------------------------------------

_sync_cache: Dict = {'checked': 0.0, 'synced': None}


def time_synced() -> Optional[bool]:
    """True once systemd reports the clock is NTP-synchronised.

    Returns None when it can't be determined (no timedatectl, e.g. when
    developing on a non-systemd machine).
    """
    now = time.monotonic()
    if now - _sync_cache['checked'] < 5:
        return _sync_cache['synced']
    try:
        out = subprocess.run(
            ['timedatectl', 'show', '-p', 'NTPSynchronized', '--value'],
            capture_output=True, text=True, timeout=5,
        )
        synced: Optional[bool] = out.stdout.strip() == 'yes' if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        synced = None
    _sync_cache.update(checked=now, synced=synced)
    return synced


def clock_ok() -> bool:
    """Whether it's safe to transmit the system time."""
    if not REQUIRE_TIME_SYNC:
        return True
    return time_synced() is not False


_autostart_cancel = threading.Event()
_autostart_waiting = threading.Event()


def _autostart_worker(service: str) -> None:
    """Wait for the clock to be synchronised, then start transmitting."""
    if not clock_ok():
        _autostart_waiting.set()
        _log("… Waiting for internet time sync before transmitting.")
        logging.info("Autostart: waiting for NTP time sync")
        while not clock_ok():
            if _autostart_cancel.wait(5):
                _autostart_waiting.clear()
                return
        _autostart_waiting.clear()
        _log("✓ Clock synchronised.")
    if _autostart_cancel.is_set():
        return
    ok, err = start_transmitter(service)
    if not ok:
        logging.error("Autostart failed: %s", err)
        _log(f"✗ Autostart failed: {err}")


def schedule_autostart(service: str) -> None:
    _autostart_cancel.clear()
    threading.Thread(target=_autostart_worker, args=(service,), daemon=True).start()


def device_addresses() -> List[str]:
    """IPv4 addresses of this device, for display on the web page."""
    try:
        out = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=3)
        return [a for a in out.stdout.split() if '.' in a]
    except (OSError, subprocess.SubprocessError):
        return []

# ---------------------------------------------------------------------------
# Flask application
# ---------------------------------------------------------------------------

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)


@app.errorhandler(ConfigSaveError)
def _config_save_failed(exc):
    return jsonify({'error': str(exc)}), 500


@app.route('/')
def index():
    cfg = load_config()
    return render_template(
        'index.html',
        services=VALID_SERVICES,
        service_info=SERVICE_INFO,
        config=cfg,
    )


@app.route('/api/status')
def api_status():
    """Return current transmitter status, config, and recent log lines."""
    cfg = load_config()
    with _log_lock:
        recent_logs = list(_log_lines[-50:])
    service = cfg['service']
    station_time = datetime.now(ZoneInfo(SERVICE_TZ[service]))
    return jsonify({
        'running':      is_running(),
        'service':      service,
        'autostart':    cfg['autostart'],
        'logs':         recent_logs,
        'time_synced':  time_synced(),
        'waiting_for_sync': _autostart_waiting.is_set(),
        'station_time': station_time.strftime('%Y-%m-%d %H:%M:%S'),
        'station_tz':   station_time.tzname(),
        'hostname':     socket.gethostname(),
        'addresses':    device_addresses(),
        'port':         PORT,
        'config_persistent': config_persistent(),
    })


@app.route('/api/start', methods=['POST'])
def api_start():
    """Start the transmitter.

    Optional JSON body: {"service": "DCF77"}
    If omitted, the last-used service from config is used.
    """
    data = request.get_json(silent=True) or {}
    service = (data.get('service') or '').upper() or None

    cfg = load_config()
    if service and service in VALID_SERVICES:
        cfg['service'] = service
        save_config(cfg)
    elif not service:
        service = cfg['service']

    if service not in VALID_SERVICES:
        return jsonify({
            'error': f"Invalid service. Choose from: {', '.join(VALID_SERVICES)}"
        }), 400

    if not clock_ok() and not data.get('force'):
        return jsonify({
            'error': "The clock hasn't synchronised with internet time yet, so it "
                     "would send the wrong time. Check the Wi-Fi connection and "
                     "try again in a minute."
        }), 409

    _autostart_cancel.set()
    ok, err = start_transmitter(service)
    if not ok:
        return jsonify({'error': err}), 500
    return jsonify({'ok': True, 'service': service})


@app.route('/api/stop', methods=['POST'])
def api_stop():
    """Stop the transmitter."""
    stop_transmitter()
    return jsonify({'ok': True})


@app.route('/api/config', methods=['GET'])
def api_config_get():
    """Return the current configuration."""
    return jsonify(load_config())


@app.route('/api/config', methods=['POST'])
def api_config_post():
    """Update configuration.

    JSON body (all fields optional):
        {"service": "DCF77", "autostart": true}
    """
    data = request.get_json(silent=True) or {}
    cfg = load_config()
    changed = False

    if 'service' in data:
        svc = str(data['service']).upper()
        if svc not in VALID_SERVICES:
            return jsonify({'error': f"Invalid service. Choose from: {', '.join(VALID_SERVICES)}"}), 400
        cfg['service'] = svc
        changed = True

    if 'autostart' in data:
        cfg['autostart'] = bool(data['autostart'])
        changed = True

    if changed:
        save_config(cfg)
    return jsonify({'ok': True, 'config': cfg})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    cfg = load_config()
    logging.info("Config file: %s", CONFIG_PATH)
    if config_persistent() is False:
        logging.warning("%s is on a filesystem that is cleared at reboot "
                        "(is the data partition mounted?). Settings changed "
                        "in the web page will not be kept.", CONFIG_PATH)
    if cfg.get('autostart'):
        logging.info(
            "Autostart is enabled – starting %s transmitter …", cfg['service']
        )
        schedule_autostart(cfg['service'])
    else:
        logging.info("Autostart is disabled – transmitter will not start automatically.")

    logging.info("Web interface available on http://0.0.0.0:%d", PORT)
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
