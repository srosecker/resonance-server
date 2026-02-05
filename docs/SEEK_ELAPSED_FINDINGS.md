# Seek & Elapsed Time: LMS-Kompatible Implementierung

## Das Problem

Nach einem Seek (z.B. zu Position 30s) zeigte der Slider falsche Werte:
- Erwartung: 30s, 31s, 32s...
- Realität: 33s, 38s, 45s... (oder andere falsche Werte)

## Ursache

Squeezelite (und andere Slimproto-Player) reportet `elapsed` **relativ zum Stream-Start**, nicht zur absoluten Track-Position.

**Beispiel:**
1. Track läuft bei 5s
2. User seekt zu 30s
3. Server startet neuen Stream ab 30s
4. Player empfängt neuen Stream und reportet: `elapsed=0, 1, 2, 3...`
5. Die **echte** Track-Position ist: `30+0=30, 30+1=31, 30+2=32...`

## LMS-Lösung (aus SlimServer Quellcode)

In `Slim/Player/StreamingController.pm` Zeile 1727-1741:

```perl
my $client      = master($self);
my $songtime    = $client->songElapsedSeconds();
my $song        = playingSong($self) || return 0;
my $startStream = $song->startOffset() || 0;
my $duration    = $song->duration();

if (defined($songtime)) {
    $songtime = $startStream + $songtime;

    # limit check
    if ($songtime < 0) {
        $songtime = 0;
    } elsif ($duration && $songtime > $duration) {
        $songtime = $duration;
    }

    return $songtime;
}
```

**LMS macht:**
1. `startOffset` = Seek-Position (wird beim Seek gesetzt)
2. `songElapsedSeconds` = Was der Player reportet (relativ zum Stream-Start)
3. **Ergebnis = `startOffset + songElapsedSeconds`**
4. **Limit-Check:** Ergebnis wird auf `[0, duration]` begrenzt

**KEINE HEURISTIKEN** - das ist die komplette Logik!

Der `startOffset` wird beim Seek gesetzt (in `File.pm`, `HTTP.pm`, `MMS.pm`, etc.):
```perl
$song->startOffset($seekdata->{'timeOffset'});
```

## Unsere Implementierung

### 1. Start-Offset speichern (StreamingServer)

In `resonance/streaming/server.py`:

```python
def queue_file_with_seek(self, player_mac, file_path, start_seconds, ...):
    # Record start offset (LMS-style) so status can calculate correct position.
    # After seek, player reports elapsed relative to stream start (0, 1, 2...).
    # Real position = start_offset + raw_elapsed (e.g., 30 + 0 = 30, 30 + 1 = 31...).
    self._start_offset[player_mac] = float(start_seconds)

def queue_file(self, player_mac, file_path):
    # Clear start offset for non-seek queueing (track starts from beginning).
    self._start_offset.pop(player_mac, None)

def get_start_offset(self, player_mac: str) -> float:
    """Get the start offset for a player (LMS-style startOffset)."""
    return self._start_offset.get(player_mac, 0.0)
```

### 2. Elapsed berechnen (Status Handler)

In `resonance/web/handlers/status.py` und `resonance/web/routes/api.py`:

```python
# Get raw elapsed from player (relative to stream start after seek)
raw_elapsed_sec = status.elapsed_milliseconds / 1000.0

# Get start offset from streaming server (LMS-style startOffset)
start_offset = streaming_server.get_start_offset(player_id)

# Calculate actual elapsed: start_offset + raw_elapsed (LMS formula)
elapsed_sec = start_offset + raw_elapsed_sec

# Cap elapsed to duration (never show more than 100% progress)
if duration_sec > 0 and elapsed_sec > duration_sec:
    elapsed_sec = duration_sec
```

### 3. Raw Elapsed immer akzeptieren (Slimproto)

**WICHTIG:** In `resonance/protocol/slimproto.py` dürfen wir den `elapsed`-Wert vom Player **NICHT filtern**:

```python
# RICHTIG: Immer akzeptieren
client.status.elapsed_seconds = elapsed_seconds
client.status.elapsed_milliseconds = elapsed_ms

# FALSCH: Filtering verhindert korrekte Seek-Berechnung!
# if elapsed > 0:  # <-- NICHT machen!
#     client.status.elapsed_seconds = elapsed_seconds
```

Der Player **SOLL** `elapsed=0` reporten wenn ein neuer Stream startet. Das ist korrekt und notwendig für die Offset-Berechnung.

## Wann wird der Start-Offset gecleart?

Der Offset (`_start_offset`) wird gecleart wenn:
- Ein neuer Track startet (`queue_file()` ohne Seek)
- Ein neuer Seek passiert (überschreibt den alten)
- Byte-basiertes Seeking verwendet wird

Der Offset wird **NICHT** zeitbasiert gecleart, da er für die gesamte Restdauer des Tracks benötigt wird.

## Zusammenfassung

| Komponente | Aufgabe |
|------------|---------|
| `StreamingServer` | Speichert `_start_offset` (Seek-Position) beim Seek |
| `slimproto.py` | Akzeptiert **immer** den rohen `elapsed` vom Player |
| `status.py` / `api.py` | Berechnet `elapsed = start_offset + raw_elapsed` |
| Duration-Cap | Verhindert Werte > 100% |

## Die Formel (EINFACH!)

```
elapsed = start_offset + raw_elapsed
```

Das ist alles! Keine komplizierten Heuristiken zur Erkennung von "alten" vs "neuen" Stream-Daten. LMS vertraut darauf, dass der Player schnell genug auf den neuen Stream wechselt.

## Warum keine Heuristiken?

In früheren Versionen hatten wir komplexe Heuristiken:
- Zeitfenster-basierte Erkennung von "alten" Stream-Daten
- Generation-Counter zum Tracking von Stream-Wechseln
- Sticky-Elapsed für transiente Nullen

**Das war unnötig!** LMS macht es einfacher:
1. Wenn der Player während des Stream-Wechsels `stopped` ist, gibt `songElapsedSeconds()` 0 zurück
2. Dann ist `playingSongElapsed = startOffset + 0 = startOffset` (genau die Seek-Position!)
3. Sobald der neue Stream läuft: `startOffset + raw_elapsed` = korrekte Position

## Referenz

- LMS Quellcode: `Slim/Player/StreamingController.pm` → `playingSongElapsed()` (Zeile 1720-1795)
- LMS Quellcode: `Slim/Player/Squeezebox2.pm` → `songElapsedSeconds()` (Zeile 432-460)
- LMS Quellcode: `Slim/Networking/Slimproto.pm` → `getPlayPointData()` (Zeile 881-884)
- LMS Quellcode: `Slim/Player/Protocols/File.pm` → `startOffset` Setzung (Zeile 196-198)
- LMS Quellcode: `Slim/Player/Protocols/HTTP.pm` → `startOffset` Setzung (Zeile 976-979)