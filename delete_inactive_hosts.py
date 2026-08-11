#!/usr/bin/env python3
"""Delete inactive FRITZ!Box hosts listed in inactive.csv."""

from __future__ import annotations

import argparse
import csv
import getpass
import hashlib
import json
import logging
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.markup import escape
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    Task,
    TextColumn,
)
from rich.prompt import Confirm
from rich.text import Text


# Standardwerte; sie koennen per Kommandozeile ueberschrieben werden.
DEFAULT_FRITZBOX_URL = "https://fritz.box"
DEFAULT_FRITZBOX_USERNAME = "BENUTZERNAME_EINTRAGEN"

CSV_FILE = Path("inactive.csv")
LOG_FILE = Path("delete_inactive_hosts.log")
VERIFY_TLS = False
TIMEOUT = 180

LOGIN_PATH = "/login_sid.lua?version=2"
DATA_PATH = "/data.lua"
INVALID_SID = "0000000000000000"
LOGGER = logging.getLogger("delete_inactive_hosts")


class FritzError(RuntimeError):
    pass


class CountdownRemainingColumn(ProgressColumn):
    """Recalibrate after each item and count down between updates."""

    def __init__(self) -> None:
        super().__init__()
        self._state: dict[int, tuple[float, float, float]] = {}

    def render(self, task: Task) -> Text:
        now = time.monotonic()
        estimated = task.time_remaining
        previous = self._state.get(task.id)

        if estimated is not None and (
            previous is None or previous[0] != task.completed
        ):
            previous = (task.completed, estimated, now)
            self._state[task.id] = previous

        if previous is None:
            return Text("-:--:--", style="progress.remaining")

        remaining = max(0, previous[1] - (now - previous[2]))
        seconds = int(remaining + 0.999)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        return Text(
            f"{hours}:{minutes:02d}:{seconds:02d}",
            style="progress.remaining",
        )


@dataclass(frozen=True)
class Target:
    line: int
    name: str
    mac: str

    @property
    def label(self) -> str:
        return self.name or self.mac


def setup_logging() -> Path:
    for handler in LOGGER.handlers:
        handler.close()
    LOGGER.handlers.clear()
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False

    handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    LOGGER.addHandler(handler)
    LOGGER.info("Programm gestartet")
    return LOG_FILE.resolve()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inaktive FRITZ!Box-Hosts aus einer CSV-Datei entfernen."
    )
    parser.add_argument(
        "-f",
        "--file",
        type=Path,
        default=CSV_FILE,
        metavar="FILE.csv",
        help=f"CSV-Datei (Standard: {CSV_FILE})",
    )
    parser.add_argument(
        "-u",
        "--user",
        default=DEFAULT_FRITZBOX_USERNAME,
        help="FRITZ!Box-Benutzername",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_FRITZBOX_URL,
        help=f"FRITZ!Box-URL (Standard: {DEFAULT_FRITZBOX_URL})",
    )
    return parser.parse_args()


def record_result(
    results: list[tuple[Target, str, str]],
    target: Target,
    state: str,
    detail: str,
) -> None:
    results.append((target, state, detail))
    level = {
        "geloescht": logging.INFO,
        "uebersprungen": logging.WARNING,
        "Fehler": logging.ERROR,
    }.get(state, logging.INFO)
    LOGGER.log(
        level,
        "%s | Name=%s | MAC=%s | CSV-Zeile=%d | %s",
        state,
        target.label,
        target.mac,
        target.line,
        detail,
    )


def make_opener() -> urllib.request.OpenerDirector:
    context = ssl.create_default_context()
    if not VERIFY_TLS:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=context),
        urllib.request.HTTPCookieProcessor(CookieJar()),
    )


def request(
    opener: urllib.request.OpenerDirector,
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> bytes:
    url = urllib.parse.urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))
    req = urllib.request.Request(
        url, data=data, headers=headers or {}, method=method
    )
    try:
        with opener.open(req, timeout=TIMEOUT) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        if len(detail) > 200:
            detail = f"{detail[:200]}..."
        suffix = f": {detail}" if detail else ""
        raise FritzError(f"HTTP {exc.code} bei {method} {url}{suffix}") from None
    except urllib.error.URLError as exc:
        raise FritzError(f"FRITZ!Box nicht erreichbar: {exc.reason}") from None
    except TimeoutError:
        raise FritzError(
            f"Zeitueberschreitung nach {TIMEOUT} Sekunden bei {method} {url}"
        ) from None


def parse_login_xml(data: bytes) -> ET.Element:
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise FritzError("Ungueltige Antwort von login_sid.lua") from exc


def calculate_response(challenge: str, password: str) -> str:
    if challenge.startswith("2$"):
        parts = challenge.split("$")
        if len(parts) != 5:
            raise FritzError("Unbekanntes PBKDF2-Challenge-Format")
        try:
            iter1 = int(parts[1])
            salt1 = bytes.fromhex(parts[2])
            iter2 = int(parts[3])
            salt2 = bytes.fromhex(parts[4])
        except ValueError as exc:
            raise FritzError("Ungueltige PBKDF2-Challenge") from exc
        hash1 = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt1, iter1
        )
        hash2 = hashlib.pbkdf2_hmac("sha256", hash1, salt2, iter2)
        return f"{parts[4]}${hash2.hex()}"

    value = f"{challenge}-{password}"
    compatible = "".join(char if ord(char) <= 255 else "." for char in value)
    digest = hashlib.md5(compatible.encode("utf-16le")).hexdigest()
    return f"{challenge}-{digest}"


def login(
    opener: urllib.request.OpenerDirector,
    base_url: str,
    username: str,
    password: str,
    status_update: Callable[[str], None],
) -> str:
    state = parse_login_xml(request(opener, base_url, LOGIN_PATH))
    challenge = state.findtext("Challenge", default="")
    try:
        block_time = int(state.findtext("BlockTime", default="0"))
    except ValueError:
        block_time = 0
    if not challenge:
        raise FritzError("Die FRITZ!Box hat keine Login-Challenge geliefert")
    if block_time > 0:
        status_update(
            f"[yellow]Login gesperrt, warte {block_time} Sekunden...[/yellow]"
        )
        time.sleep(block_time)

    post_data = urllib.parse.urlencode(
        {
            "username": username,
            "response": calculate_response(challenge, password),
        }
    ).encode("ascii")
    result = parse_login_xml(
        request(
            opener,
            base_url,
            LOGIN_PATH,
            method="POST",
            data=post_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    )
    sid = result.findtext("SID", default=INVALID_SID)
    if sid == INVALID_SID:
        raise FritzError("Anmeldung fehlgeschlagen: Benutzer oder Kennwort falsch")
    return sid


def logout(
    opener: urllib.request.OpenerDirector, base_url: str, sid: str
) -> None:
    data = urllib.parse.urlencode({"logout": "1", "sid": sid}).encode("ascii")
    try:
        request(
            opener,
            base_url,
            LOGIN_PATH,
            method="POST",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    except FritzError:
        pass


def normalize_mac(value: str) -> str:
    compact = value.replace(":", "").replace("-", "").replace(".", "").lower()
    if len(compact) != 12 or any(char not in "0123456789abcdef" for char in compact):
        raise ValueError(value)
    return compact


def read_targets(csv_file: Path) -> list[Target]:
    try:
        handle = csv_file.open("r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise FritzError(f"{csv_file} kann nicht gelesen werden: {exc}") from exc

    targets: list[Target] = []
    with handle:
        reader = csv.reader(handle, delimiter=";", quotechar='"')
        for line_number, row in enumerate(reader, start=1):
            if not row or all(not field.strip() for field in row):
                continue
            if len(row) == 1:
                continue
            if len(row) >= 3 and row[2].strip().casefold() == "host name":
                continue
            if len(row) < 5:
                raise FritzError(
                    f"CSV-Zeile {line_number} hat weniger als 5 Felder"
                )
            if row[1].strip().casefold() in {"yes", "ja", "1", "true", "active"}:
                raise FritzError(f"CSV-Zeile {line_number} ist als aktiv markiert")
            try:
                mac = normalize_mac(row[4].strip())
            except ValueError:
                raise FritzError(
                    f"CSV-Zeile {line_number} enthaelt keine gueltige MAC-Adresse"
                ) from None
            targets.append(Target(line_number, row[2].strip(), mac))

    if not targets:
        raise FritzError(f"{csv_file} enthaelt keine Hosts")
    return targets


def post_data(
    opener: urllib.request.OpenerDirector,
    base_url: str,
    sid: str,
    fields: dict[str, str],
) -> dict[str, object]:
    form = {"sid": sid, "lang": "de", **fields}
    raw = request(
        opener,
        base_url,
        DATA_PATH,
        method="POST",
        data=urllib.parse.urlencode(form).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FritzError("data.lua hat kein gueltiges JSON geliefert") from exc
    if not isinstance(payload, dict):
        raise FritzError("data.lua hat kein JSON-Objekt geliefert")
    return payload


def load_mac_map(
    opener: urllib.request.OpenerDirector, base_url: str, sid: str
) -> dict[str, list[str]]:
    payload = post_data(
        opener,
        base_url,
        sid,
        {
            "xhr": "1",
            "page": "netDev",
            "xhrId": "cleanup",
            "useajax": "1",
            "no_sidrenew": "",
        },
    )
    data = payload.get("data")
    devices = data.get("passive") if isinstance(data, dict) else None
    if not isinstance(devices, list):
        raise FritzError("data.lua-Antwort enthaelt keine passive Geraeteliste")

    mac_map: dict[str, list[str]] = {}
    for device in devices:
        if not isinstance(device, dict):
            continue
        uid = str(device.get("UID", "")).strip()
        try:
            mac = normalize_mac(str(device.get("mac", "")).strip())
        except ValueError:
            continue
        if uid:
            mac_map.setdefault(mac, []).append(uid)
    return mac_map


def delete_device(
    opener: urllib.request.OpenerDirector, base_url: str, sid: str, uid: str
) -> None:
    fields = {
        "xhr": "1",
        "page": "edit_device",
        "back_to_page": "netDev",
        "dev": uid,
        "btn_reset_dev": "",
    }
    payload = post_data(opener, base_url, sid, fields)
    data = payload.get("data")
    status = data.get("btn_reset_dev") if isinstance(data, dict) else None
    if status == "confirm":
        payload = post_data(
            opener,
            base_url,
            sid,
            {**fields, "confirmed": ""},
        )
        data = payload.get("data")
        status = data.get("btn_reset_dev") if isinstance(data, dict) else None
    if status not in (None, "ok"):
        raise FritzError(f"FRITZ!Box meldet btn_reset_dev={status!r}")


def main() -> int:
    args = parse_args()
    csv_file: Path = args.file
    base_url = args.url.rstrip("/")
    username = args.user
    console = Console()
    try:
        log_path = setup_logging()
    except OSError as exc:
        console.print(f"[red]Fehler:[/red] Logdatei kann nicht geoeffnet werden: {escape(str(exc))}")
        return 1

    console.print(f"Logdatei: [bold]{escape(str(log_path))}[/bold]")
    if username == "BENUTZERNAME_EINTRAGEN":
        LOGGER.error("FRITZ!Box-Benutzername ist nicht konfiguriert")
        console.print(
            "[red]Fehler:[/red] Benutzername im Skript oder mit --user angeben."
        )
        return 1

    try:
        with console.status(f"[cyan]Lese {escape(str(csv_file))}...[/cyan]"):
            targets = read_targets(csv_file)
    except FritzError as exc:
        LOGGER.error("CSV konnte nicht gelesen werden: %s", exc)
        console.print(f"[red]Fehler:[/red] {escape(str(exc))}")
        return 1

    LOGGER.info("%d Hosts aus %s geladen", len(targets), csv_file)
    console.print(f"[bold]{len(targets)}[/bold] Hosts aus {csv_file} geladen.")
    if not Confirm.ask("Diese Hosteintraege loeschen?", default=False):
        LOGGER.info("Vom Benutzer vor dem Loeschlauf abgebrochen")
        console.print("Abgebrochen.")
        return 0

    password = getpass.getpass("FRITZ!Box-Kennwort: ")
    opener = make_opener()
    sid: str | None = None
    try:
        with console.status("[cyan]Melde an der FRITZ!Box an...[/cyan]") as status:
            sid = login(opener, base_url, username, password, status.update)
        LOGGER.info("Anmeldung an %s erfolgreich", base_url)
        password = ""
        with console.status("[cyan]Ermittle interne Geraete-IDs...[/cyan]"):
            mac_map = load_mac_map(opener, base_url, sid)
        LOGGER.info("%d MAC-Adressen auf interne Geraete-IDs abgebildet", len(mac_map))
    except FritzError as exc:
        LOGGER.error("Vorbereitung fehlgeschlagen: %s", exc)
        console.print(f"[red]Fehler:[/red] {escape(str(exc))}")
        if sid:
            logout(opener, base_url, sid)
        return 1
    finally:
        password = ""

    results: list[tuple[Target, str, str]] = []
    processed_macs: set[str] = set()
    progress = Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        CountdownRemainingColumn(),
        speed_estimate_period=3600,
        console=console,
    )

    try:
        with progress:
            task = progress.add_task("Vorbereitung", total=len(targets))
            for target in targets:
                progress.update(task, description=f"[cyan]{escape(target.label)}[/cyan]")
                LOGGER.info(
                    "Bearbeitung gestartet | Name=%s | MAC=%s | CSV-Zeile=%d",
                    target.label,
                    target.mac,
                    target.line,
                )
                uids = mac_map.get(target.mac, [])
                if target.mac in processed_macs:
                    record_result(
                        results, target, "uebersprungen", "doppelte MAC in CSV"
                    )
                elif not uids:
                    record_result(
                        results, target, "uebersprungen", "MAC nicht gefunden"
                    )
                elif len(uids) > 1:
                    record_result(
                        results,
                        target,
                        "uebersprungen",
                        f"MAC hat {len(uids)} Treffer",
                    )
                else:
                    try:
                        delete_device(opener, base_url, sid, uids[0])
                    except FritzError as exc:
                        record_result(results, target, "Fehler", str(exc))
                    else:
                        processed_macs.add(target.mac)
                        record_result(results, target, "geloescht", uids[0])
                progress.advance(task)
    finally:
        LOGGER.info("FRITZ!Box-Sitzung wird beendet")
        with console.status("[cyan]Beende FRITZ!Box-Sitzung...[/cyan]"):
            logout(opener, base_url, sid)
        LOGGER.info("FRITZ!Box-Sitzung beendet")

    deleted = sum(state == "geloescht" for _, state, _ in results)
    skipped = sum(state == "uebersprungen" for _, state, _ in results)
    failed = sum(state == "Fehler" for _, state, _ in results)
    LOGGER.info(
        "Loeschlauf beendet | geloescht=%d | uebersprungen=%d | Fehler=%d",
        deleted,
        skipped,
        failed,
    )
    console.print(
        f"[green]{deleted} geloescht[/green], "
        f"[yellow]{skipped} uebersprungen[/yellow], "
        f"[red]{failed} Fehler[/red]"
    )
    for target, state, detail in results:
        if state != "geloescht":
            color = "red" if state == "Fehler" else "yellow"
            console.print(
                f"[{color}]{state}[/{color}] "
                f"{escape(target.label)}: {escape(detail)}"
            )
    return 0 if skipped == 0 and failed == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        LOGGER.warning("Abbruch durch Benutzer (Ctrl+C)")
        for handler in LOGGER.handlers:
            handler.flush()
        Console().print("\n[yellow]Abgebrochen. Der bisherige Stand steht in der Logdatei.[/yellow]")
        raise SystemExit(130) from None
