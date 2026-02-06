# The Silent UI: Warum Squeezebox-Hardware Resonance „hört“, aber nicht „sieht“
**Status-Report & Problemanalyse Projekt Resonance**

## 1. Das Phänomen: „Split Brain“ Verhalten
Wir befinden uns in einer paradoxen Situation bei der Entwicklung von **Resonance**, unserer Python-Reimplementierung des Logitech Media Servers (LMS). Wir beobachten eine vollständige Diskrepanz zwischen Software-Playern (Squeezelite) und Hardware-Geräten mit Touch-UI (Squeezebox Radio, Boom, Touch).

*   **Squeezelite** funktioniert perfekt: Es entdeckt den Server, streamt Audio, zeigt Metadaten.
*   **Squeezebox Hardware** zeigt ein „Split Brain“-Verhalten:
    1.  **Audio-Ebene (Slimproto/TCP 3483):** ✅ Das Gerät verbindet sich. Der TCP-Handshake (HELO) findet statt. Der Server und das Gerät tauschen Status-Pakete aus (`strm`, `stat`). Technisch ist das Gerät „da“.
    2.  **UI-Ebene (Cometd/HTTP 9000):** ❌ Totenstille. Das Gerät baut **niemals** eine HTTP-Verbindung zu Port 9000 auf.

Ohne diese HTTP-Verbindung gibt es keine Menüs, keine Cover-Art, keine Steuerung über das Display. Das Gerät ist ein „Zombie“ – verbunden, aber steuerungsunfähig.

## 2. Die fehlende Kausalität: Der Trigger
Unsere ursprüngliche Annahme war, dass unsere **Discovery-Antworten** (UDP Broadcasts) fehlerhaft seien. Wir gingen davon aus, dass das Gerät den Server nicht als „gültig“ erkennt und deshalb keine HTTP-Verbindung aufbaut.

Wir haben daraufhin unsere Discovery-Implementierung rigoros gegen LMS abgeglichen und korrigiert:
*   ✅ **UUID:** Korrigiert auf RFC-konforme 36-Zeichen Strings (statt 8 Hex).
*   ✅ **JSON-Port:** Korrigiert auf ASCII-String `"9000"` (statt Integer/Binär).
*   ✅ **Version (VERS):** Korrigiert auf `"7.9.1"`, um den Firmware-Bug (Version-Compare bei Firmware 7.7.x) zu umgehen.

Das Ergebnis: Das Verhalten änderte sich **nicht**. Die Geräte ignorieren den HTTP-Port weiterhin.

## 3. Die Erkenntnis: Das „State Gate“ (Research Gold)
Durch tiefgehende Analyse des Client-Sourcecodes (`JiveLite`, `SlimDiscoveryApplet.lua`) und unsere Dokumente `Research_gold.md` & `II` haben wir die wahre Ursache isoliert. Es handelt sich nicht um einen Fehler im Resonance-Servercode, sondern um eine **Logik-Sperre im Client**.

Der SqueezePlay-Client (die Software auf der Box) besitzt eine Zustandsmaschine mit fünf Status. Die Funktion `_serverUpdateAddress`, die durch unsere Discovery getriggert wird, enthält eine harte Bedingung:

```lua
-- Pseudocode Logik aus SlimDiscoveryApplet.lua
function _serverUpdateAddress(server, ip, port)
    server:updateAddress(ip, port) -- Update interner Daten

    -- DER BLOCKER:
    if state == 'searching' OR state == 'probing' then
        server:connect() -- Triggert HTTP/Cometd
    end
    -- Wenn state == 'connected', passiert HIER NICHTS.
end
```

**Die Hypothese:**
Unsere Squeezebox-Hardware befindet sich im Zustand **`connected`**. Sie glaubt, bereits verbunden zu sein – höchstwahrscheinlich mit **mysqueezebox.com** (SqueezeNetwork).

## 4. Der „Geist“ von MySqueezebox.com
Hier kommt der externe Faktor ins Spiel: Logitech hat die `mysqueezebox.com` Server im **Februar 2024** abgeschaltet.

Geräte (besonders nach einem Factory Reset) versuchen aggressiv, diese Server zu erreichen (`baby.squeezenetwork.com`, `fab4...`). Da diese Server nicht mehr antworten (oder DNS-Fehler werfen), bleiben die Geräte in einem "Setup-Limbo" oder einem "Phantom-Connected"-Zustand hängen. Der Setup-Wizard auf Original-Firmware lässt den User oft gar nicht erst ins Hauptmenü, um einen lokalen Server zu wählen.

Das erklärt exakt unser Wireshark-Bild (ws21):
*   UDP Discovery kommt an.
*   Slimproto (Audio) verbindet sich (da dies separate Logik ist).
*   Aber der **Cometd-Connect (HTTP)** wird unterdrückt, weil der übergeordnete Applet-State blockiert ist.

## 5. Fazit & Lösungsweg
Das Problem ist **nicht**, dass Resonance falsch antwortet. Das Problem ist, dass das Endgerät aufgrund veralteter Firmware-Logik und abgeschalteter Cloud-Dienste nicht bereit ist, "zuzuhören".

**Die nächsten Schritte sind nicht in Python (Server-Code) zu suchen, sondern in der Infrastruktur:**

1.  **Beweis:** Analyse von `ws21.pcapng` auf DNS-Queries zu `*.squeezenetwork.com`.
2.  **Fix A (Infrastruktur):** DNS-Spoofing/Redirection. Wir müssen dem Gerät vorgaukeln, dass Resonance `mysqueezebox.com` ist (oder zumindest erreichbar), damit der Setup-Wizard durchläuft oder der State resetet.
3.  **Fix B (Client):** Installation der Community-Firmware (8.5+), welche die Abhängigkeit zu MySqueezebox entfernt hat.

Wir stehen kurz vor dem Durchbruch – wir haben nur an der falschen Stelle (Server-Code) gesucht, während das Problem im "Trauma" des verlassenen Clients liegt.