from __future__ import annotations

import argparse
import getpass
import sys
import warnings

import urllib3

from .client import FritzBoxClient, TIMEOUT
from .models import ResetResult
from .tui import run_tui

DEFAULT_USER = "BENUTZERNAME_EINTRAGEN"


def _prompt(args: argparse.Namespace) -> tuple[str, str, str]:
    base_url = args.url or input("FRITZ!Box URL [https://fritz.box]: ").strip() or "https://fritz.box"
    username = args.user if args.user is not None else input(f"Benutzername [{DEFAULT_USER}]: ").strip() or DEFAULT_USER
    password = getpass.getpass("FRITZ!Box Passwort: ")
    return base_url, username, password


def _print_progress(index: int, total: int, row: dict[str, object]) -> None:
    name = row.get("name") or row.get("UID") or "?"
    print(f"Lade Details {index}/{total}: {name}", flush=True)


def _print_results(results: list[ResetResult]) -> None:
    ok = [r for r in results if r.ok]
    failed = [r for r in results if not r.ok]
    if ok:
        print(f"\nErfolgreich entfernt/zurueckgesetzt: {len(ok)}")
        for result in ok:
            print(f"  OK  {result.name} ({result.uid})")
    if failed:
        print(f"\nFehlgeschlagen: {len(failed)}", file=sys.stderr)
        for result in failed:
            print(f"  ERR {result.name} ({result.uid}): {result.message}", file=sys.stderr)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FRITZ!Box passive devices TUI")
    parser.add_argument("--url", help="FRITZ!Box URL, default: https://fritz.box")
    parser.add_argument("--user", help=f"FRITZ!Box user, default: {DEFAULT_USER}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    warnings.filterwarnings("ignore", message="Unverified HTTPS request")
    args = parse_args(argv)
    base_url, username, password = _prompt(args)
    client = FritzBoxClient(base_url=base_url, timeout=TIMEOUT)

    try:
        print("Login ...")
        client.login(username, password)
        print("Lade passive Geraete und Details. Das kann dauern ...")
        devices = client.load_passive_devices(progress=_print_progress)
    except Exception as exc:
        print(f"Fehler beim Laden: {exc}", file=sys.stderr)
        return 1

    marked_uids = run_tui(devices)
    if not marked_uids:
        print("Keine Geraete entfernt.")
        return 0

    selected = [device for device in devices if device.uid in marked_uids]
    print(f"Entferne {len(selected)} Geraete ...")
    results = [client.reset_device(device) for device in selected]
    _print_results(results)
    return 0 if all(result.ok for result in results) else 1
