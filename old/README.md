# FRITZ!Box Passive Devices TUI

Ein kleines `mutt`-artiges TUI zum Auflisten passiver FRITZ!Box-Heimnetzgeraete und zum gezielten Zuruecksetzen markierter Eintraege.
> [!NOTE]
> nicht fertig, weiß nicht mal mehr, obs funktioniert. AI-slop und bei langsamer Fritzbox auch ohne Mehrwert.
> Sag nicht, ich hätte es nicht gesagt.
## Dokumentation

- [HANDOFF.md](HANDOFF.md): Kontext und Arbeitsstand fuer spaetere Codex-Instanzen.
- [FRITZBOX_API_NOTES.md](FRITZBOX_API_NOTES.md): Reverse-engineerte Endpunkte und Payloads.
- [SAFETY.md](SAFETY.md): Sicherheitsmodell und Regeln fuer mutierende Requests.
- [DEVELOPMENT.md](DEVELOPMENT.md): Projektstruktur, Tests und bekannte offene Punkte.

## Installation

```powershell
cd C:\Projekte\fritzbox_passive_tui
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .[test]
```

## Start

```powershell
.\.venv\Scripts\fritzbox-passive-tui.exe
```

Alternativ ohne Installation:

```powershell
$env:PYTHONPATH="src"
python -m fritzbox_passive_tui
```

## Bedienung

- Pfeiltasten, PageUp/PageDown, Home/End: navigieren
- `Enter`: Details anzeigen
- `Esc`: aus Details zurueck
- `d`: aktuelles Geraet zum Entfernen markieren oder Markierung entfernen
- `a`: automatisch entfernbare Geraete markieren, die vor mehr als 90 Tagen zuletzt gesehen wurden
- `q`: beenden; markierte Geraete werden erst nach finaler Bestaetigung zurueckgesetzt

Das Programm laedt alle Daten einmal beim Start. Innerhalb der TUI werden keine weiteren Geraetedetails nachgeladen.
