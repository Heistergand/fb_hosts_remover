# Handoff

Dieses Projekt entstand aus einer Copy/Paste-Erkundung einer FRITZ!Box 7490 im lokalen LAN. Die Sandbox hatte keinen Zugriff auf die Box und kein Passwort. Alle Erkenntnisse zu Endpunkten stammen aus vom Nutzer ausgefuehrten Probe-Scripts und aus den JS-Dateien der Box.

## Ziel

Ein Python-TUI im Stil von `mutt`, das passive FRITZ!Box-Heimnetzgeraete einmalig laedt, sortiert anzeigt, Details ohne Nachladen zeigt und markierte Geraete erst beim Beenden nach finaler Bestaetigung zuruecksetzt.

## Zielgeraet

- Modell: FRITZ!Box 7490
- FRITZ!OS: 7.59
- Host: normalerweise `https://fritz.box`
- Default-User: `BENUTZERNAME_EINTRAGEN`
- HTTP-Timeout: fest `180` Sekunden

## Implementierter Stand

- Projekt unter `src/fritzbox_passive_tui`.
- CLI-Einstieg: `fritzbox_passive_tui.cli:main`.
- TUI: `textual`-basiert, Navigation per Tastatur.
- HTTP: `requests.Session`, TLS-Verifikation deaktiviert, weil lokale FRITZ!Box-Zertifikate typischerweise selbstsigniert sind.
- Login: `/login_sid.lua?version=2` mit PBKDF2 und Legacy-Fallback.
- Initialload:
  - `POST /data.lua` `page=netDev`, `xhrId=cleanup`
  - fuer jedes passive Device `POST /data.lua` `page=edit_device`, `xhrId=all`
- Reset:
  - `POST /data.lua` `page=edit_device`, `dev=<UID>`, `btn_reset_dev=`
  - bei JSON-Status `confirm` zweiter Request mit `confirmed=`

## Wichtige Annahmen

- "Entfernen" bedeutet der UI-Button "Einstellungen zuruecksetzen" fuer ein Geraet, nicht der eingeschraenkte Sammel-Cleanup.
- Passive Geraete ohne `lastused` werden angezeigt, aber nicht automatisch markiert.
- "3 Monate" ist als 90 Tage implementiert.
- Der TUI-Snapshot ist statisch; nach Start werden keine Details nachgeladen.

## Was eine spaetere Instanz zuerst tun sollte

1. Dependencies installieren: `python -m pip install -e .[test]`.
2. `python -m pytest` ausfuehren.
3. Falls `textual`-API-Probleme auftreten, zuerst `src/fritzbox_passive_tui/tui.py` pruefen.
4. Mit `--url`, `--user` optional starten; Passwort interaktiv via `getpass`.
5. Echte Reset-Funktion nur an einem bewusst ausgewaehlten Testgeraet pruefen.

## Bekannte Umgebungseinschraenkung bei Erstellung

Die Codex-Runtime hatte beim Implementieren kein `requests`, kein `textual` und kein `pytest` installiert. Verifiziert wurde deshalb mit `compileall` und einem kleinen dependency-freien Kerncheck. Vollstaendige Tests muessen nach Installation der Dependencies laufen.
