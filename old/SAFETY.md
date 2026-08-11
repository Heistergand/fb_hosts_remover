# Safety Model

Dieses Tool kann Einstellungen fuer FRITZ!Box-Heimnetzgeraete zuruecksetzen. Deshalb gilt: Anzeigen ist billig, Mutieren nur bewusst und spaet.

## Grundregeln

- Passwort nur interaktiv mit `getpass` abfragen.
- Passwort niemals speichern oder loggen.
- SID niemals ausgeben.
- Beim Start duerfen Daten geladen werden.
- Innerhalb der TUI duerfen keine weiteren Netzwerkanfragen fuer Details passieren.
- Mutierende Requests duerfen erst beim Beenden nach expliziter Bestaetigung gesendet werden.

## Markieren ist noch nicht Entfernen

Die Taste `d` setzt nur `Device.marked`. Es wird kein Request gesendet.

Die Taste `a` markiert zusaetzlich passende Geraete, sendet aber ebenfalls keinen Request.

## Autoselect

Automatisch markiert werden nur Geraete, die alle Bedingungen erfuellen:

- passiv geladen
- `Device.removable` ist wahr
- `lastused` ist vorhanden
- `lastused` ist aelter als 90 Tage

Geraete ohne `lastused` bleiben unmarkiert.

## Removable-Bedingung

Ein Geraet gilt nur als entfernbar, wenn:

- `options.deleteable == true`
- `reset.show == true`
- `page.editable == true`
- `state == "INACTIVE"`

Nicht entfernbare Geraete werden angezeigt, koennen aber in der TUI nicht mit `d` markiert werden.

## Finaler Reset

Beim Quit mit markierten Geraeten wird eine Liste mit Anzahl, Namen und MACs gezeigt. Erst `y` in diesem Dialog startet Requests.

Pro Geraet wird sequenziell gearbeitet. Fehler werden gesammelt und am Ende ausgegeben. Exit-Code:

- `0`: nichts zu tun oder alle Reset-Requests erfolgreich
- `1`: Laden fehlgeschlagen oder mindestens ein Reset fehlgeschlagen

## Erster Realtest

Beim ersten Lauf gegen eine echte Box sollte nur ein einzelnes, eindeutig entbehrliches Testgeraet markiert werden. Danach in der FRITZ!Box-Oberflaeche pruefen, ob der Eintrag wie erwartet verschwindet oder nur Einstellungen zurueckgesetzt wurden.
