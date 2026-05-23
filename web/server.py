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
import subprocess
import threading
from typing import Dict, List, Optional, Tuple

from flask import Flask, jsonify, render_template, request

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
BINARY_PATH = os.path.join(BASE_DIR, '..', 'time-signal')
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')
PORT        = int(os.environ.get('TIMESIGNAL_PORT', 8080))

VALID_SERVICES = ('DCF77', 'WWVB', 'JJY40', 'JJY60', 'MSF')
SERVICE_INFO = {
    'DCF77': {'freq': '77.5 kHz', 'region': 'Europe'},
    'WWVB':  {'freq': '60 kHz',   'region': 'USA'},
    'JJY40': {'freq': '40 kHz',   'region': 'Japan'},
    'JJY60': {'freq': '60 kHz',   'region': 'Japan'},
    'MSF':   {'freq': '60 kHz',   'region': 'UK'},
}
DEFAULT_CONFIG: Dict = {'service': 'DCF77', 'autostart': False}
MAX_LOG_LINES = 200

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
    """Persist config to disk atomically."""
    tmp = CONFIG_PATH + '.tmp'
    with open(tmp, 'w') as fh:
        json.dump(cfg, fh, indent=2)
    os.replace(tmp, CONFIG_PATH)

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

        try:
            proc = subprocess.Popen(
                [binary, '-s', service],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            return False, str(exc)

        _proc = proc
        threading.Thread(
            target=_capture_output, args=(proc,), daemon=True
        ).start()
        return True, None


def stop_transmitter() -> None:
    """Stop the transmitter process."""
    with _proc_lock:
        _stop_locked()
    with _log_lock:
        _log_lines.append("■ Transmission stopped.")


def is_running() -> bool:
    """Return True if the transmitter process is currently running."""
    return _proc is not None and _proc.poll() is None

# ---------------------------------------------------------------------------
# Flask application
# ---------------------------------------------------------------------------

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)


@app.route('/')
def index():
    return render_template('index.html', services=VALID_SERVICES,
                           service_info=SERVICE_INFO)


@app.route('/api/status')
def api_status():
    """Return current transmitter status, config, and recent log lines."""
    cfg = load_config()
    with _log_lock:
        recent_logs = list(_log_lines[-50:])
    return jsonify({
        'running':   is_running(),
        'service':   cfg['service'],
        'autostart': cfg['autostart'],
        'logs':      recent_logs,
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
    if cfg.get('autostart'):
        logging.info(
            "Autostart is enabled – starting %s transmitter …", cfg['service']
        )
        ok, err = start_transmitter(cfg['service'])
        if not ok:
            logging.error("Autostart failed: %s", err)
    else:
        logging.info("Autostart is disabled – transmitter will not start automatically.")

    logging.info("Web interface available on http://0.0.0.0:%d", PORT)
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
