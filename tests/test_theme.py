import shutil
import subprocess
import unittest
from pathlib import Path


class ThemeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js non installato")
    def test_theme_selection_and_browser_storage(self):
        test_path = Path(__file__).resolve().with_name("test_theme_init.js")
        result = subprocess.run(["node", str(test_path)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Theme preference tests: OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
