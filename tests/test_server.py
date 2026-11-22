"""Tests for web/server.py that run without a Raspberry Pi.

They replace the transmitter binary and `timedatectl` with small stubs so the
time-sync gate, per-station time zones and config handling can be checked on
any Linux/macOS machine:

    python3 -m unittest discover -s tests -v
"""
import importlib
import json
import os
import stat
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'web'))


def _write_exec(path, body):
    with open(path, 'w') as fh:
        fh.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        # stub transmitter: report the TZ it was started with, then idle
        self.binary = os.path.join(t, 'time-signal')
        _write_exec(self.binary, '#!/bin/sh\necho "TZ=$TZ args=$*"\nexec sleep 30\n')
        # stub timedatectl driven by a file
        self.sync_file = os.path.join(t, 'synced')
        bindir = os.path.join(t, 'bin')
        os.mkdir(bindir)
        _write_exec(os.path.join(bindir, 'timedatectl'), f'#!/bin/sh\ncat "{self.sync_file}"\n')
        self.set_synced(True)
        self.old_path = os.environ['PATH']
        os.environ['PATH'] = bindir + os.pathsep + self.old_path
        os.environ['TIMESIGNAL_CONFIG'] = os.path.join(t, 'data', 'time-signal', 'config.json')
        os.environ['TIMESIGNAL_DEFAULT_SERVICE'] = 'JJY60'
        os.environ['TIMESIGNAL_DEFAULT_AUTOSTART'] = '1'
        os.environ.pop('TIMESIGNAL_REQUIRE_TIME_SYNC', None)
        if 'server' in sys.modules:
            del sys.modules['server']
        self.server = importlib.import_module('server')
        self.server.BINARY_PATH = self.binary
        self.client = self.server.app.test_client()

    def tearDown(self):
        self.server.stop_transmitter()
        os.environ['PATH'] = self.old_path
        for k in ('TIMESIGNAL_CONFIG', 'TIMESIGNAL_DEFAULT_SERVICE', 'TIMESIGNAL_DEFAULT_AUTOSTART'):
            os.environ.pop(k, None)
        self.tmp.cleanup()

    def set_synced(self, value):
        with open(self.sync_file, 'w') as fh:
            fh.write('yes\n' if value else 'no\n')
        if 'server' in sys.modules:
            sys.modules['server']._sync_cache['checked'] = 0.0

    def wait_for_log(self, text, timeout=5):
        end = time.time() + timeout
        while time.time() < end:
            logs = self.client.get('/api/status').get_json()['logs']
            if any(text in line for line in logs):
                return logs
            time.sleep(0.1)
        self.fail(f'log line containing {text!r} not seen; logs={logs}')

    def test_defaults_come_from_environment(self):
        cfg = self.client.get('/api/config').get_json()
        self.assertEqual(cfg, {'service': 'JJY60', 'autostart': True})

    def test_config_written_to_configured_path(self):
        self.client.post('/api/config', json={'autostart': False})
        with open(os.environ['TIMESIGNAL_CONFIG']) as fh:
            self.assertFalse(json.load(fh)['autostart'])

    def test_jjy_runs_in_japan_time(self):
        r = self.client.post('/api/start', json={'service': 'JJY60'})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.wait_for_log('TZ=Asia/Tokyo args=-s JJY60')

    def test_each_station_gets_its_zone(self):
        for svc, tz in self.server.SERVICE_TZ.items():
            r = self.client.post('/api/start', json={'service': svc})
            self.assertEqual(r.status_code, 200)
            self.wait_for_log(f'TZ={tz} args=-s {svc}')

    def test_start_refused_until_clock_synced(self):
        self.set_synced(False)
        r = self.client.post('/api/start', json={'service': 'JJY60'})
        self.assertEqual(r.status_code, 409)
        self.assertFalse(self.client.get('/api/status').get_json()['running'])
        r = self.client.post('/api/start', json={'service': 'JJY60', 'force': True})
        self.assertEqual(r.status_code, 200)

    def test_autostart_waits_for_sync(self):
        self.set_synced(False)
        self.server.schedule_autostart('JJY60')
        self.wait_for_log('Waiting for internet time sync')
        status = self.client.get('/api/status').get_json()
        self.assertFalse(status['running'])
        self.assertTrue(status['waiting_for_sync'])
        self.set_synced(True)
        self.wait_for_log('TZ=Asia/Tokyo', timeout=10)
        self.assertTrue(self.client.get('/api/status').get_json()['running'])

    def test_stop_cancels_pending_autostart(self):
        self.set_synced(False)
        self.server.schedule_autostart('JJY60')
        self.wait_for_log('Waiting for internet time sync')
        self.client.post('/api/stop')
        self.set_synced(True)
        time.sleep(6)
        status = self.client.get('/api/status').get_json()
        self.assertFalse(status['running'])
        self.assertFalse(status['waiting_for_sync'])

    def test_status_reports_station_time_and_device(self):
        s = self.client.get('/api/status').get_json()
        self.assertEqual(s['station_tz'], 'JST')
        self.assertTrue(s['time_synced'])
        self.assertIn('hostname', s)

    def fake_mounts(self, *lines):
        path = os.path.join(self.tmp.name, 'mounts')
        with open(path, 'w') as fh:
            fh.write(''.join(l + '\n' for l in lines))
        self.server.MOUNTS_FILE = path

    def test_config_on_data_partition_is_persistent(self):
        data = os.path.join(self.tmp.name, 'data')
        self.fake_mounts('overlayroot / overlay rw 0 0',
                         f'/dev/mmcblk0p3 {data} ext4 rw,noatime 0 0')
        self.assertTrue(self.server.config_persistent())
        self.assertTrue(self.client.get('/api/status').get_json()['config_persistent'])

    def test_config_on_overlay_flagged_not_persistent(self):
        # data partition didn't mount: /data is just a folder on the RAM overlay
        self.fake_mounts('overlayroot / overlay rw 0 0',
                         '/dev/mmcblk0p1 /boot/firmware vfat rw 0 0')
        self.assertFalse(self.client.get('/api/status').get_json()['config_persistent'])
        r = self.client.post('/api/config', json={'autostart': False})
        self.assertEqual(r.status_code, 200)   # still saved for this session

    def test_save_failure_returns_error(self):
        # e.g. the data partition went read-only or vanished
        self.server.CONFIG_PATH = os.path.join(self.tmp.name, 'gone', 'config.json')
        r = self.client.post('/api/config', json={'autostart': False})
        self.assertEqual(r.status_code, 500)
        self.assertIn('save', r.get_json()['error'])

    def test_page_renders(self):
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'stationTime', r.data)


if __name__ == '__main__':
    unittest.main()
