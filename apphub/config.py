"""Private-on-device configuration and strict validation of GitOps manifests."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit


SLUG = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
GITHUB_PATH = re.compile(r"^/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}(?:\.git)?$")
BRANCH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,119}$")
REMOTE_HOSTNAME = re.compile(
    r"^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}$",
    re.IGNORECASE,
)
MAX_APPS = 100


class ConfigError(ValueError):
    """A manifest cannot be used safely."""


def data_directory() -> Path:
    if override := os.environ.get("LOCAL_APPHUB_DATA_DIR"):
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return base / "LocalAppHub"
    return Path.home() / ".local-apphub"


def ensure_data_directory(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        root.chmod(0o700)


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def save_json(path: Path, value) -> None:
    ensure_data_directory(path.parent)
    descriptor, name = tempfile.mkstemp(prefix=".apphub-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        if os.name != "nt":
            os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def github_url(value: str) -> str:
    if not isinstance(value, str):
        raise ConfigError("Repository GitHub non valida")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or parsed.netloc != "github.com" or
            parsed.query or parsed.fragment or not GITHUB_PATH.fullmatch(parsed.path) or
            parsed.username or parsed.password):
        raise ConfigError("Usa un URL HTTPS GitHub senza token o parametri")
    return value


def branch_name(value: str) -> str:
    if (not isinstance(value, str) or not BRANCH.fullmatch(value) or
            ".." in value or "//" in value or "/." in value or
            value.endswith(("/", ".", ".lock"))):
        raise ConfigError("Nome branch non valido")
    return value


def relative_file(value: str, extension: str | tuple[str, ...]) -> str:
    if (not isinstance(value, str) or "\\" in value or "\x00" in value or
            not value.endswith(extension)):
        raise ConfigError("Percorso file non valido")
    posix = PurePosixPath(value)
    if (posix.is_absolute() or not posix.parts or
            any(part in (".", "..") or part.startswith(".") for part in value.split("/"))):
        raise ConfigError("Il file deve essere un percorso relativo sicuro")
    return value


def validate_settings(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ConfigError("Le impostazioni devono essere un oggetto JSON")
    repo = value.get("configRepository")
    interval = value.get("syncIntervalSeconds", 60)
    if type(interval) is not int or not 30 <= interval <= 3600:
        raise ConfigError("L'intervallo deve essere tra 30 e 3600 secondi")
    remote_hostname = value.get("remoteHostname", "")
    if not isinstance(remote_hostname, str):
        raise ConfigError("Hostname remoto non valido")
    remote_hostname = remote_hostname.strip().lower()
    if remote_hostname and not REMOTE_HOSTNAME.fullmatch(remote_hostname):
        raise ConfigError("Inserisci soltanto l'hostname HTTPS, senza protocollo, porta o percorso")
    return {
        "configRepository": github_url(repo) if repo else None,
        "configBranch": branch_name(value.get("configBranch", "main")),
        "configFile": relative_file(value.get("configFile", "apps.json"), ".json"),
        "syncIntervalSeconds": interval,
        "remoteHostname": remote_hostname,
    }


def validate_manifest(value) -> list[dict]:
    if not isinstance(value, dict) or not isinstance(value.get("apps"), list):
        raise ConfigError("Il manifesto deve contenere un elenco 'apps'")
    if len(value["apps"]) > MAX_APPS:
        raise ConfigError("Troppe applicazioni nel manifesto")
    names: set[str] = set()
    occupied: set[int] = set()
    # Collect explicit positions first so legacy apps cannot take a reserved slot.
    for item in value["apps"]:
        if not isinstance(item, dict):
            raise ConfigError("Ogni applicazione deve essere un oggetto")
        position = item.get("slot")
        if position is not None:
            if type(position) is not int or not 0 <= position < MAX_APPS or position in occupied:
                raise ConfigError("Slot applicazione non valido o già occupato")
            occupied.add(position)
    apps = []
    for item in value["apps"]:
        if not isinstance(item, dict):
            raise ConfigError("Ogni applicazione deve essere un oggetto")
        slug = item.get("id")
        if not isinstance(slug, str) or not SLUG.fullmatch(slug) or slug in names:
            raise ConfigError("ID applicazione non valido o duplicato")
        names.add(slug)
        title = item.get("title", slug)
        category = item.get("category", "Altro")
        launch_url = item.get("url", "")
        for label, text in (("title", title), ("category", category)):
            if not isinstance(text, str) or not 1 <= len(text.strip()) <= 80:
                raise ConfigError(f"Campo '{label}' non valido")
        if not isinstance(launch_url, str) or len(launch_url) > 300:
            raise ConfigError("URL di apertura non valido")
        if launch_url:
            parsed = urlsplit(launch_url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password:
                raise ConfigError("URL di apertura deve essere HTTP(S) senza credenziali")
        auto_deploy = item.get("autoDeploy", False)
        if type(auto_deploy) is not bool:
            raise ConfigError("autoDeploy deve essere true oppure false")
        position = item.get("slot")
        if position is None:
            position = next(index for index in range(MAX_APPS) if index not in occupied)
            occupied.add(position)
        apps.append({
            "id": slug,
            "slot": position,
            "title": title.strip(),
            "category": category.strip(),
            "repository": github_url(item.get("repository")),
            "branch": branch_name(item.get("branch", "main")),
            "composeFile": relative_file(item.get("composeFile", "compose.yaml"), (".yaml", ".yml")),
            "url": launch_url,
            "autoDeploy": auto_deploy,
        })
    return sorted(apps, key=lambda app: app["slot"])
