# 📡 Slimproto Protokoll-Referenz

Dokumentation des Slimproto-Protokolls für Resonance-Entwickler.

---

## Übersicht

Slimproto ist das binäre TCP-Protokoll zwischen Squeezebox-Playern und dem Server.

| Eigenschaft | Wert |
|-------------|------|
| Port | 3483 (TCP) |
| Byte-Order | Big-Endian |
| Verbindung | Persistent (Player hält Verbindung offen) |

---

## Message-Format

Jede Nachricht besteht aus:

```
┌──────────────┬──────────────┬─────────────────┐
│ Command      │ Length       │ Payload         │
│ (4 Bytes)    │ (4 Bytes)    │ (Length Bytes)  │
└──────────────┴──────────────┴─────────────────┘
```

- **Command**: 4 ASCII-Zeichen (z.B. `HELO`, `STAT`, `strm`)
- **Length**: Unsigned 32-bit Big-Endian (Länge des Payloads)
- **Payload**: Binärdaten, Format abhängig vom Command

---

## Client → Server Messages

### HELO (Hello/Handshake)

Erste Nachricht vom Player nach Verbindungsaufbau.

```
Offset  Länge  Feld                Beschreibung
------  -----  ------------------  --------------------------------
0       1      Device ID           Gerätetyp (siehe Device IDs)
1       1      Firmware Revision   Firmware-Version
2       6      MAC Address         6 Bytes MAC-Adresse
8       16     UUID                (optional) 16 Bytes UUID
24      2      WLAN Channel List   Bitmap + Flags
26      4      Bytes Received H    High 32-bit
30      4      Bytes Received L    Low 32-bit  
34      2      Language            2-Byte Sprachcode (z.B. "EN")
36      *      Capabilities        Komma-separierte Key=Value Paare
```

**Device IDs:**
| ID | Name |
|----|------|
| 2 | squeezebox |
| 3 | softsqueeze |
| 4 | squeezebox2 |
| 5 | transporter |
| 6 | softsqueeze3 |
| 7 | receiver |
| 8 | squeezeslave/squeezelite |
| 9 | controller |
| 10 | boom |
| 11 | softboom |
| 12 | squeezeplay |

**Capabilities-Beispiel:**
```
Name=Living Room,Model=squeezelite,ModelName=SqueezeLite,MaxSampleRate=192000
```

---

### STAT (Status/Heartbeat)

Periodische Status-Updates und Heartbeat.

```
Offset  Länge  Feld                Beschreibung
------  -----  ------------------  --------------------------------
0       4      Event Code          4-Byte Event (z.B. "STMt")
4       1      CRLFs in Buffer     Anzahl CRLF im Buffer
5       1      MAS Initialized     (SB1 only)
6       1      MAS Mode            (SB1 only)
7       4      Buffer Size         Empfangspuffer-Größe
11      4      Buffer Fullness     Bytes im Empfangspuffer
15      8      Bytes Received      Total empfangene Bytes
23      2      Signal Strength     WLAN-Signalstärke (0-100)
25      4      Jiffies             Uptime in Ticks
29      4      Output Buffer Size  Ausgabepuffer-Größe
33      4      Output Fullness     Bytes im Ausgabepuffer
37      4      Elapsed Seconds     Abspielposition (Sekunden)
41      2      Voltage             (Boom only)
43      4      Elapsed MS          Abspielposition (Millisekunden)
47      4      Server Timestamp    Echo des Server-Timestamps
```

**Event Codes:**

| Code | Bedeutung |
|------|-----------|
| STMa | Autostart |
| STMc | Connected |
| STMd | Decoder ready |
| STMe | Connection established |
| STMf | Flushed |
| STMh | HTTP headers received |
| STMl | Buffer threshold reached |
| STMn | Not supported |
| STMo | Output underrun |
| STMp | Paused |
| STMr | Resume/Playing |
| STMs | Stopped |
| STMt | Timer/Heartbeat |
| STMu | Underrun |

---

### BYE! (Goodbye)

Player trennt Verbindung.

```
Payload: Leer (0 Bytes)
```

---

### IR (Infrarot)

Fernbedienungs-Code empfangen.

```
Offset  Länge  Feld                Beschreibung
------  -----  ------------------  --------------------------------
0       4      Time                Uptime in Ticks (1 kHz)
4       1      Format              IR-Code-Format
5       1      Bits                Anzahl Bits
6       4      Code                IR-Code (bis 32 Bit)
```

---

### DSCO (Disconnect)

Datenstream wurde getrennt.

```
Offset  Länge  Feld                Beschreibung
------  -----  ------------------  --------------------------------
0       1      Reason              Disconnect-Grund
```

---

### RESP (HTTP Response)

HTTP-Response-Header vom Player (bei Proxy-Streaming).

```
Payload: HTTP-Header als Text
```

---

### META (Metadata)

Stream-Metadaten (z.B. ICY-Title).

```
Payload: Metadaten als Text
```

---

### BUTN (Button)

Hardware-Button gedrückt (Transporter, Boom).

```
Offset  Länge  Feld                Beschreibung
------  -----  ------------------  --------------------------------
0       4      Time                Uptime in Ticks
4       4      Button              Button-Code
```

---

### KNOB (Knob)

Drehregler bewegt (Transporter, Boom).

```
Offset  Länge  Feld                Beschreibung
------  -----  ------------------  --------------------------------
0       4      Time                Uptime in Ticks
4       4      Position            Relative Position
8       4      Sync                Sync-Counter
```

---

## Server → Client Messages

### strm (Stream Control)

Steuert Audio-Streaming.

```
Offset  Länge  Feld                Beschreibung
------  -----  ------------------  --------------------------------
0       1      Command             's'=start, 'p'=pause, 'u'=unpause, 'q'=stop
1       1      Autostart           '0'=off, '1'=on, '2'=direct, '3'=direct+auto
2       1      Format              'p'=PCM, 'f'=FLAC, 'm'=MP3, etc.
3       1      PCM Sample Size     '0'=8, '1'=16, '2'=24, '3'=32 bit
4       1      PCM Sample Rate     '0'=11025, '1'=22050, '2'=32000, etc.
5       1      PCM Channels        '1'=mono, '2'=stereo
6       1      PCM Endian          '0'=big, '1'=little
7       1      Threshold           Buffer threshold (KB)
8       1      Spdif Enable        '0'=auto, '1'=off, '2'=on
9       1      Trans Period        Transition period
10      1      Trans Type          '0'=none, '1'=crossfade, etc.
11      1      Flags               Bit-Flags
12      1      Output Threshold    Output buffer threshold
13      1      Slaves              Anzahl Sync-Slaves
14      4      Replay Gain         Replay Gain (fixed-point)
18      2      Server Port         HTTP-Port für Stream
20      4      Server IP           Server-IP (oder 0 für Absender)
24      *      HTTP Request        HTTP-Request String
```

**Stream Commands:**
| Char | Bedeutung |
|------|-----------|
| s | Start streaming |
| p | Pause |
| u | Unpause/Resume |
| q | Stop (quit) |
| t | Status request |
| f | Flush buffer |
| a | Skip ahead |

---

### audg (Audio Gain)

Setzt Lautstärke.

```
Offset  Länge  Feld                Beschreibung
------  -----  ------------------  --------------------------------
0       4      Old Gain Left       (deprecated)
4       4      Old Gain Right      (deprecated)
8       1      Digital Volume      0=analog, 1=digital
9       1      Preamp              Preamp-Einstellung
10      4      New Gain Left       Gain links (Fixed-Point)
14      4      New Gain Right      Gain rechts (Fixed-Point)
18      2      Sequence            Sequenz-Nummer
```

---

### aude (Audio Enable)

Aktiviert/deaktiviert Audio-Ausgänge.

```
Offset  Länge  Feld                Beschreibung
------  -----  ------------------  --------------------------------
0       1      SPDIF Enable        0=off, 1=on
1       1      DAC Enable          0=off, 1=on
```

---

### setd (Set Data)

Setzt Player-Konfiguration.

```
Offset  Länge  Feld                Beschreibung
------  -----  ------------------  --------------------------------
0       1      ID                  Daten-ID
1       *      Data                Wert (abhängig von ID)
```

**Daten-IDs:**
| ID | Bedeutung | Daten |
|----|-----------|-------|
| 0 | Player name | String |
| 4 | Disabled | 0/1 |

---

### grfb/grfe/grfs (Graphics)

Display-Updates (für Player mit Bildschirm).

Nicht relevant für Squeezelite (hat kein Display).

---

## Verbindungsablauf

```
Player                              Server
  │                                    │
  │────── TCP Connect (Port 3483) ────►│
  │                                    │
  │────────────── HELO ───────────────►│
  │                                    │
  │◄─────────── setd (name) ───────────│
  │◄─────────── aude (enable) ─────────│
  │                                    │
  │────────────── STAT ───────────────►│  (Heartbeat alle ~1s)
  │────────────── STAT ───────────────►│
  │                                    │
  │◄─────────── strm (start) ──────────│  (Streaming starten)
  │                                    │
  │────── HTTP GET (Audio-Daten) ─────►│  (Separate HTTP-Verbindung)
  │◄──────── Audio-Stream ─────────────│
  │                                    │
  │────────────── STAT ───────────────►│  (Status während Playback)
  │                                    │
  │◄─────────── strm (stop) ───────────│
  │                                    │
  │────────────── BYE! ───────────────►│
  │                                    │
```

---

## Implementierungsstatus in Resonance

| Message | Richtung | Implementiert | Datei |
|---------|----------|---------------|-------|
| HELO | C→S | ✅ Vollständig | `slimproto.py` |
| STAT | C→S | ✅ Vollständig | `slimproto.py` |
| BYE! | C→S | ✅ Vollständig | `slimproto.py` |
| IR | C→S | 📋 Stub | `slimproto.py` |
| DSCO | C→S | 📋 Stub | `slimproto.py` |
| RESP | C→S | 📋 Stub | `slimproto.py` |
| META | C→S | 📋 Stub | `slimproto.py` |
| BUTN | C→S | 📋 Stub | `slimproto.py` |
| KNOB | C→S | 📋 Stub | `slimproto.py` |
| strm | S→C | ✅ Vollständig | `commands.py`, `slimproto.py` |
| audg | S→C | ✅ Vollständig | `commands.py`, `slimproto.py` |
| aude | S→C | 📋 Stub | `commands.py` |
| setd | S→C | 📋 Stub | - |
| grfe/grfb | S→C | 📋 Stub | `commands.py` |

---

## Referenzen

- `slimserver-public-9.1/Slim/Networking/Slimproto.pm` — Original-Implementierung
- `slimserver-public-9.1/Slim/Player/Squeezebox.pm` — Player-spezifische Befehle
- [Squeezelite Source](https://github.com/ralph-irving/squeezelite) — Client-Implementierung in C