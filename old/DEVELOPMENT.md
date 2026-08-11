# Development Notes

## Struktur

```text
src/fritzbox_passive_tui/
  auth.py       Login-Challenge-Berechnung
  client.py     FRITZ!Box HTTP-Client und Reset-Flow
  cli.py        Prompting, Laden, TUI starten, Reset-Ergebnisse ausgeben
  models.py     Device- und ResetResult-Dataclasses
  parser.py     JSON zu Device-Modell, Sortierung
  requests.py   Reine Request-Payload-Helfer ohne externe Dependencies
  tui.py        Textual-App, Liste, Details, Confirm-Dialog
```

## Installation fuer Entwicklung

```powershell
cd C:\Projekte\fritzbox_passive_tui
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .[test]
.\.venv\Scripts\python.exe -m pytest
```

## Start

```powershell
.\.venv\Scripts\fritzbox-passive-tui.exe
```

oder:

```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\python.exe -m fritzbox_passive_tui
```

## Tests

Vorhandene Tests:

- PBKDF2- und Legacy-Login-Response
- Passive-Listen-Parser
- Detail-Parser zu `Device`
- Sortierung: bekannte `lastused` zuerst, danach unbekannt
- Autoselect-Regel als Kernlogik
- Reset-Payload mit und ohne `confirmed=`

Beim Implementieren stand lokal kein `pytest`, `requests` oder `textual` in der Codex-Runtime bereit. Syntax wurde mit `compileall` geprueft; die echten Tests sollten nach Installation laufen.

## Bekannte offene Punkte

- `textual`-APIs aendern sich gelegentlich. Falls die Tabelle nicht startet, zuerst `DataTable` und `coordinate_to_cell_key` in `tui.py` pruefen.
- Der Reset-Erfolg wird aktuell aus `data.btn_reset_dev` interpretiert. Falls die Box anders antwortet, die Antwort eines einzelnen Test-Resets anonymisiert erfassen und `client.reset_device` anpassen.
- Der TUI zeigt aktuell eine feste Sortierung. Weitere Sortier-Tasten koennen spaeter ergaenzt werden.
- TLS-Verifikation ist deaktiviert. Das ist fuer die lokale `https://fritz.box`-Oberflaeche pragmatisch, sollte aber nicht fuer fremde Hosts verallgemeinert werden.

## Keine Chat-Abhaengigkeit

Alle fuer die Fortsetzung wichtigen Reverse-Engineering-Erkenntnisse stehen in `FRITZBOX_API_NOTES.md`. Eine spaetere Instanz muss den urspruenglichen Chat nicht kennen.
