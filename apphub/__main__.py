"""CLI for installation, private config registration, and daemon startup."""

from __future__ import annotations

import argparse
import getpass
import json
import sys

from .auth import initialize_auth
from .config import (ConfigError, data_directory, ensure_data_directory,
                     read_json, save_json, validate_settings)
from .manager import AppHubManager
from .server import serve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="local-apphub", description="Local AppHub by iPhone Facile")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Imposta la password e inizializza i file privati")
    sub.add_parser("sync", help="Aggiorna il catalogo ed esegue i deploy abilitati")
    sub.add_parser("status", help="Mostra lo stato del catalogo")
    config = sub.add_parser("set-config", help="Collega una repository privata di configurazione")
    config.add_argument("--repo", required=True, help="https://github.com/utente/repo-privata")
    config.add_argument("--branch", default="main")
    config.add_argument("--file", default="apps.json")
    local = sub.add_parser("use-local-config", help="Torna al file apps.json privato sul PC")
    server = sub.add_parser("serve", help="Avvia la dashboard e il watcher")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8766)
    server.add_argument("--allow-network", action="store_true", help="Consenti il bind non locale, a tuo rischio")
    server.add_argument("--allowed-host", action="append", default=[], help="Hostname affidabile per reverse proxy")
    args = parser.parse_args(argv)
    root = data_directory()
    ensure_data_directory(root)

    try:
        if args.command == "init":
            password = getpass.getpass("Crea password dashboard (minimo 12 caratteri): ")
            if password != getpass.getpass("Ripeti password: "):
                raise ValueError("Le password non coincidono")
            initialize_auth(root, password)
            if not (root / "settings.json").exists():
                save_json(root / "settings.json", validate_settings({}))
            if not (root / "apps.json").exists():
                save_json(root / "apps.json", {"apps": []})
            print(f"Configurazione privata creata in: {root}")
            return 0

        if args.command in ("set-config", "use-local-config"):
            settings = read_json(root / "settings.json", {})
            if args.command == "set-config":
                settings.update({"configRepository": args.repo, "configBranch": args.branch,
                                 "configFile": args.file})
            else:
                settings["configRepository"] = None
            save_json(root / "settings.json", validate_settings(settings))
            print("Configurazione salvata. Il servizio la rileggerà al prossimo controllo.")
            return 0

        manager = AppHubManager(root)
        if args.command == "sync":
            manager.sync_once()
            result = manager.snapshot()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1 if result["lastSyncError"] else 0
        if args.command == "status":
            print(json.dumps(manager.snapshot(), ensure_ascii=False, indent=2))
            return 0
        if args.command == "serve":
            if args.port < 1 or args.port > 65535:
                raise ValueError("Porta fuori intervallo")
            if args.host not in ("127.0.0.1", "localhost", "::1") and not args.allow_network:
                raise ValueError("Per esporre il servizio in rete serve --allow-network")
            serve(manager, host=args.host, port=args.port, allowed_hosts=set(args.allowed_host))
            return 0
    except (ConfigError, RuntimeError, ValueError, OSError) as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
