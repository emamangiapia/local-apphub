"""Desired-state reconciliation for a user's private application catalogue."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from .config import (ConfigError, read_json, relative_file, save_json,
                     validate_manifest, validate_settings)
from .gitops import GitOps, OperationError


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AppHubManager:
    def __init__(self, root: Path, driver: GitOps | None = None):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.git = driver if driver is not None else GitOps(root)
        self.settings = validate_settings(read_json(root / "settings.json", {}))
        initial = read_json(root / "state.json", {"deployments": {}})
        self.state = initial if isinstance(initial, dict) else {"deployments": {}}
        self.state.setdefault("deployments", {})
        self.apps: list[dict] = []
        self.work_lock = threading.Lock()
        self.state_lock = threading.RLock()
        self.last_sync_error: str | None = None
        self.syncing = False

    def _save_state(self) -> None:
        with self.state_lock:
            save_json(self.root / "state.json", self.state)

    def _manifest(self) -> list[dict]:
        if repo := self.settings["configRepository"]:
            try:
                cache, revision = self.git.revision(repo, self.settings["configBranch"])
                snapshot = self.git.snapshot("_configuration", cache, revision)
                relative = relative_file(self.settings["configFile"], ".json")
                candidate = (snapshot / relative).resolve()
                if not candidate.is_relative_to(snapshot.resolve()):
                    raise ConfigError("Manifesto fuori dal repository")
                raw = read_json(candidate)
                apps = validate_manifest(raw)
                save_json(self.root / "last_good_apps.json", {
                    "source": [repo, self.settings["configBranch"], self.settings["configFile"]],
                    "manifest": raw,
                })
                return apps
            except (OperationError, ConfigError, OSError, ValueError, json.JSONDecodeError):
                # Keep working with the last valid manifest if GitHub is offline.
                cached = read_json(self.root / "last_good_apps.json")
                if not isinstance(cached, dict) or cached.get("source") != [
                    repo, self.settings["configBranch"], self.settings["configFile"]
                ]:
                    raise OperationError("Impossibile leggere la configurazione remota") from None
                self.last_sync_error = "Configurazione remota non raggiungibile: uso l'ultima copia valida"
                return validate_manifest(cached["manifest"])
        return validate_manifest(read_json(self.root / "apps.json", {"apps": []}))

    def catalog(self) -> dict:
        with self.state_lock:
            return {"settings": self.settings.copy(), "apps": [app.copy() for app in self.apps]}

    def update_settings(self, updates: dict) -> dict:
        if not isinstance(updates, dict):
            raise ConfigError("Impostazioni non valide")
        allowed = {"configRepository", "configBranch", "configFile", "syncIntervalSeconds"}
        if any(key not in allowed for key in updates):
            raise ConfigError("Campo impostazioni sconosciuto")
        with self.work_lock:
            old = validate_settings(read_json(self.root / "settings.json", {}))
            new = validate_settings({**old, **updates})
            save_json(self.root / "settings.json", new)
            with self.state_lock:
                self.settings = new
            return new

    def edit_catalog(self, operation: str, item: dict | None = None,
                     slug: str | None = None) -> list[dict]:
        """Change the local catalogue or commit the change to the private Git repo.

        Keeps unrelated custom manifest fields; remote changes are fetched first
        and pushed using Git's normal non-force fast-forward protection.
        """
        if operation not in ("add", "update", "remove"):
            raise ConfigError("Operazione catalogo non valida")
        with self.work_lock:
            repo = self.settings["configRepository"]
            if repo:
                cache, revision = self.git.revision(repo, self.settings["configBranch"])
                checkout = self.git.snapshot("_configuration", cache, revision)
                path = (checkout / self.settings["configFile"]).resolve()
                if not path.is_relative_to(checkout.resolve()):
                    raise ConfigError("File catalogo fuori dal repository")
                raw = read_json(path, {"apps": []})
            else:
                raw = read_json(self.root / "apps.json", {"apps": []})
            validate_manifest(raw)
            current = list(raw["apps"])
            ids = {entry["id"] for entry in current}
            if operation == "add":
                if not isinstance(item, dict):
                    raise ConfigError("Dati app non validi")
                if item.get("id") in ids:
                    raise ConfigError("Esiste già un'app con questo ID")
                current.append(item)
            elif operation == "update":
                if slug not in ids or not isinstance(item, dict) or item.get("id") != slug:
                    raise ConfigError("L'ID di un'app esistente non può essere modificato")
                current = [{**entry, **item} if entry["id"] == slug else entry for entry in current]
            else:
                if slug not in ids:
                    raise ConfigError("App non trovata")
                current = [entry for entry in current if entry["id"] != slug]
            updated = {**raw, "apps": current}
            normalized = validate_manifest(updated)
            if repo:
                self.git.publish_manifest(cache, revision, self.settings["configBranch"],
                                          self.settings["configFile"], updated)
                save_json(self.root / "last_good_apps.json", {
                    "source": [repo, self.settings["configBranch"], self.settings["configFile"]],
                    "manifest": updated,
                })
            else:
                save_json(self.root / "apps.json", updated)
            with self.state_lock:
                self.apps = normalized
            return normalized

    def _record(self, slug: str, **changes) -> dict:
        with self.state_lock:
            record = self.state["deployments"].setdefault(slug, {})
            record.update(changes)
            self._save_state()
            return record.copy()

    def _app(self, slug: str) -> dict:
        with self.state_lock:
            app = next((app for app in self.apps if app["id"] == slug), None)
        if app is None:
            raise ConfigError("App non presente nel catalogo")
        return app

    def _deploy(self, app: dict, cache: Path | None = None,
                revision: str | None = None) -> None:
        slug = app["id"]
        with self.state_lock:
            previous = self.state["deployments"].get(slug, {}).get("sha")
        self._record(slug, status="deploying", error=None)
        try:
            if cache is None or revision is None:
                cache, revision = self.git.revision(app["repository"], app["branch"])
            checkout = self.git.snapshot(slug, cache, revision)
            self.git.deploy(app, checkout)
            self._record(slug, sha=revision, status="running", manuallyStopped=False,
                         lastDeployedAt=now_iso(), error=None)
        except (OperationError, OSError) as exc:
            if previous and previous != revision:
                try:
                    old_checkout = self.root / "snapshots" / slug / previous
                    self.git.deploy(app, old_checkout)
                    self._record(slug, status="running", error="Aggiornamento fallito: versione precedente ripristinata")
                    return
                except (OperationError, OSError):
                    pass
            self._record(slug, status="error", error=str(exc))

    def sync_once(self) -> None:
        with self.work_lock:
            with self.state_lock:
                self.syncing = True
                self.last_sync_error = None
            try:
                updated_settings = validate_settings(read_json(self.root / "settings.json", {}))
                with self.state_lock:
                    self.settings = updated_settings
                desired = self._manifest()
                with self.state_lock:
                    self.apps = desired
                for app in desired:
                    slug = app["id"]
                    try:
                        with self.state_lock:
                            record = self.state["deployments"].get(slug, {}).copy()
                        # A newly registered manual app must not be cloned just
                        # to show it in the catalogue. This also avoids Git
                        # credential prompts until the user asks for a deploy.
                        if not app["autoDeploy"] and not record.get("sha"):
                            self._record(slug, status="not-installed", error=None)
                            continue
                        cache, revision = self.git.revision(app["repository"], app["branch"])
                        self._record(slug, availableSha=revision)
                        if (app["autoDeploy"] and not record.get("manuallyStopped") and
                                record.get("sha") != revision):
                            self._deploy(app, cache, revision)
                        elif not record.get("sha"):
                            self._record(slug, status="not-installed", error=None)
                    except (OperationError, OSError) as exc:
                        self._record(slug, error=str(exc))
                with self.state_lock:
                    self.state["lastSyncAt"] = now_iso()
                    self._save_state()
            except (ConfigError, OperationError, ValueError, OSError, json.JSONDecodeError) as exc:
                with self.state_lock:
                    self.last_sync_error = str(exc)
            finally:
                with self.state_lock:
                    self.syncing = False

    def action(self, slug: str, action: str) -> None:
        with self.work_lock:
            try:
                app = self._app(slug)
                if action == "deploy":
                    self._deploy(app)
                elif action in ("stop", "start"):
                    with self.state_lock:
                        sha = self.state["deployments"].get(slug, {}).get("sha")
                    if not sha and action == "start":
                        self._deploy(app)
                        return
                    if not sha:
                        raise OperationError("App non ancora installata")
                    checkout = self.root / "snapshots" / slug / sha
                    if action == "stop":
                        self.git.stop(app, checkout)
                        self._record(slug, status="stopped", manuallyStopped=True, error=None)
                    else:
                        self.git.start(app, checkout)
                        self._record(slug, status="running", manuallyStopped=False, error=None)
                else:
                    raise ConfigError("Azione non valida")
            except (OperationError, ConfigError, OSError) as exc:
                self._record(slug, status="error", error=str(exc))

    def snapshot(self) -> dict:
        with self.state_lock:
            records = self.state["deployments"]
            apps = []
            for app in self.apps:
                record = records.get(app["id"], {})
                apps.append({**app,
                             "status": record.get("status", "not-installed"),
                             "error": record.get("error"),
                             "deployedSha": record.get("sha"),
                             "availableSha": record.get("availableSha"),
                             "manuallyStopped": record.get("manuallyStopped", False),
                             "lastDeployedAt": record.get("lastDeployedAt")})
            return {
                "apps": apps,
                "syncing": self.syncing,
                "lastSyncAt": self.state.get("lastSyncAt"),
                "lastSyncError": self.last_sync_error,
                "syncIntervalSeconds": self.settings["syncIntervalSeconds"],
                "remoteConfig": bool(self.settings["configRepository"]),
            }
