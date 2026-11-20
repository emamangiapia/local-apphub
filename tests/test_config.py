import json
import tempfile
import unittest
from pathlib import Path

from apphub.config import (ConfigError, github_url, read_json, save_json,
                           validate_manifest, validate_settings)


def example(**changes):
    return {"id": "first-app", "title": "App", "repository": "https://github.com/example/demo",
            "branch": "main", "composeFile": "compose.yaml", "autoDeploy": False, **changes}


class ConfigTests(unittest.TestCase):
    def test_empty_catalogue(self):
        self.assertEqual(validate_manifest({"apps": []}), [])

    def test_auto_deploy_defaults_to_false(self):
        item = example()
        item.pop("autoDeploy")
        self.assertFalse(validate_manifest({"apps": [item]})[0]["autoDeploy"])

    def test_rejects_unsafe_git_urls(self):
        for url in ["http://github.com/x/y", "https://github.com/x/y?token=abc",
                    "https://user:pass@github.com/x/y", "https://evil.test/x/y",
                    "https://github.com:999/x/y", "https://github.com/x/y/../z",
                    "file:///etc/passwd", "https://github.com/x/y#secret"]:
            with self.subTest(url=url), self.assertRaises(ConfigError):
                github_url(url)

    def test_rejects_traversal_and_bad_names(self):
        cases = [
            {"id": "../escape"}, {"id": "X"}, {"branch": "--upload-pack=evil"},
            {"branch": "foo/../bar"}, {"composeFile": "../../secret.yaml"},
            {"composeFile": "/etc/secret.yaml"}, {"composeFile": "dir\\compose.yaml"},
            {"autoDeploy": "true"}, {"url": "javascript:alert(1)"},
        ]
        for changes in cases:
            item = example()
            item.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ConfigError):
                validate_manifest({"apps": [item]})

    def test_duplicate_ids(self):
        with self.assertRaises(ConfigError):
            validate_manifest({"apps": [example(), example()]})

    def test_settings(self):
        self.assertEqual(validate_settings({})["syncIntervalSeconds"], 60)
        with self.assertRaises(ConfigError):
            validate_settings({"syncIntervalSeconds": 1})

    def test_atomic_json_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "local" / "prefs.json"
            save_json(path, {"title": "Caffè"})
            self.assertEqual(read_json(path)["title"], "Caffè")


if __name__ == "__main__":
    unittest.main()
