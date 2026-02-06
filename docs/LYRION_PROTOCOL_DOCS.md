# Lyrion Protocol Documentation

> Compiled from https://lyrion.org/reference/

---

## Table of Contents

1. [SlimProto Protocol](#slimproto-protocol)
2. [SLIMP3 Protocol](#slimp3-protocol)
3. [IP3K Graphics (Classic/Boom/Transporter)](#ip3k-graphics)
4. [Home Menu vs SlimBrowse Items](#home-menu-vs-slimbrowse-items)
5. [Adding Menus on SqueezePlay](#adding-menus-on-squeezeplay)
6. [Database Structure](#database-structure)

---

## SlimProto Protocol

> Note: Always check the Perl source code, this documentation is not in sync with actual byte length in multiple places

The SlimProto protocol is the protocol developed for the Squeezebox and replaces the SLIMP3 one. It is designed to allow the players to communicate effectively over WANs as well as LANs.

The server listens on **TCP port 3483** for connections by players. To register a player with the server, they exchange "helo"s and then any of the commands below are valid.

The client also listens on **UDP port 3483** for SlimProto commands from the server it has already established a TCP connection with.

### Client → Server Communications

A command to the server consists of three parts:
1. The 1st 4 bytes specify the operation
2. The 2nd 4 bytes is the length of the data packet (in network order)
3. The 3rd part is the data itself

#### Supported Operations

| Operation | Description |
|-----------|-------------|
| HELO | Hello - alerts server to client presence |
| BYE! | Client disconnecting |
| STAT | Heartbeat and play-event notification |
| RESP | HTTP headers from data stream |
| BODY | HTTP body from data stream |
| META | Metadata from stream |
| DSCO | Data stream disconnected |
| DBUG | Reports firmware revision |
| IR   | Infrared remote code (note: padded with spaces) |
| RAWI | Raw infra-red |
| ANIC | Animation complete |
| BUTN | Hardware button (Transporter) |
| KNOB | Hardware knob (Transporter) |
| SETD | Update preferences |
| UREQ | Firmware update request |

### HELO Message

Data Length: 10, 20, or 36 bytes, depending upon deviceID and firmware revision.

| Field | Length | Notes |
|-------|--------|-------|
| DeviceID | 1 byte | See device IDs below |
| Revision | 1 byte | Firmware revision number |
| MAC 0-5 | 6 bytes | Player's MAC address |
| UUID 0-15 | 16 bytes | Unique identifier (newer firmware only) |
| WLanChannelList | 2 bytes | 802.11 channels enabled (bitfield) |
| Bytes received | 8 bytes | Data-stream bytes received |
| Language | 2 bytes | Country code |

#### Device IDs

| ID | Device |
|----|--------|
| 2 | Squeezebox |
| 3 | Softsqueeze |
| 4 | Squeezebox2 |
| 5 | Transporter |
| 6 | Softsqueeze3 |
| 7 | Receiver |
| 8 | Squeezeslave |
| 9 | Controller |
| 10 | Boom |
| 11 | Softboom |
| 12 | Squeezeplay |

#### Capabilities Extension (LMS 7.4+)

The basic HELO packet can be augmented by a comma-separated list of capabilities:

**CODECs** (lowercase, in order of preference):
- `wma`, `wmap` (WMAPro), `wmal` (WMA Lossless)
- `ogg`, `flc`, `pcm`, `aif`, `mp3`
- `alc` (Apple Lossless), `aac` (AAC & HE-AAC)

**Other capabilities** (case sensitive):
- `MaxSampleRate=96000` - max sample rate in frames/s
- `Model=controller` - device model
- `ModelName=Controller` - human-readable model name
- `AccuratePlayPoints` - precise playpoints for sync
- `SyncgroupID=nnnnnnnnnn` - sync-group to join
- `HasDigitalOut`, `HasPreAmp`, `HasDisableDac`

### STAT Message

Sent by the player in response to commands and periodically as keep-alive.

| Size | Field |
|------|-------|
| u32 | Event Code (4 byte string) |
| u8 | Number of consecutive CRLF received |
| u8 | MAS Initialized - 'm' or 'p' |
| u8 | MAS Mode |
| u32 | Buffer size (bytes) |
| u32 | Buffer fullness (bytes) |
| u64 | Bytes Received |
| u16 | Wireless Signal Strength (0-100) |
| u32 | Jiffies - timestamp @1kHz |
| u32 | Output buffer size |
| u32 | Output buffer fullness |
| u32 | Elapsed seconds |
| u16 | Voltage |
| u32 | Elapsed milliseconds |
| u32 | Server timestamp (reflected from strm-t) |
| u16 | Error code (used with STMn) |

#### STAT Event Codes

| EventCode | Description | Notes |
|-----------|-------------|-------|
| vfdc | VFD received | Ack to display message |
| i2cc | I2C confirmation | |
| STMa | Autostart | Track started (SB v1 only) |
| STMc | Connect | Response to strm-s, guaranteed first |
| STMd | Decoder ready | Ready for next track |
| STMe | Stream connection Established | |
| STMf | Connection flushed | Response to strm-f or strm-q |
| STMh | HTTP headers received | From streaming connection |
| STMl | Buffer threshold reached | When autostart=0/2 |
| STMn | Not Supported | Decoder error or unsupported format |
| STMo | Output Underrun | No decoded data; triggers rebuffering |
| STMp | Pause | Confirmation of pause |
| STMr | Resume | Confirmation of resume |
| STMs | Track Started | Playback of new track started |
| STMt | Timer | Heartbeat, periodic or response to strm-t |
| STMu | Underrun | **Normal end of playback** |

### Server → Client Communication

Data format: 2 bytes length (network order) + 4 byte command + data.
Length = size of data + 4 byte command header.

### Command: "strm"

24 bytes data:

| Field | Length | Notes |
|-------|--------|-------|
| command | 1 byte | 's'=start, 'p'=pause, 'u'=unpause, 'q'=stop, 't'=status, 'f'=flush, 'a'=skip-ahead |
| autostart | 1 byte | '0'=don't auto-start, '1'=auto-start, '2'=direct streaming, '3'=direct+auto |
| formatbyte | 1 byte | 'p'=PCM, 'm'=MP3, 'f'=FLAC, 'w'=WMA, 'o'=Ogg, 'a'=AAC, 'l'=ALAC |
| pcmsamplesize | 1 byte | '0'=8, '1'=16, '2'=20, '3'=32; '?' for self-describing |
| pcmsamplerate | 1 byte | '0'=11kHz, '1'=22kHz, '2'=32kHz, '3'=44.1kHz, '4'=48kHz, '5'=8kHz, '6'=12kHz, '7'=16kHz, '8'=24kHz, '9'=96kHz |
| pcmchannels | 1 byte | '1'=mono, '2'=stereo |
| pcmendian | 1 byte | '0'=big, '1'=little |
| threshold | 1 byte | KB of input buffer before autostart/notify |
| spdif_enable | 1 byte | '0'=auto, '1'=on, '2'=off |
| trans_period | 1 byte | Transition duration (seconds) |
| trans_type | 1 byte | '0'=none, '1'=crossfade, '2'=fade in, '3'=fade out, '4'=fade in & out |
| flags | 1 byte | 0x80=loop, 0x40=stream without restart, 0x01/0x02=polarity inversion |
| output_threshold | 1 byte | Output buffer data before playback (tenths of second) |
| RESERVED | 1 byte | |
| replay_gain | 4 bytes | 16.16 fixed point, 0=none |
| server_port | 2 bytes | Server port (default 9000) |
| server_ip | 4 bytes | 0 = use control server IP |

Followed by HTTP header for stream request.

#### Special uses of replay_gain field

- **u** (unpause): if non-zero, timestamp (ms) at which to unpause (for sync)
- **p** (pause): if non-zero, interval (ms) to pause then auto-resume
- **a** (skip-ahead): if non-zero, interval (ms) to skip over
- **t** (status): timestamp to be returned in STMt response (for latency measurement)

### Command: "aude"

Enable/disable audio outputs. 2 bytes:

| Field | Length | Notes |
|-------|--------|-------|
| spdif_enable | 1 byte | 0x0=disable, 0x1=enable SPDIF |
| dac_enable | 1 byte | 0x0=disable, 0x1=enable DAC |

### Command: "audg"

Adjust audio gain (volume). 18-22 bytes:

| Field | Length | Notes |
|-------|--------|-------|
| old_left | 4 bytes | unsigned int (0..128) |
| old_right | 4 bytes | unsigned int (0..128) |
| dvc | 1 byte | Digital volume control 0/1 |
| preamp | 1 byte | Preamp (255-0) |
| new_left | 4 bytes | 16.16 fixed point |
| new_right | 4 bytes | 16.16 fixed point |
| sequence | 4 bytes | unsigned int, optional |

### Command: "grfb"

Adjust display brightness. 2 bytes (short int, network order):
- Range: -1 to 5
- -1 = totally off
- 5 = brightest

### Command: "grfe"

Send bitmap to display. Header (4 bytes) + 1280 bytes data:

| Field | Length | Notes |
|-------|--------|-------|
| offset | 2 bytes | short int |
| transition | 1 byte | 'L','R','U','D' (uppercase=bounce, lowercase=scroll) |
| param | 1 byte | pixels in animation |

Data: 1280 bytes for Squeezebox3 (320x32 display, 4 bytes per column).
Bits are laid out top-to-bottom in each column.

Compressed graphics: set highest byte of 'grfe' command; data is LZF compressed.

### Command: "vers"

Send server version string to client. Data is human-readable version string.

### Command: "serv"

Tell client to switch to another server:

| Field | Length | Notes |
|-------|--------|-------|
| ip_address | 4 bytes | network order; 0x1 = switch to SqueezeNetwork |
| syncgroupid | 10 bytes | optional, ASCII digits for sync-group |

### Command: "setd"

Get/set player firmware settings.

### Command: "vfdc"

Send VFD data to client (same format as SLIMP3 protocol).

### Other Commands

| Command | Description |
|---------|-------------|
| audc | Transporter: update clock source |
| audp | Transporter: update audio source |
| body | Request file body from player |
| cont | Content-type related |
| grfd | SqueezeboxG: draw graphics |
| irtm | Send IR timing info |
| knob | Transporter: knob-related |
| visu | Activate/deactivate visualizer |

---

## SLIMP3 Protocol

The SLIMP3 protocol is UDP-based, designed to be extremely lightweight.

All packets have an 18-byte header. First byte indicates packet type.
- Server listens on **port 1069**
- All numbers are unsigned integers in network order
- Last 6 bytes of Client→Server messages are the client's MAC address

### Server → Client

#### 'D' - Discovery Response

| Field | Description |
|-------|-------------|
| 0 | 'D' |
| 1 | reserved |
| 2..5 | server's IP address (or 0.0.0.0) |
| 6..7 | server's port |
| 8..17 | reserved |

#### 'h' - Hello

| Field | Description |
|-------|-------------|
| 0 | 'h' |
| 1..17 | reserved |

Used to check if clients are up and get firmware revision.

#### 'l' - LCD/VFD Display Data

| Field | Description |
|-------|-------------|
| 0 | 'l' |
| 1..17 | reserved |
| 18... | variable length string of 16-bit codes |

16-bit codes:
- `00XX` - delay in ms (up to 255)
- `02XX` - command
- `03XX` - character (0-255)

#### 'm' - MPEG Data

| Field | Description |
|-------|-------------|
| 0 | 'm' |
| 1 | control signal (0=decoding, 1=stopped, 3=stopped+reset) |
| 2..5 | reserved |
| 6..7 | write pointer |
| 8..9 | reserved |
| 10..11 | sequence number |
| 12..17 | reserved |
| 18.. | data (even number of bytes) |

### Client → Server

#### 'd' - Discovery Request

| Field | Description |
|-------|-------------|
| 0 | 'd' |
| 1 | reserved |
| 2 | Device ID ('1' for SLIMP3) |
| 3 | Firmware rev |
| 4..11 | reserved |
| 12..17 | MAC address |

Sent to broadcast address on port 1069.

#### 'h' - Hello

| Field | Description |
|-------|-------------|
| 0 | 'h' |
| 1 | Device ID |
| 2 | Firmware rev |
| 3..11 | reserved |
| 12..17 | MAC address |

#### 'i' - IR Code

| Field | Description |
|-------|-------------|
| 0 | 'i' |
| 1 | 0x00 |
| 2..5 | time since startup @625kHz |
| 6 | 0xFF |
| 7 | number of bits (16 for JVC) |
| 8..11 | 32-bit IR code |
| 12..17 | MAC address |

#### 'a' - ACK Response

| Field | Description |
|-------|-------------|
| 0 | 'a' |
| 1..5 | reserved |
| 6..7 | write pointer |
| 8..9 | read pointer |
| 10..11 | sequence number |
| 12..17 | MAC address |

---

## IP3K Graphics

This covers bitmap files for fonts on legacy players (Classic/Transporter/Boom).
**Does NOT cover** colour display devices (Radio/Touch/Controller).

Font files reside in the `Graphics` folder.

### File Naming

- `<mode>.<line>.font.bmp`
- Example: `medium.1.font.bmp` (top line), `medium.2.font.bmp` (bottom line)
- Single-line modes (Huge font) only need the bottom font file

### File Format

- SqueezeboxG: 17 pixels high
- Squeezebox2/3/Classic/Boom/Transporter: 33 pixels high
- First 16/32 rows: font bitmaps
- Last row: character boundary markers

### Character Set

- 256 characters using latin1 character set (0-255)
- First 31 characters: reserved for special graphics
- Character 32: space
- Characters 33-255: standard latin1

#### Special Characters (0-16)

| Index | Symbol |
|-------|--------|
| 0 | Inter-character spacing |
| 1 | Note symbol |
| 2 | Right arrow |
| 3 | Progress indicator end |
| 4-6 | Progress indicator (empty) |
| 7-9 | Progress indicator (full) |
| 10 | Cursor overlay |
| 11 | Moodlogic symbol |
| 12-13 | Radio button (empty/full circle) |
| 14-15 | Checkbox (empty/full square) |
| 16 | Bell symbol |

### Custom Fonts

Plugins can define custom fonts:
- Naming: `<fontname>.<line_number>.font.bmp`
- Place in plugin's root directory
- Restart server after adding
- Register characters with `Slim::Display::Graphics::setCustomChar`

Reserved characters: 0x0a (chr 10), 0x1b-0x1d (chr 27-29)

---

## Home Menu vs SlimBrowse Items

### Two Types of Items from LMS to SqueezePlay

1. **Home Menu Items** - delivered as individual items
2. **SlimBrowse Items** - delivered as full menus

### Home Menu Items

Managed by `jive.ui.HomeMenu` class.

- Includes top-level items AND miscellaneous nodes below
- Each item requires:
  - Unique **ID** for management
  - **node** - where to place the item
- Current nodes: `home`, `settings`, `advanced`, `myMusic`, `hidden`
- Can be customized via CustomizeHomeMenu applet
- Registered via `Slim::Control::Jive::registerPluginMenu`

Examples:
- Home → Music Library → Genres
- Home → Settings → Screen → Wallpaper
- Home → Internet Radio

### SlimBrowse Items

Menus delivered via specific CLI command.

- NOT available for customizing into top level menu
- Used for drill-down menus

Examples:
- Home → Music Library → Artists → [specific artist] → ...
- Home → Music Library → Genres → Acid Jazz → ...

### Hidden Node

Items in `node=hidden` are not displayed by default but can be added to top level menu.
Used for Internet Radio and Music Services items (Pandora, Rhapsody, etc.).

---

## Adding Menus on SqueezePlay

### Adding a Node

Use `Slim::Control::Jive::registerPluginNode()`:

```perl
my $node = {
    text           => 'Foobar',
    weight         => 100,
    id             => 'pluginFoobarMenu',
    node           => 'settings',
    homeMenuText   => 'Foobar Settings',  # optional
    window         => { titleStyle => 'settings' },
};
Slim::Control::Jive::registerPluginNode($node, $client);
```

- `weight` - ordering within menu (default 5), same weight = alphabetical
- `window` - parameters for opened window
- `noCustom` - disallow user adding to top level
- `$client` - optional, for player-specific nodes

### Adding Menu Items

Use `Slim::Control::Jive::registerPluginMenu()`:

```perl
my @menu = ({
    text    => Slim::Utils::Strings::string('SOME_STRING'),
    id      => 'pluginFoobarTweakSomething',
    weight  => 10,
    actions => {
        do => {
            player => 0,
            cmd    => [ 'someCustomPluginCommand', 'someArgument' ],
            params => { state => 'tweaked' },
        }
    },
});
Slim::Control::Jive::registerPluginMenu(\@menu, 'settings', $client);
```

### Refreshing Menus

```perl
# Refresh plugin menu items
Slim::Control::Jive::refreshPluginMenus($client);

# Refresh entire main menu
Slim::Control::Jive::mainMenu($client);

# Refresh settings menu
Slim::Control::Jive::playerSettingsMenu($client);

# Refresh player power menu item only
Slim::Control::Jive::playerPower($client);

# Refresh Music Library node
Slim::Control::Jive::myMusicMenu($client);

# Refresh search node only
Slim::Control::Jive::searchMenu($client);
```

---

## Database Structure

LMS uses SQLite (MySQL/MariaDB possible but unsupported).

### Database Files

| File | Description |
|------|-------------|
| library.db | Main library database |
| persist.db | Persistent data (survives rescans) |
| artwork.db, cached.db, imgproxy.db | Cache databases (key/value stores) |

### Main Tables (library.db)

#### albums

All albums plus special "No Album" entry for tracks without album.

#### contributors

All composers, conductors, artists, album artists, bands, track artists.
Includes special "Various Artists" entry for compilation albums.

#### tracks

- All tracks (`audio=1`, `remote=0`)
- Internet radio stations (`remote=1`)
- Directories (`audio=0`, `content_type='dir'`)
- Playlists (`audio=0`, `content_type`=playlist type)
- Current playlist (`content_type='cpl'`)

**Key columns:**
- `title`, `titlesort` - track title and sort version
- `url` - URL-encoded path (e.g., `file:///mnt/music/...`)
- `audio` - 1=music file, null=not music
- `content_type` - file format or playlist format
- `tracknum`, `disc` - track and disc number
- `timestamp`, `filesize` - file metadata
- `year`, `secs`, `bitrate`, `samplerate`, `samplesize`, `channels`
- `bpm`, `lyrics` - optional metadata
- `remote`, `lossless` - flags
- `album` - relation to albums table

#### tracks_persistent

Statistics: play count, rating, last played time.
Survives rescans if musicbrainz tags present or file not moved.

#### works, genres, years, comments

Additional metadata tables.

### Many-to-Many Associations

#### contributor_track

| Column | Description |
|--------|-------------|
| contributor | → contributors.id |
| track | → tracks.id |
| role | 1=Artist, 2=Composer, 3=Conductor, 4=Band, 5=Album artist, 6=Track artist |

#### contributor_album

Summary view for artist→album browsing (shortcut for performance).

#### genre_track

Links genres to tracks.

#### playlist_track

Links playlists to tracks.
- `playlist_track.playlist` → `tracks.id`
- `playlist_track.track` → `tracks.url`

### Many-to-One Associations

- `tracks.album` → `albums.id`
- `albums.year` → `years.id`
- `tracks.year` → `years.id`
- `comments.track` → `tracks.id`
- `albums.contributor` → `contributors.id` (main artist)

### Meta Tables

- `metainformation` - database meta (last rescan, scanning status)
- `dbix_migration` - database schema version
- `progress` - scanning progress

### Sample Queries

**Get all artists with tracks:**
```sql
SELECT contributors.* FROM contributors, contributor_album
WHERE contributors.id = contributor_album.contributor
GROUP BY contributors.id
ORDER BY contributors.namesort
```

**Get artists (excluding Various Artists):**
```sql
SELECT contributors.* FROM contributors, contributor_album
WHERE contributors.id = contributor_album.contributor
  AND contributor_album.role IN (1, 5, 6)
GROUP BY contributors.id
ORDER BY contributors.namesort
```

**Get albums with tracks:**
```sql
SELECT albums.* FROM albums, tracks
WHERE tracks.album = albums.id
  AND tracks.audio = 1
GROUP BY albums.id
ORDER BY albums.titlesort
```

**Get tracks ordered by album:**
```sql
SELECT tracks.* FROM tracks, albums
WHERE tracks.album = albums.id
  AND tracks.audio = 1
GROUP BY tracks.id
ORDER BY albums.titlesort, tracks.disc, tracks.tracknum
```

---

## Key Insights for Resonance Implementation

### Connection Sequence

1. **Discovery** (UDP 3483) - Player broadcasts, server responds with IP/port
2. **Slimproto** (TCP 3483) - Player connects, sends HELO, receives server commands
3. **HTTP/Cometd** (TCP 9000) - Touch-UI connects for menus and real-time updates

### Important STM Events

| Event | Action |
|-------|--------|
| STMs | Track started → PLAYING |
| STMp | Pause confirmed → PAUSED |
| STMr | Resume confirmed → PLAYING |
| STMf | Flush confirmed → no state change |
| STMd | Decoder ready → no auto-advance! |
| STMu | Underrun → STOPPED + track finished (triggers next track) |

### Device-Specific Notes

- **Touch-UI devices** (Radio, Touch, Boom, Controller): Need HTTP/Cometd for UI
- **Legacy devices** (SB2/3, Classic, Transporter): Use Slimproto for everything including display (grfe/grfb)
- **Software players** (Squeezelite): Slimproto only, no UI

### Port Summary

| Port | Protocol | Purpose |
|------|----------|---------|
| 3483 UDP | Discovery | Player finds server |
| 3483 TCP | Slimproto | Player control, audio streaming commands |
| 9000 TCP | HTTP | Audio streaming, Cometd, JSON-RPC, Web UI |