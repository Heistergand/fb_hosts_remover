from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class Device:
    uid: str
    name: str
    mac: str
    ip: str
    dev_type: str
    state: str
    filter_profile: str
    filter_profile_id: str
    deleteable: bool
    reset_show: bool
    page_editable: bool
    lastused: int | None
    detail: dict[str, Any] = field(repr=False)
    list_row: dict[str, Any] = field(repr=False)
    marked: bool = False

    @property
    def removable(self) -> bool:
        return self.deleteable and self.reset_show and self.page_editable and self.state == "INACTIVE"

    @property
    def last_seen(self) -> datetime | None:
        if self.lastused is None:
            return None
        try:
            return datetime.fromtimestamp(self.lastused)
        except (OverflowError, OSError, ValueError):
            return None

    @property
    def last_seen_label(self) -> str:
        seen = self.last_seen
        if seen is None:
            return "unbekannt"
        return seen.strftime("%Y-%m-%d %H:%M")


@dataclass(slots=True)
class ResetResult:
    uid: str
    name: str
    ok: bool
    message: str
