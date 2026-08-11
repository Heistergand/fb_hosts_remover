# Passive Hosts TUI

> [!NOTE]
> ist nicht fertig, macht auch bei sehr lahmer Fritzbox leider wenig Sinn.

Eine mutt-artige Python-TUI zum Anzeigen und Untersuchen inaktiver
FRITZ!Box-Heimnetzgeraete. Alle Routerabfragen laufen ueber das bereits
installierte `fbtr64toolbox.sh`; die TUI implementiert selbst kein TR-064 und
keine FRITZ!Box-Authentifizierung.

Das produktive CSV-Loeschskript liegt getrennt im
[Projektstamm](../README.md). Der Loeschdialog dieser TUI ist nur ein Mockup
und veraendert nichts auf der FRITZ!Box.

## Installation unter Ubuntu

Vom Projektstamm aus:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r tui-projekt/requirements.txt
python tui-projekt/fritz_hosts_tui.py
```

Die Toolbox muss vorher eingerichtet sein und selbststaendig funktionieren:

```bash
fbtr64toolbox.sh hostsinfo --inactive
```

Optional koennen eine Box und ein Konfigurationssuffix weitergereicht werden:

```bash
python tui-projekt/fritz_hosts_tui.py \
  --fbip 192.168.178.1 --conffilesuffix zuhause
```

## Toolbox-Aufrufe

Die Liste wird maschinenlesbar geladen mit:

```bash
fbtr64toolbox.sh hostsinfo --inactive --csvtableoutput
```

Fuer jeden Host werden die Details seriell geladen:

```bash
fbtr64toolbox.sh hostinfo <IP-ADRESSE-ODER-NAME>
```

Die Aufrufe laufen absichtlich nicht parallel, weil die Toolbox feste
temporaere Dateien verwendet.

## Bedienung

- `j`/`k` oder Pfeiltasten: navigieren
- `D`: Loeschmarkierung umschalten
- `r`: Details des ausgewaehlten Hosts neu laden
- `Strg+R`: Hostliste und alle Details neu laden
- `Strg+D`: Mockup-Dialog fuer markierte Hosts
- `Enter`: alle gecachten Details anzeigen
- `q`: beenden

`D`, `r`, `Strg+R` und `Strg+D` sind waehrend des initialen Ladens gesperrt.

## Cache und Zeitstempel

`fritz_hosts_cache.json` enthaelt Kopfdaten, die von `hostinfo` gelieferten
Details, Markierungen und die eigene Sichtungshistorie. Die Tabelle wird beim
Start aus dem Cache aufgebaut und danach zeilenweise aktualisiert.

TR-064 liefert fuer Hosts keinen belastbaren Zeitpunkt `zuletzt aktiv`. Die
TUI speichert daher selbst, wann sie einen Host aktiv erkannt hat. Solange das
unbekannt ist, wird die erste passive Sichtung als `Zuletzt aktiv` angezeigt.

## Technische Grundlage

- [fbtr64toolbox](https://github.com/MarcusRoeckrath/fbtr64toolbox)
- [FRITZ!-Schnittstellen](https://fritz.com/pages/schnittstellen/)
- [TR-064 Hosts Service](https://fritz.support/resources/TR-064_Hosts.pdf)
- [Textual DataTable](https://textual.textualize.io/widgets/data_table/)
- [Textual Workers](https://textual.textualize.io/guide/workers/)
- [Textual ProgressBar](https://textual.textualize.io/widgets/progress_bar/)

