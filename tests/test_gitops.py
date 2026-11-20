import shutil
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from apphub.gitops import GitOps, OperationError


@unittest.skipUnless(shutil.which("git"), "Git non disponibile")
class GitOpsTests(unittest.TestCase):
    def test_real_git_fetch_and_immutable_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            upstream = root / "upstream"
            upstream.mkdir()

            def git(*args):
                return subprocess.run(["git", "-C", str(upstream), *args],
                                      check=True, capture_output=True, text=True).stdout.strip()

            subprocess.run(["git", "init", str(upstream)], check=True, capture_output=True)
            git("config", "user.email", "test@example.invalid")
            git("config", "user.name", "Test")
            git("checkout", "-b", "main")
            (upstream / "compose.yaml").write_text("services: {}\n", encoding="utf-8")
            git("add", ".")
            git("commit", "-m", "first")
            driver = GitOps(root / "hub")
            cache, first = driver.revision(str(upstream), "main")
            snapshot = driver.snapshot("demo", cache, first)
            self.assertTrue((snapshot / "compose.yaml").exists())
            self.assertEqual(driver.snapshot("demo", cache, first), snapshot)

            (upstream / "compose.yaml").write_text("services:\n  web:\n    image: nginx\n", encoding="utf-8")
            git("add", ".")
            git("commit", "-m", "second")
            cache, second = driver.revision(str(upstream), "main")
            self.assertNotEqual(first, second)
            next_snapshot = driver.snapshot("demo", cache, second)
            self.assertNotEqual(snapshot, next_snapshot)
            self.assertEqual((snapshot / "compose.yaml").read_text(), "services: {}\n")

    def test_compose_symlink_cannot_escape_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkout = root / "snapshot"
            checkout.mkdir()
            external = root / "outside.yaml"
            external.write_text("services: {}\n", encoding="utf-8")
            try:
                (checkout / "compose.yaml").symlink_to(external)
            except OSError:
                self.skipTest("Creazione link simbolici non disponibile")
            driver = GitOps(root / "hub")
            with self.assertRaises(OperationError):
                driver.deploy({"id": "demo", "composeFile": "compose.yaml"}, checkout)

    def test_publish_private_catalogue_without_force_push(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bare = root / "remote.git"
            subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
            working = root / "editing"
            subprocess.run(["git", "clone", str(bare), str(working)], check=True, capture_output=True)

            def git(*args):
                return subprocess.run(["git", "-C", str(working), *args],
                                      check=True, capture_output=True, text=True).stdout.strip()

            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.invalid")
            git("checkout", "-b", "main")
            (working / "apps.json").write_text('{"apps": []}\n', encoding="utf-8")
            git("add", ".")
            git("commit", "-m", "initial")
            git("push", "-u", "origin", "main")
            driver = GitOps(root / "hub")
            cache, revision = driver.revision(str(bare), "main")
            driver.publish_manifest(cache, revision, "main", "apps.json", {"apps": [], "version": 2})
            git("pull", "--ff-only")
            self.assertEqual(json.loads((working / "apps.json").read_text())["version"], 2)
            # A concurrent remote commit must not be overwritten by an old edit.
            git("commit", "--allow-empty", "-m", "newer")
            git("push")
            with self.assertRaises(OperationError):
                driver.publish_manifest(cache, revision, "main", "apps.json", {"apps": [], "version": 3})


if __name__ == "__main__":
    unittest.main()
