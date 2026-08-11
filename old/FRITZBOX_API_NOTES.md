# FRITZ!Box API Notes

Diese Notizen dokumentieren die beim Nutzer beobachtete FRITZ!Box-7490-/FRITZ!OS-7.59-Oberflaeche. Es handelt sich nicht um eine offiziell stabile API.

## Login

Start:

```text
GET /login_sid.lua?version=2
```

Beobachtet:

- Antwort XML mit `SID`, `Challenge`, `BlockTime`.
- Challenge-Prefix begann mit `2$60000$`, also PBKDF2-Login.
- Ungueltige SID ist `0000000000000000`.

PBKDF2-Antwort:

```text
challenge = 2$iter1$salt1$iter2$salt2
h1 = PBKDF2-HMAC-SHA256(password_utf8, salt1, iter1)
h2 = PBKDF2-HMAC-SHA256(h1, salt2, iter2)
response = salt2 + "$" + hex(h2)
```

Login-POST:

```text
POST /login_sid.lua?version=2
username=BENUTZERNAME_EINTRAGEN
response=<computed>
```

## Passive Geraeteliste

Funktionierender Request:

```text
POST /data.lua
sid=<SID>
lang=de
xhr=1
page=netDev
xhrId=cleanup
useajax=1
no_sidrenew=
```

Beobachtete Struktur:

```text
data.active: 33 rows
data.passive: 125 rows
```

Wichtige Felder in `data.passive[]`:

- `UID`, z.B. `landevice281905`
- `name`
- `mac`
- `type`
- `state`
- `ipv4.ip`
- `options.editable`
- `options.deleteable`
- `options.disable`
- `model`, bei passiven Eintraegen `passive`

## Device-Details

Auf der 7490 war `edit_device2` falsch und fiel auf `overview` zurueck. Korrekt ist:

```text
POST /data.lua
sid=<SID>
lang=de
xhr=1
page=edit_device
xhrId=all
backToPage=netDev
dev=<UID>
no_sidrenew=
```

Wichtige Felder:

- `data.vars.dev.UID`
- `data.vars.dev.mac`
- `data.vars.dev.devType`
- `data.vars.dev.state`, fuer passive Geraete typischerweise `INACTIVE`
- `data.vars.dev.name.displayName`
- `data.vars.dev.ipv4.current.ip`
- `data.vars.dev.lastused`, optional Unix-Timestamp als String
- `data.vars.dev.page.editable`
- `data.vars.dev.reset.show`
- `data.vars.dev.netAccess.kisi.profiles.selected`
- `data.vars.dev.netAccess.kisi.profiles.list[]`

Nicht jedes passive Geraet hatte `lastused`. In den Beispielen fehlte es bei manchen Geraeten komplett.

## Reset-/Entfernen-Button

Direkt aus `/net/net_edit_device.js` beobachtet:

```javascript
function onResetDev(){
  jsl.setValue("uiViewDeviceName","");
  if(confirmReset()){
    newval.submit("btn_reset_dev", {dev: jsl.getValue("uiDeviceNode")}, {
      onAfterSubmit(){ main.changePage(null, jsl.getValue("uiBackToPage")); }
    });
  }
}
```

`newval.submit` fuegt hinzu:

- `sid`
- `lang`
- `page` aus aktuellem PID, hier `edit_device`
- den Submit-Namen, hier `btn_reset_dev=`

Vom Programm gesendeter mutierender Request:

```text
POST /data.lua
sid=<SID>
lang=de
xhr=1
page=edit_device
back_to_page=netDev
dev=<UID>
btn_reset_dev=
```

Moegliche Confirm-Folge gemaess `/js/newval.js`:

```text
POST /data.lua
sid=<SID>
lang=de
xhr=1
page=edit_device
back_to_page=netDev
dev=<UID>
btn_reset_dev=
confirmed=
```

Die JS-Oberflaeche fragt vorher per Browser-Confirm:

```text
Beim Zuruecksetzen werden alle Einstellungen dieses Geraetes entfernt und das Geraet wird neu ins Heimnetz aufgenommen. Moechten Sie trotzdem fortfahren?
```

Bei aktivem WLAN-MAC-Filter warnt die Oberflaeche zusaetzlich, dass das WLAN-Geraet aus der Liste zugelassener WLAN-Geraete geloescht wird.

## Nicht verwendeter Sammel-Cleanup

Es gibt Hinweise auf einen Sammel-Cleanup ueber `cleanup_landevices`, aber der Nutzer will gerade die Geraete mit individuellen Einstellungen/Filtergruppen behandeln. Deshalb verwendet das Programm den Einzel-Reset ueber `btn_reset_dev`.
