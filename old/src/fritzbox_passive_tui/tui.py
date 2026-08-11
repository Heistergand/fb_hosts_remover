from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import ModalScreen, Screen
from textual.widgets import DataTable, Footer, Header, Label, Static

from .models import Device


class ConfirmQuit(ModalScreen[bool]):
    DEFAULT_CSS = """
    ConfirmQuit {
        align: center middle;
    }
    ConfirmQuit > Container {
        width: 78;
        height: auto;
        border: tall $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    BINDINGS = [
        Binding("y", "yes", "Ja"),
        Binding("n", "no", "Nein"),
        Binding("escape", "no", "Abbrechen"),
    ]

    def __init__(self, devices: list[Device]) -> None:
        super().__init__()
        self.devices = devices

    def compose(self) -> ComposeResult:
        names = "\n".join(f"- {d.name} ({d.mac})" for d in self.devices[:12])
        more = "" if len(self.devices) <= 12 else f"\n... und {len(self.devices) - 12} weitere"
        yield Container(
            Label(f"{len(self.devices)} Geraete wirklich entfernen/zuruecksetzen?\n\n{names}{more}\n\n[y] Ja  [n/Esc] Nein")
        )

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)


class DetailScreen(Screen[None]):
    BINDINGS = [Binding("escape", "back", "Zurueck")]

    def __init__(self, device: Device) -> None:
        super().__init__()
        self.device = device

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(self._details(), id="details")
        yield Footer()

    def _details(self) -> str:
        d = self.device
        ipv4 = d.detail.get("ipv4", {})
        ipv6 = d.detail.get("ipv6", {})
        wake = d.detail.get("wakeOnLan", {})
        dev_details = d.detail.get("devDetails", {})
        return "\n".join(
            [
                f"Name:          {d.name}",
                f"UID:           {d.uid}",
                f"MAC:           {d.mac}",
                f"MAC Details:   {dev_details.get('mac', '') if isinstance(dev_details, dict) else ''}",
                f"IPv4:          {d.ip or '-'}",
                f"IPv4 DHCP:     {ipv4.get('dhcp') if isinstance(ipv4, dict) else ''}",
                f"IPv4 current:  {ipv4.get('current') if isinstance(ipv4, dict) else ''}",
                f"IPv6:          {ipv6.get('current') if isinstance(ipv6, dict) else ''}",
                f"Typ:           {d.dev_type}",
                f"Status:        {d.state}",
                f"Last Seen:     {d.last_seen_label}",
                f"Filterprofil:  {d.filter_profile} ({d.filter_profile_id})",
                f"Deleteable:    {d.deleteable}",
                f"Reset show:    {d.reset_show}",
                f"Page editable: {d.page_editable}",
                f"Removable:     {d.removable}",
                f"Wake-on-LAN:   {wake if isinstance(wake, dict) else ''}",
                f"Hersteller:    {d.detail.get('manufacturer', '')}",
                "",
                "Esc: zurueck",
            ]
        )

    def action_back(self) -> None:
        self.app.pop_screen()


class PassiveDeviceApp(App[set[str]]):
    CSS = """
    #status {
        dock: bottom;
        height: 1;
        background: $panel;
    }
    DataTable {
        height: 1fr;
    }
    #details {
        padding: 1 2;
    }
    """

    BINDINGS = [
        Binding("d", "toggle_delete", "Markieren"),
        Binding("a", "autoselect", "Auto"),
        Binding("enter", "details", "Details"),
        Binding("q", "quit_requested", "Beenden"),
    ]

    def __init__(self, devices: list[Device]) -> None:
        super().__init__()
        self.devices = devices
        self.table: DataTable[str] | None = None
        self.status = Static()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        table: DataTable[str] = DataTable(cursor_type="row", zebra_stripes=True)
        table.add_columns("D", "Last Seen", "Name", "IP", "MAC", "Typ", "Profil")
        self.table = table
        yield table
        self.status = Static(id="status")
        yield self.status
        yield Footer()

    def on_mount(self) -> None:
        self.title = "FRITZ!Box passive devices"
        self._rebuild_table()

    def _rebuild_table(self) -> None:
        assert self.table is not None
        self.table.clear()
        for index, device in enumerate(self.devices):
            marker = "D" if device.marked else ("-" if not device.removable else " ")
            self.table.add_row(
                marker,
                device.last_seen_label,
                device.name,
                device.ip or "-",
                device.mac or "-",
                device.dev_type or "-",
                device.filter_profile or "-",
                key=str(index),
            )
        self._update_status()

    def _update_status(self) -> None:
        marked = sum(1 for d in self.devices if d.marked)
        removable = sum(1 for d in self.devices if d.removable)
        self.status.update(
            f"{len(self.devices)} passive | {removable} entfernbar | {marked} markiert | d=toggle a=auto enter=details q=quit"
        )

    def _current_device(self) -> Device | None:
        if self.table is None or self.table.cursor_row < 0:
            return None
        key = self.table.coordinate_to_cell_key(self.table.cursor_coordinate).row_key
        if key is None:
            return None
        value = key.value if hasattr(key, "value") else key
        return self.devices[int(value)]

    def action_toggle_delete(self) -> None:
        device = self._current_device()
        if device is None:
            return
        if device.removable:
            device.marked = not device.marked
            self._rebuild_table()
        else:
            self.notify("Dieses Geraet ist nicht entfernbar.", severity="warning")

    def action_autoselect(self) -> None:
        cutoff = datetime.now() - timedelta(days=90)
        count = 0
        for device in self.devices:
            if device.removable and device.last_seen is not None and device.last_seen < cutoff and not device.marked:
                device.marked = True
                count += 1
        self._rebuild_table()
        self.notify(f"Autoselect: {count} Geraete zusaetzlich markiert.")

    def action_details(self) -> None:
        device = self._current_device()
        if device is not None:
            self.push_screen(DetailScreen(device))

    def action_quit_requested(self) -> None:
        marked = [d for d in self.devices if d.marked]
        if not marked:
            self.exit(set())
            return

        def done(confirmed: bool | None) -> None:
            self.exit({d.uid for d in marked} if confirmed else set())

        self.push_screen(ConfirmQuit(marked), done)


def run_tui(devices: Iterable[Device]) -> set[str]:
    app = PassiveDeviceApp(list(devices))
    result = app.run()
    return result or set()
