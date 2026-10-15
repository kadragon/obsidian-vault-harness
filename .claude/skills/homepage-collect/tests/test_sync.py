"""Offline pipeline locking regressions; no network or vault notes are touched."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import collect

spec = importlib.util.spec_from_file_location('homepage_sync', SCRIPTS / 'sync.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class SyncTests(unittest.TestCase):
    def test_pipeline_holds_lock_through_every_stage_and_rejects_competitors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = ['sync.py', '--output', directory, '--vault', directory]
            stages = []

            def stage(command=None, **kwargs):
                self.assertTrue((root / '.collection.lock').exists())
                # Both entry points must reject the same output before doing any work.
                with patch.object(sys, 'argv', args):
                    with self.assertRaisesRegex(collect.CollectionError, 'lock exists'):
                        sync.main()
                with patch.object(sys, 'argv', ['collect.py', '--output', directory]):
                    with self.assertRaisesRegex(collect.CollectionError, 'lock exists'):
                        collect.main()
                stages.append(command)

            # refresh must read the previous dataset only after acquiring the lock.
            with patch.object(collect, 'refresh', side_effect=stage), \
                 patch.object(sync.subprocess, 'run', side_effect=stage), \
                 patch.object(sys, 'argv', args):
                sync.main()
            self.assertEqual(len(stages), 3)
            self.assertIn('render_notes.py', stages[1][1])
            self.assertIn('verify_notes.py', stages[2][1])
            self.assertFalse((root / '.collection.lock').exists())

    def test_separate_cli_process_cannot_enter_locked_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with collect.output_lock(root):
                for entry in ('sync.py', 'collect.py'):
                    result = subprocess.run(
                        [sys.executable, str(SCRIPTS / entry), '--output', directory],
                        capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertIn('lock exists', result.stderr)
                    self.assertTrue((root / '.collection.lock').exists())
                self.assertEqual(list(root.iterdir()), [root / '.collection.lock'])
            self.assertFalse((root / '.collection.lock').exists())

    def test_failure_at_each_stage_releases_lock_and_stops_pipeline(self):
        for failure_stage in range(3):
            with self.subTest(stage=failure_stage), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                stages = []

                def stage(*args, **kwargs):
                    stages.append(1)
                    if len(stages) == failure_stage + 1:
                        raise subprocess.CalledProcessError(7, 'fixture')

                with patch.object(collect, 'refresh', side_effect=stage), \
                     patch.object(sync.subprocess, 'run', side_effect=stage), \
                     patch.object(sys, 'argv', ['sync.py', '--output', directory]):
                    with self.assertRaises(subprocess.CalledProcessError):
                        sync.main()
                self.assertEqual(len(stages), failure_stage + 1)
                self.assertFalse((root / '.collection.lock').exists())


if __name__ == '__main__':
    unittest.main()
