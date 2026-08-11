# Inaktive FRITZ!Box-Hosts löschen
Ein stumpfes python skript sorgt dafür, dass deine FritzBox wieder aufgeräumt wird, damit Du währenddessen was schöneres machen kannst.
## Vorwort
Die Ursprüngliche Idee war eine komfortable TUI Oberfläche, die das ganze *mal eben* 
bedienbar macht. Da ich feststellen musste, dass auch mit den verschiedenen API-Zugriffsmethoden, 
sei es WebUI-/Lua oder TR-064, die Antwortzeiten zum auflisten und löschen der hosts 
nicht wirklich angenehmer wurden, habe ich diese schöne Idee wieder verworfen und bin 
zur pragmatischeren Lösung übergegangen, mit einer Methode die hosts zu ermitteln,
diese manuell in der Datei mit einem normalen Editor zu selektieren und dann die 
liste der Kandidaten dem nächsten Skript zum Fraß vorzuwerfen. Das läuft für 118 Hosts 
auch mal eben locker zwei Stunden oder länger, aber dafür unbeaufsichtigt und ich kann die 
Zeit mit etwas schönerem verbringen. Zum Beipiel damit, diesen Text für euch zu schreiben.

Die abgebrochenen versuche findet ihr in den ordnern old und tui-projekt. 
Deswegen heißt das Repo auch noch so.

## KI Disclaimer
Natürlich habe ich, obwohl ich finde, dass ich ganz passabel programmieren kann, der 
heutigen Zeit angepasst eher dem Prompten gefrönt. Daher ist der Rest hier auch von 
der Codex KI verzapft. Läuft aber.

##  Zusätzliches Erklärbär Zeugs

`delete_inactive_hosts.py` ist ein Workaround als Ergänzung zur
`fbtr64toolbox.sh`. Die Toolbox ermittelt die inaktiven Hosts und erzeugt die
CSV-Datei; dieses Skript entfernt die darin ausgewählten Einträge einzeln
über die FRITZ!Box-Weboberfläche.

Der Workaround wird benötigt, wenn die FRITZ!Box unter **Heimnetz > Netzwerk >
Netzwerkverbindungen** die ungenutzten Verbindungen nicht vollständig
massenhaft entfernt. Das betrifft insbesondere Geräte mit individuellen
Einstellungen, beispielsweise einem zugewiesenen Kinder- oder Zugangsprofil.
Solche Einträge behält die normale Sammelbereinigung bei. Das Skript kann die
zuvor bewusst in der CSV ausgewählten Einträge trotzdem einzeln zurücksetzen.

Die MAC-Adresse dient zur eindeutigen Zuordnung; der Hostname wird nur für
Fortschritt und Log verwendet.

Die separate Textual-Oberfläche liegt unter
[tui-projekt](tui-projekt/README.md).

## Voraussetzungen

- Ubuntu mit Python 3
- eine eingerichtete und funktionierende
  [fbtr64toolbox](https://github.com/MarcusRoeckrath/fbtr64toolbox)
- Zugriff auf die Weboberfläche der FRITZ!Box

Die Python-Abhängigkeit kann in einer virtuellen Umgebung installiert werden:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## CSV mit fbtr64toolbox erzeugen

Alle derzeit inaktiven Hosts werden mit der CSV-Ausgabe der Toolbox in eine
Datei geschrieben:

```bash
fbtr64toolbox.sh hostsinfo --inactive --csvtableoutput > inactive.csv
```

Die Datei kann danach in einem Editor oder Tabellenprogramm weiter gefiltert
werden. Die Kopfzeile und reine Informationszeilen der Toolbox ignoriert das
Löschskript. Ein Datensatz hat beispielsweise dieses Format:

```text
"1";"no";"KUEHLSCHRANK-42";"";"DE:AD:BE:EF:42:17";"192.168.178.234:DHCP:0"
```

Relevant sind Feld 3 als Anzeigename und Feld 5 als MAC-Adresse.

## Aufruf

Ohne Optionen werden `inactive.csv`, die URL `https://fritz.box` und der im
Skript konfigurierte Standardbenutzer verwendet. Das Kennwort wird verdeckt
abgefragt:

```bash
python delete_inactive_hosts.py
```

Alle Laufzeitparameter können überschrieben werden:

```bash
python delete_inactive_hosts.py \
  --file alte_hosts.csv \
  --url https://fritz.box \
  --user fritz0123
```

Verfügbare Optionen:

```text
-f, --file FILE.csv
-u, --user BENUTZER
    --url URL
```

Das Skript fragt das Kennwort immer verdeckt ab und nimmt es nicht als
Kommandozeilenargument entgegen.

## Ablauf und Protokoll

Nach der Bestätigung meldet sich das Skript einmal an der Weboberfläche an.
Es ermittelt über `data.lua` die zu den CSV-MAC-Adressen gehörenden internen
Geräte-IDs und verarbeitet danach alle Einträge innerhalb derselben Sitzung.
Bereits entfernte Hosts werden als `MAC nicht gefunden` übersprungen.

Die Fortschrittsanzeige zeigt den aktuellen Host, Anzahl, Balken und eine
laufend herunterzählende Restzeit. Wegen der langsamen `data.lua` gilt für
HTTP-Aufrufe ein Timeout von 180 Sekunden.

Bei einer FRITZ!Box 7490 kann bereits das Öffnen beziehungsweise Bearbeiten
eines einzelnen Geräteeintrags bis zu 30 Sekunden dauern. Bei einer grösseren
Liste kommt dadurch leicht etwa eine Stunde zusammen. Das Skript erledigt diese
wiederholten Schritte selbstständig, sodass man diese Stunde schöner
verbringen kann, als vor der Weboberfläche auf den jeweils nächsten Eintrag zu
warten.

Jeder Schritt wird sofort mit Zeitstempel an `delete_inactive_hosts.log`
angehängt. Das Protokoll bleibt bei `Ctrl+C` oder einem Fehler erhalten und
enthält weder Kennwort noch SID.

## Hinweis

Das Skript benutzt interne, nicht offiziell stabile Endpunkte der
FRITZ!Box-Weboberfläche. Das Entfernen entspricht dem Zurücksetzen eines
Geräteeintrags über `btn_reset_dev`.
