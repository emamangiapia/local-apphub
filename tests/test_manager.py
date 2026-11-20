import tempfile
import unittest
from pathlib import Path

from apphub.config import save_json
from apphub.gitops import OperationError
from apphub.manager import AppHubManager


APP = {"id": "demo", "title": "Demo", "repository": "https://github.com/example/demo",
       "branch": "main", "composeFile": "compose.yaml", "autoDeploy": False}


class FakeGitOps:
    def __init__(self, root):
        self.root = root
        self.sha = "a" * 40
        self.deployments = []
        self.stops = 0
        self.starts = 0
        self.fail_sha = None
        self.published = None

    def revision(self, repository, branch):
        return self.root / "fake-cache", self.sha

    def snapshot(self, slug, cache, revision):
        return self.root / "snapshots" / slug / revision

    def deploy(self, app, checkout):
        if checkout.name == self.fail_sha:
            raise OperationError("Simulazione errore deploy")
        self.deployments.append(checkout.name)

    def stop(self, app, checkout):
        self.stops += 1

    def start(self, app, checkout):
        self.starts += 1

    def publish_manifest(self, cache, revision, branch, manifest_path, manifest):
        self.published = {"branch": branch, "file": manifest_path, "content": manifest}


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.driver = FakeGitOps(self.root)
        save_json(self.root / "apps.json", {"apps": [APP]})
        self.manager = AppHubManager(self.root, self.driver)

    def tearDown(self):
        self.tmp.cleanup()

    def test_manual_app_never_auto_deploys(self):
        self.manager.sync_once()
        self.assertEqual(self.driver.deployments, [])
        self.assertEqual(self.manager.snapshot()["apps"][0]["status"], "not-installed")
        self.manager.action("demo", "deploy")
        self.assertEqual(len(self.driver.deployments), 1)
        self.assertEqual(self.manager.snapshot()["apps"][0]["status"], "running")

    def test_automatically_installs_and_updates(self):
        save_json(self.root / "apps.json", {"apps": [{**APP, "autoDeploy": True}]})
        self.manager.sync_once()
        self.assertEqual(self.driver.deployments, ["a" * 40])
        self.manager.sync_once()
        self.assertEqual(len(self.driver.deployments), 1)
        self.driver.sha = "b" * 40
        self.manager.sync_once()
        self.assertEqual(self.driver.deployments, ["a" * 40, "b" * 40])

    def test_stop_prevents_auto_restart(self):
        save_json(self.root / "apps.json", {"apps": [{**APP, "autoDeploy": True}]})
        self.manager.sync_once()
        self.manager.action("demo", "stop")
        self.assertEqual(self.driver.stops, 1)
        self.driver.sha = "c" * 40
        self.manager.sync_once()
        self.assertEqual(len(self.driver.deployments), 1)
        self.assertEqual(self.manager.snapshot()["apps"][0]["status"], "stopped")
        self.manager.action("demo", "start")
        self.assertEqual(self.driver.starts, 1)

    def test_rolls_back_failed_revision(self):
        save_json(self.root / "apps.json", {"apps": [{**APP, "autoDeploy": True}]})
        self.manager.sync_once()
        self.driver.sha = "b" * 40
        self.driver.fail_sha = "b" * 40
        self.manager.sync_once()
        app = self.manager.snapshot()["apps"][0]
        self.assertEqual(app["status"], "running")
        self.assertEqual(app["deployedSha"], "a" * 40)
        self.assertIn("ripristinata", app["error"])

    def test_removing_app_does_not_delete_state(self):
        self.manager.sync_once()
        self.manager.action("demo", "deploy")
        save_json(self.root / "apps.json", {"apps": []})
        self.manager.sync_once()
        self.assertEqual(self.manager.snapshot()["apps"], [])
        self.assertIn("demo", self.manager.state["deployments"])

    def test_gui_catalog_add_update_remove(self):
        self.manager.sync_once()
        added = {"id": "note", "title": "Note", "category": "Personale",
                 "repository": "https://github.com/example/notes", "composeFile": "compose.yml",
                 "autoDeploy": False}
        apps = self.manager.edit_catalog("add", added)
        self.assertEqual(len(apps), 2)
        self.assertEqual(self.driver.deployments, [])
        updated = {**added, "title": "Le mie note"}
        apps = self.manager.edit_catalog("update", updated, "note")
        self.assertEqual(apps[1]["title"], "Le mie note")
        self.assertEqual(AppHubManager(self.root, self.driver)._manifest()[1]["title"], "Le mie note")
        apps = self.manager.edit_catalog("remove", slug="note")
        self.assertEqual(len(apps), 1)

    def test_cannot_change_existing_app_id(self):
        self.manager.sync_once()
        with self.assertRaisesRegex(Exception, "ID"):
            self.manager.edit_catalog("update", {**APP, "id": "another"}, "demo")

    def test_gui_settings_persist(self):
        value = self.manager.update_settings({"syncIntervalSeconds": 120})
        self.assertEqual(value["syncIntervalSeconds"], 120)
        self.manager.sync_once()
        self.assertEqual(self.manager.snapshot()["syncIntervalSeconds"], 120)

    def test_gui_changes_are_published_to_private_catalogue(self):
        self.manager.update_settings({"configRepository": "https://github.com/example/private-config"})
        remote = self.root / "snapshots" / "_configuration" / self.driver.sha
        save_json(remote / "apps.json", {"apps": []})
        apps = self.manager.edit_catalog("add", {
            "id": "calendar", "title": "Calendario",
            "repository": "https://github.com/example/calendar", "autoDeploy": False})
        self.assertEqual(apps[0]["id"], "calendar")
        self.assertEqual(self.driver.published["branch"], "main")
        self.assertEqual(self.driver.published["content"]["apps"][0]["id"], "calendar")
        self.assertEqual(len(self.manager._manifest()), 0)  # Fake remote has not advanced.


if __name__ == "__main__":
    unittest.main()
