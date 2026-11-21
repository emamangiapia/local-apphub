import shutil
import subprocess
import unittest
from pathlib import Path


class ServiceWorkerTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js non installato")
    def test_private_requests_never_cached(self):
        script = Path(__file__).with_name("test_service_worker.js")
        result = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PWA privacy tests: OK", result.stdout)
