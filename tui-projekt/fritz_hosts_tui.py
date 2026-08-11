#!/usr/bin/env python3
"""Mutt-like TUI for inspecting inactive hosts through fbtr64toolbox.sh."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import locale
import re
import shutil
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Label, ProgressBar, Static


CACHE_VERSION = 1
DEFAULT_CACHE = Path("fritz_hosts_cache.json")
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def timestamp() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def display_timestamp(value: str) -> str:
    if not value:
        return "-"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    return parsed.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def normalize_mac(value: str) -> str:
    return value.strip().replace("-", ":").upper()


def host_key(mac: str, ip: str, name: str) -> str:
    if mac:
        return "mac:" + normalize_mac(mac)
    if ip:
        return "ip:" + ip.strip().casefold()
    return "name:" + name.strip().casefold()


def is_active(value: str) -> bool:
    return value.strip().casefold() in {"1", "yes", "true", "active", "aktiv"}


@dataclass(slots=True)
class HostCandidate:
    index: str
    active: str
    name: str
    interface: str
    mac: str
    ip: str
    address_source: str = ""
    lease_remaining: str = ""

    @property
    def key(self) -> str:
        return host_key(self.mac, self.ip, self.name)


@dataclass(slots=True)
class HostRecord:
    key: str
    index: str = ""
    active: str = "no"
    name: str = ""
    friendly_name: str = ""
    interface: str = ""
    mac: str = ""
    ip: str = ""
    address_source: str = ""
    lease_remaining: str = ""
    model: str = ""
    port: str = ""
    speed: str = ""
    first_seen_at: str = ""
    last_seen_at: str = ""
    last_active_at: str = ""
    detail_updated_at: str = ""
    visible: bool = True
    marked: bool = False
    details: dict[str, str] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return self.friendly_name or self.name or "(ohne Namen)"

    @property
    def effective_last_active_at(self) -> str:
        return self.last_active_at or self.first_seen_at

    @classmethod
    def from_candidate(
        cls,
        candidate: HostCandidate,
        seen_at: str,
        existing: HostRecord | None = None,
    ) -> HostRecord:
        record = existing or cls(key=candidate.key, first_seen_at=seen_at)
        record.index = candidate.index
        record.active = candidate.active
        record.name = candidate.name or record.name
        record.interface = candidate.interface or record.interface
        record.mac = normalize_mac(candidate.mac) or record.mac
        record.ip = candidate.ip or record.ip
        record.address_source = candidate.address_source or record.address_source
        record.lease_remaining = candidate.lease_remaining
        record.last_seen_at = seen_at
        record.visible = True
        return record


class ToolboxError(RuntimeError):
    def __init__(self, command: list[str], returncode: int, output: str) -> None:
        self.command = command
        self.returncode = returncode
        self.output = output.strip()
        super().__init__(self.output or f"Toolbox endete mit Status {returncode}")

    @property
    def host_not_found(self) -> bool:
        text = self.output.casefold()
        return "not found" in text or "no such" in text


class Toolbox:
    def __init__(
        self,
        executable: str,
        *,
        fbip: str = "",
        conffilesuffix: str = "",
    ) -> None:
        self.executable = executable
        self.fbip = fbip
        self.conffilesuffix = conffilesuffix
        self.encoding = locale.getpreferredencoding(False) or "utf-8"

    def command(self, *arguments: str) -> list[str]:
        command = [self.executable, *arguments]
        if self.fbip:
            command.extend(("--fbip", self.fbip))
        if self.conffilesuffix:
            command.extend(("--conffilesuffix", self.conffilesuffix))
        return command

    async def run(self, *arguments: str) -> str:
        command = self.command(*arguments)
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise ToolboxError(command, 127, f"{self.executable} wurde nicht gefunden") from exc

        stdout, stderr = await process.communicate()
        output = stdout.decode(self.encoding, errors="replace")
        error = stderr.decode(self.encoding, errors="replace")
        if process.returncode:
            combined = "\n".join(part for part in (output, error) if part.strip())
            raise ToolboxError(command, process.returncode, combined)
        return output

    async def inactive_hosts(
        self,
        on_candidate: Callable[[HostCandidate], None] | None = None,
    ) -> list[HostCandidate]:
        command = self.command("hostsinfo", "--inactive", "--csvtableoutput")
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise ToolboxError(command, 127, f"{self.executable} wurde nicht gefunden") from exc

        assert process.stdout is not None
        assert process.stderr is not None
        parser = HostsCsvStreamParser()
        candidates: dict[str, HostCandidate] = {}
        stderr_task = asyncio.create_task(process.stderr.read())

        while line := await process.stdout.readline():
            candidate = parser.feed(line.decode(self.encoding, errors="replace"))
            if candidate is None:
                continue
            candidates[candidate.key] = candidate
            if on_candidate is not None:
                on_candidate(candidate)

        returncode = await process.wait()
        error = (await stderr_task).decode(self.encoding, errors="replace")
        if returncode:
            raise ToolboxError(command, returncode, error)
        return list(candidates.values())

    async def host_details(self, selector: str) -> dict[str, str]:
        return parse_host_details(await self.run("hostinfo", selector))


class HostsCsvStreamParser:
    def __init__(self) -> None:
        self.header: list[str] | None = None

    def feed(self, raw_line: str) -> HostCandidate | None:
        line = ANSI_ESCAPE.sub("", raw_line).strip()
        if ";" not in line:
            return None
        try:
            row = next(csv.reader([line], delimiter=";", quotechar='"'))
        except (csv.Error, StopIteration):
            return None
        while row and not row[-1]:
            row.pop()
        row = [cell.strip() for cell in row]
        if row and row[0] == "Index":
            self.header = row
            return None
        if self.header is None or len(row) < len(self.header):
            return None

        values = dict(zip(self.header, row))
        packed_ip = values.get("IP:Type:Remaining DHCP Lease Time", "")
        ip_parts = packed_ip.split(":", 2)
        ip = ip_parts[0] if ip_parts else ""
        address_source = ip_parts[1] if len(ip_parts) > 1 else ""
        lease_remaining = ip_parts[2] if len(ip_parts) > 2 else ""
        candidate = HostCandidate(
            index=values.get("Index", ""),
            active=values.get("Active", "no"),
            name=values.get("Host name", ""),
            interface=values.get("Interface", ""),
            mac=normalize_mac(values.get("MAC address", "")),
            ip=ip,
            address_source=address_source,
            lease_remaining=lease_remaining,
        )
        if candidate.key in {"name:", "ip:", "mac:"}:
            return None
        return candidate


def parse_hosts_csv(output: str) -> list[HostCandidate]:
    parser = HostsCsvStreamParser()
    unique: dict[str, HostCandidate] = {}
    for raw_line in output.splitlines():
        candidate = parser.feed(raw_line)
        if candidate is not None:
            unique[candidate.key] = candidate

    return list(unique.values())


def parse_host_details(output: str) -> dict[str, str]:
    details: dict[str, str] = {}
    for raw_line in output.splitlines():
        line = ANSI_ESCAPE.sub("", raw_line).strip()
        match = re.match(r"^([^:]+?)\s*:\s*(.*)$", line)
        if not match:
            continue
        key = " ".join(match.group(1).split()).casefold()
        details[key] = match.group(2).strip()
    if not details:
        raise ValueError("hostinfo lieferte keine auswertbaren Detailzeilen")
    return details


def detail(details: dict[str, str], name: str) -> str:
    return details.get(name.casefold(), "")


def apply_details(record: HostRecord, details: dict[str, str], updated_at: str) -> None:
    record.details = details
    record.detail_updated_at = updated_at
    record.name = detail(details, "Host name") or record.name
    record.friendly_name = detail(details, "Friendly name") or record.friendly_name
    record.model = detail(details, "Model") or record.model
    record.mac = normalize_mac(detail(details, "MAC address")) or record.mac
    record.interface = detail(details, "Interface type") or record.interface
    record.port = detail(details, "Port") or record.port
    record.speed = detail(details, "Speed") or record.speed
    record.active = detail(details, "Active") or record.active
    record.last_seen_at = updated_at
    if is_active(record.active):
        record.last_active_at = updated_at


def load_cache(path: Path) -> dict[str, HostRecord]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("version") != CACHE_VERSION:
        raise ValueError("unbekannte Cache-Version")
    raw_hosts = payload.get("hosts", {})
    if not isinstance(raw_hosts, dict):
        raise ValueError("ungueltiger Cache-Inhalt")

    allowed = {item.name for item in fields(HostRecord)}
    records: dict[str, HostRecord] = {}
    for key, raw_record in raw_hosts.items():
        if not isinstance(raw_record, dict):
            continue
        values = {name: value for name, value in raw_record.items() if name in allowed}
        values["key"] = key
        try:
            records[key] = HostRecord(**values)
        except TypeError:
            continue
    return records


def save_cache(path: Path, records: dict[str, HostRecord]) -> None:
    payload = {
        "version": CACHE_VERSION,
        "saved_at": timestamp(),
        "hosts": {key: asdict(record) for key, record in records.items()},
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


class DeleteDialog(ModalScreen[bool]):
    DEFAULT_CSS = """
    DeleteDialog {
        align: center middle;
    }

    DeleteDialog > #delete-dialog {
        grid-size: 2;
        grid-rows: 1fr 3;
        grid-gutter: 1 2;
        width: 56;
        height: 9;
        padding: 1 2;
        border: thick $error 70%;
        background: $surface;
    }

    DeleteDialog #delete-question {
        column-span: 2;
        content-align: center middle;
    }

    DeleteDialog Button {
        width: 100%;
    }
    """

    BINDINGS = [Binding("escape", "dismiss_no", "Nein", show=False)]

    def __init__(self, count: int) -> None:
        super().__init__()
        self.count = count

    def compose(self) -> ComposeResult:
        yield Grid(
            Label(
                f"Alle {self.count} markierten Hosts löschen?",
                id="delete-question",
            ),
            Button("Ja", variant="error", id="yes"),
            Button("Nein", variant="primary", id="no"),
            id="delete-dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def action_dismiss_no(self) -> None:
        self.dismiss(False)


class DetailDialog(ModalScreen[None]):
    DEFAULT_CSS = """
    DetailDialog {
        align: center middle;
    }

    DetailDialog > #detail-dialog {
        width: 86%;
        height: 82%;
        padding: 1 2;
        border: thick $accent 70%;
        background: $surface;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Schliessen", show=False),
        Binding("q", "close", "Schliessen", show=False),
    ]

    def __init__(self, record: HostRecord) -> None:
        super().__init__()
        self.record = record

    def compose(self) -> ComposeResult:
        lines = [
            f"Name: {self.record.display_name}",
            f"IP: {self.record.ip or '-'}",
            f"MAC: {self.record.mac or '-'}",
            f"Erste Sichtung: {display_timestamp(self.record.first_seen_at)}",
            f"Zuletzt gesehen: {display_timestamp(self.record.last_seen_at)}",
            f"Zuletzt aktiv: {display_timestamp(self.record.effective_last_active_at)}",
            "",
        ]
        lines.extend(
            f"{key}: {value or '-'}" for key, value in sorted(self.record.details.items())
        )
        yield VerticalScroll(Static("\n".join(lines)), id="detail-dialog")

    def action_close(self) -> None:
        self.dismiss(None)


class HostsApp(App[None]):
    TITLE = "Passive Hosts"
    SUB_TITLE = "fbtr64toolbox.sh"

    CSS = """
    Screen {
        layout: vertical;
        background: #101214;
    }

    Header {
        background: #d7d7d7;
        color: #101214;
    }

    #loading-area {
        grid-size: 1 2;
        grid-rows: 1 1;
        height: 3;
        padding: 0 1;
        background: #202428;
        display: none;
    }

    #loading-label {
        height: 1;
        color: #f0c674;
    }

    ProgressBar {
        height: 1;
    }

    #hosts {
        height: 1fr;
        border: none;
        background: #101214;
    }

    #hosts:focus > .datatable--cursor {
        background: #d7d7d7;
        color: #101214;
        text-style: bold;
    }

    #status {
        height: 1;
        padding: 0 1;
        background: #30353a;
        color: #eeeeee;
    }

    Footer {
        background: #202428;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Beenden"),
        Binding("j", "cursor_down", "Ab", show=False),
        Binding("k", "cursor_up", "Auf", show=False),
        Binding("d", "toggle_delete", "D Markieren"),
        Binding("r", "reload_selected", "r Details laden"),
        Binding("ctrl+r", "reload_all", "^R Alles laden"),
        Binding("ctrl+d", "delete_marked", "^D Loeschen"),
        Binding("enter", "show_details", "Enter Details"),
    ]

    COLUMNS = (
        ("D", "marked", 1),
        ("Name", "name", 28),
        ("IP", "ip", 15),
        ("MAC", "mac", 17),
        ("Typ", "interface", 8),
        ("Modell", "model", 18),
        ("Zuletzt gesehen", "last_seen", 19),
        ("Zuletzt aktiv", "last_active", 19),
        ("Details", "status", 12),
    )

    def __init__(self, toolbox: Toolbox, cache_path: Path) -> None:
        super().__init__()
        self.toolbox = toolbox
        self.cache_path = cache_path
        self.records: dict[str, HostRecord] = {}
        self.row_keys: set[str] = set()
        self.row_status: dict[str, str] = {}
        self.loading = True

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Grid(
            Label("Hostliste wird geladen ...", id="loading-label"),
            ProgressBar(total=None, show_eta=True, id="progress"),
            id="loading-area",
        )
        yield DataTable(id="hosts", cursor_type="row", zebra_stripes=True)
        yield Label("Bereit", id="status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#hosts", DataTable)
        for title, key, width in self.COLUMNS:
            table.add_column(title, key=key, width=width)

        try:
            self.records = load_cache(self.cache_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self.records = {}
            self.notify(f"Cache konnte nicht gelesen werden: {exc}", severity="warning")

        for record in self.records.values():
            if record.visible:
                self.row_status[record.key] = "Cache"
                self.upsert_row(record)

        table.focus()
        self.set_loading(True, "Hostliste wird geladen ...", total=None)
        self.refresh_all()

    def selected_key(self) -> str | None:
        table = self.query_one("#hosts", DataTable)
        if not self.row_keys or table.row_count == 0:
            return None
        try:
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        except Exception:
            return None
        return str(row_key.value)

    def row_values(self, record: HostRecord) -> tuple[Any, ...]:
        mark = Text.from_markup("[bold red]D[/]") if record.marked else ""
        return (
            mark,
            record.display_name,
            record.ip or "-",
            record.mac or "-",
            record.interface or "-",
            record.model or "-",
            display_timestamp(record.last_seen_at),
            display_timestamp(record.effective_last_active_at),
            self.row_status.get(record.key, "Cache"),
        )

    def upsert_row(self, record: HostRecord) -> None:
        table = self.query_one("#hosts", DataTable)
        values = self.row_values(record)
        if record.key not in self.row_keys:
            table.add_row(*values, key=record.key)
            self.row_keys.add(record.key)
            return
        for (_, column_key, _), value in zip(self.COLUMNS, values):
            table.update_cell(record.key, column_key, value, update_width=False)

    def remove_row(self, key: str) -> None:
        if key not in self.row_keys:
            return
        self.query_one("#hosts", DataTable).remove_row(key)
        self.row_keys.discard(key)
        self.row_status.pop(key, None)

    def persist(self) -> None:
        try:
            save_cache(self.cache_path, self.records)
        except OSError as exc:
            self.notify(f"Cache konnte nicht gespeichert werden: {exc}", severity="error")

    def set_status(self, message: str) -> None:
        self.query_one("#status", Label).update(message)

    def set_loading(self, loading: bool, message: str = "", total: int | None = 0) -> None:
        self.loading = loading
        area = self.query_one("#loading-area", Grid)
        area.display = loading
        if loading:
            self.query_one("#loading-label", Label).update(message)
            self.query_one("#progress", ProgressBar).update(total=total, progress=0)
        else:
            self.query_one("#hosts", DataTable).focus()

    def unavailable_while_loading(self) -> bool:
        if not self.loading:
            return False
        self.notify("Waehren des initialen Ladens nicht verfuegbar", severity="warning")
        return True

    @work(exclusive=True, exit_on_error=False)
    async def refresh_all(self) -> None:
        self.set_loading(True, "Lese inaktive Hosts mit fbtr64toolbox.sh ...", total=None)
        self.set_status("Hostliste wird gelesen")
        previously_visible = set(self.row_keys)

        seen_at = timestamp()
        streamed_keys: set[str] = set()

        def add_candidate(candidate: HostCandidate) -> None:
            streamed_keys.add(candidate.key)
            record = HostRecord.from_candidate(
                candidate,
                seen_at,
                self.records.get(candidate.key),
            )
            self.records[record.key] = record
            self.row_status[record.key] = "Kopfdaten"
            self.upsert_row(record)
            self.query_one("#loading-label", Label).update(
                f"Hostliste: {len(streamed_keys)} inaktive Hosts gefunden"
            )

        try:
            candidates = await self.toolbox.inactive_hosts(add_candidate)
        except (ToolboxError, ValueError) as exc:
            self.set_status(f"Fehler beim Laden der Hostliste: {exc}")
            self.notify(str(exc), severity="error", timeout=8)
            self.set_loading(False)
            return

        current_keys: set[str] = set()
        for candidate in candidates:
            current_keys.add(candidate.key)
            record = self.records[candidate.key]
            self.row_status[record.key] = "Wartet"
            self.upsert_row(record)

        missing_keys = previously_visible - current_keys
        queue = [candidate.key for candidate in candidates]
        queue.extend(key for key in missing_keys if key not in current_keys)
        self.set_loading(
            True,
            f"Lade Details fuer {len(queue)} Hosts ...",
            total=len(queue),
        )

        progress = self.query_one("#progress", ProgressBar)
        for position, key in enumerate(queue, start=1):
            record = self.records.get(key)
            if record is None:
                progress.update(progress=position)
                continue

            self.row_status[key] = "Laedt"
            if key in self.row_keys:
                self.upsert_row(record)
            self.query_one("#loading-label", Label).update(
                f"{position}/{len(queue)}  {record.display_name}"
            )
            selector = record.ip or record.name
            if not selector:
                self.row_status[key] = "Keine ID"
                self.upsert_row(record)
                progress.update(progress=position)
                continue

            try:
                details = await self.toolbox.host_details(selector)
                apply_details(record, details, timestamp())
            except ToolboxError as exc:
                if exc.host_not_found:
                    self.remove_row(key)
                    self.records.pop(key, None)
                elif key in missing_keys:
                    record.visible = False
                    self.remove_row(key)
                else:
                    self.row_status[key] = "Fehler"
                    self.upsert_row(record)
            except ValueError:
                self.row_status[key] = "Fehler"
                if key in self.row_keys:
                    self.upsert_row(record)
            else:
                if is_active(record.active):
                    record.visible = False
                    self.remove_row(key)
                else:
                    record.visible = True
                    self.row_status[key] = "Aktuell"
                    self.upsert_row(record)

            progress.update(progress=position)
            self.persist()

        self.persist()
        self.set_loading(False)
        self.set_status(
            f"{len(self.row_keys)} inaktive Hosts | Cache: {self.cache_path}"
        )

    @work(exclusive=True, exit_on_error=False)
    async def reload_one(self, key: str) -> None:
        record = self.records.get(key)
        if record is None:
            return
        selector = record.ip or record.name
        if not selector:
            self.notify("Host hat weder IP noch Namen", severity="error")
            return

        self.set_loading(True, f"Lade Details fuer {record.display_name} ...", total=1)
        self.row_status[key] = "Laedt"
        self.upsert_row(record)
        try:
            details = await self.toolbox.host_details(selector)
            apply_details(record, details, timestamp())
        except ToolboxError as exc:
            if exc.host_not_found:
                self.remove_row(key)
                self.records.pop(key, None)
                self.set_status(f"{record.display_name} ist nicht mehr vorhanden")
            else:
                self.row_status[key] = "Fehler"
                self.upsert_row(record)
                self.notify(str(exc), severity="error", timeout=8)
        except ValueError as exc:
            self.row_status[key] = "Fehler"
            self.upsert_row(record)
            self.notify(str(exc), severity="error")
        else:
            if is_active(record.active):
                record.visible = False
                self.remove_row(key)
                self.set_status(f"{record.display_name} ist jetzt aktiv")
            else:
                self.row_status[key] = "Aktuell"
                self.upsert_row(record)
                self.set_status(f"Details fuer {record.display_name} aktualisiert")
            self.query_one("#progress", ProgressBar).update(progress=1)
        finally:
            self.persist()
            self.set_loading(False)

    def action_toggle_delete(self) -> None:
        if self.unavailable_while_loading():
            return
        key = self.selected_key()
        if key is None or key not in self.records:
            return
        record = self.records[key]
        record.marked = not record.marked
        self.upsert_row(record)
        self.persist()
        state = "markiert" if record.marked else "nicht mehr markiert"
        self.set_status(f"{record.display_name}: {state}")

    def action_cursor_down(self) -> None:
        table = self.query_one("#hosts", DataTable)
        if table.row_count:
            table.move_cursor(row=min(table.cursor_row + 1, table.row_count - 1))

    def action_cursor_up(self) -> None:
        table = self.query_one("#hosts", DataTable)
        if table.row_count:
            table.move_cursor(row=max(table.cursor_row - 1, 0))

    def action_reload_selected(self) -> None:
        if self.unavailable_while_loading():
            return
        key = self.selected_key()
        if key is not None:
            self.reload_one(key)

    def action_reload_all(self) -> None:
        if self.unavailable_while_loading():
            return
        self.refresh_all()

    def action_delete_marked(self) -> None:
        if self.unavailable_while_loading():
            return
        marked = [record for record in self.records.values() if record.visible and record.marked]
        if not marked:
            self.notify("Keine Hosts markiert")
            return
        self.push_screen(DeleteDialog(len(marked)), self.delete_dialog_result)

    def delete_dialog_result(self, confirmed: bool | None) -> None:
        if confirmed:
            self.notify("Mockup: Es wurden keine Hosts geloescht", severity="warning")
            self.set_status("Loeschen ist noch nicht implementiert")

    def action_show_details(self) -> None:
        key = self.selected_key()
        if key is not None and key in self.records:
            self.push_screen(DetailDialog(self.records[key]))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mutt-artige TUI fuer inaktive Hosts via fbtr64toolbox.sh"
    )
    parser.add_argument("--tool", default="fbtr64toolbox.sh")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--fbip", default="", help="An fbtr64toolbox.sh weiterreichen")
    parser.add_argument(
        "--conffilesuffix",
        default="",
        help="An fbtr64toolbox.sh weiterreichen",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if shutil.which(args.tool) is None:
        print(f"Fehler: {args.tool} wurde nicht gefunden.")
        return 1
    toolbox = Toolbox(
        args.tool,
        fbip=args.fbip,
        conffilesuffix=args.conffilesuffix,
    )
    HostsApp(toolbox, args.cache).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
