"""Versioned Git checkout and Docker Compose operations.

No shell commands, no automatic deletion, and no destructive Docker volume flags.
"""

from __future__ import annotations

import os
import subprocess
from hashlib import sha256
from pathlib import Path


class OperationError(RuntimeError):
    """A Git or Docker operation failed (details stay on the host)."""


def command(args: list[str], *, cwd: Path | None = None,
            env: dict[str, str] | None = None, timeout: int = 180) -> str:
    try:
        result = subprocess.run(
            args, cwd=cwd, env=env, check=False, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OperationError(f"Comando non disponibile o scaduto: {args[0]}") from exc
    if result.returncode:
        # Git/Compose output may include private URLs, tokens or environment values.
        # Do not return the subprocess output to the dashboard.
        raise OperationError(f"Operazione {args[0]} fallita (codice {result.returncode})")
    return result.stdout.strip()


class GitOps:
    def __init__(self, root: Path):
        self.root = root

    def _cache(self, repository: str) -> Path:
        # The filesystem path is derived from a hash, never from an untrusted URL.
        return self.root / "git-cache" / sha256(repository.encode("utf-8")).hexdigest()

    def revision(self, repository: str, branch: str) -> tuple[Path, str]:
        cache = self._cache(repository)
        cache.parent.mkdir(parents=True, exist_ok=True)
        if not (cache / ".git").is_dir():
            command(["git", "clone", "--filter=blob:none", "--no-checkout", "--", repository, str(cache)], timeout=300)
        # The branch has been validated; arguments are passed without a shell.
        ref = f"refs/remotes/origin/{branch}"
        command(["git", "-C", str(cache), "fetch", "--no-tags", "origin",
                 f"+refs/heads/{branch}:{ref}"], timeout=300)
        revision = command(["git", "-C", str(cache), "rev-parse", "--verify", f"{ref}^{{commit}}"]).strip()
        if len(revision) != 40 or any(ch not in "0123456789abcdef" for ch in revision):
            raise OperationError("Hash Git non valido")
        return cache, revision

    def snapshot(self, slug: str, cache: Path, revision: str) -> Path:
        checkout = self.root / "snapshots" / slug / revision
        if checkout.exists():
            existing = command(["git", "-C", str(checkout), "rev-parse", "HEAD"])
            if existing != revision:
                raise OperationError("Snapshot Git inatteso")
            return checkout
        checkout.parent.mkdir(parents=True, exist_ok=True)
        command(["git", "-C", str(cache), "worktree", "add", "--detach", str(checkout), revision], timeout=300)
        return checkout

    def _compose(self, app: dict, checkout: Path, action: list[str]) -> None:
        compose = (checkout / app["composeFile"]).resolve()
        if not compose.is_relative_to(checkout.resolve()) or not compose.is_file():
            raise OperationError("File Docker Compose assente o fuori dal repository")
        volume_root = self.root / "app-data" / app["id"]
        volume_root.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["APPHUB_DATA_DIR"] = str(volume_root.resolve())
        command(["docker", "compose", "-p", f"apphub-{app['id']}",
                 "-f", str(compose), *action], cwd=checkout, env=env, timeout=900)

    def deploy(self, app: dict, checkout: Path) -> None:
        # Validation is performed separately before build and release.
        self._compose(app, checkout, ["config", "-q"])
        self._compose(app, checkout, ["up", "-d", "--build", "--wait"])

    def stop(self, app: dict, checkout: Path) -> None:
        # STOP (not DOWN -v) preserves containers and volumes.
        self._compose(app, checkout, ["stop"])

    def start(self, app: dict, checkout: Path) -> None:
        self._compose(app, checkout, ["start"])
