"""Deployment regression checks; no external services or existing user state."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DeploymentTests(unittest.TestCase):
    def run_isolated(self, code, config=None, native=False):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) if native else Path(directory) / 'nested' / 'data'
            if config is not None:
                data.mkdir(parents=True, exist_ok=True)
                (data / 'config.json').write_text(config)
            env = dict(os.environ, PYTHONPATH=str(ROOT))
            env.pop('PLAYLIST_BRIDGE_DATA_DIR', None)
            env.pop('PLAYLIST_BRIDGE_PORT', None)
            if not native:
                env['PLAYLIST_BRIDGE_DATA_DIR'] = str(data)
            result = subprocess.run([sys.executable, '-c', code], cwd=directory,
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_empty_config_health_and_persistence(self):
        for config in (None, '', ' \n\t', '{}', '{"plex": {}}', '{"plex": null}', '{"server": {"port": 8173}}'):
            with self.subTest(config=config):
                self.run_isolated('''
from playlist_bridge.api import health
from playlist_bridge.legacy import Config, CONFIG_DIR, CONFIG_FILE
assert health()['status'] == 'ok'
assert (CONFIG_DIR / 'playlist-bridge.db').exists()
assert health()['plex_configured'] is False
assert health()['build'] == '20260908.6'
c = Config()
c.config['test_marker'] = 'saved'
c.save()
assert CONFIG_FILE.parent == CONFIG_DIR
assert Config().config['test_marker'] == 'saved'
''', config=config)

    def test_native_directory(self):
        self.run_isolated('''
from pathlib import Path
from playlist_bridge.legacy import CONFIG_DIR
assert CONFIG_DIR == Path.cwd()
''', native=True)

    def test_malformed_config_rejected(self):
        self.run_isolated('''
from playlist_bridge.legacy import Config
try:
    Config()
except RuntimeError:
    pass
else:
    raise AssertionError('Malformed config was silently accepted')
''', config='{broken')

    def test_port_configuration(self):
        self.run_isolated('''
import os
from unittest.mock import patch
from playlist_bridge.api import run
with patch('uvicorn.run') as serve:
    run()
    assert serve.call_args.kwargs['port'] == 8173
    os.environ['PLAYLIST_BRIDGE_PORT'] = '9123'
    run()
    assert serve.call_args.kwargs['port'] == 9123
    os.environ['PLAYLIST_BRIDGE_PORT'] = '65536'
    try:
        run()
    except ValueError:
        pass
    else:
        raise AssertionError('Invalid port accepted')
''')


if __name__ == '__main__':
    unittest.main()
