import json
import sys
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:9000"


def get_json(path):
    url = f"{BASE_URL}{path}"
    print(f"GET {url}")
    try:
        with urllib.request.urlopen(url) as response:
            data = response.read()
            return json.loads(data)
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        return None
    except Exception as e:
        print(f"Request failed: {e}")
        return None


def post_json_rpc(method, params):
    url = f"{BASE_URL}/jsonrpc"
    payload = {"id": 1, "method": method, "params": params}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    print(f"POST {url} - {method} {params}")
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        try:
            err_body = e.read()
            print(f"Body: {err_body.decode('utf-8')}")
        except:
            pass
        return None
    except Exception as e:
        print(f"Request failed: {e}")
        return None


def main():
    print(f"Checking Resonance API at {BASE_URL}...\n")

    # 1. Health Check
    health = get_json("/health")
    if health:
        print(f"Health Check: OK ({health})\n")
    else:
        print("Health Check: FAILED. Is the server running?\n")
        return

    # 2. Server Status (JSON-RPC)
    print("--- Server Status (JSON-RPC) ---")
    status = post_json_rpc("slim.request", ["-", ["serverstatus"]])
    if status and "result" in status:
        res = status["result"]
        print(f"Version: {res.get('version')}")
        print(f"Total Tracks: {res.get('info total tracks')}")
        print(f"Total Albums: {res.get('info total albums')}")
        print(f"Total Artists: {res.get('info total artists')}")
        print(f"Scan Status: {res.get('lastscan')}")
    else:
        print("Failed to get server status.")
    print("")

    # 3. List Albums via REST
    print("--- REST API: /api/library/albums (First 5) ---")
    albums = get_json("/api/library/albums?limit=5")
    if albums and "albums" in albums:
        count = albums.get("count", 0)
        print(f"Total Albums (via REST): {count}")
        for album in albums["albums"]:
            print(
                f"  [{album.get('id')}] {album.get('album')} - {album.get('artist')} (Tracks: {album.get('tracks')})"
            )
    else:
        print("No albums found via REST.")
    print("")

    # 3b. Check Music Folders
    print("--- Music Folders (JSON-RPC) ---")
    pref = post_json_rpc("slim.request", ["-", ["pref", "mediadirs", "?"]])
    if pref and "result" in pref:
        print(f"Music Folders: {pref['result'].get('_p2')}")
    else:
        print("Failed to get music folders.")
    print("")

    # Trigger Rescan
    print("--- Triggering Rescan (JSON-RPC) ---")
    rescan = post_json_rpc("slim.request", ["-", ["rescan"]])
    if rescan and "result" in rescan:
        print("Rescan triggered successfully.")
    else:
        print("Failed to trigger rescan.")
    print("")

    # 3c. List Tracks via REST
    print("--- REST API: /api/library/tracks (First 5) ---")
    tracks = get_json("/api/library/tracks?limit=5")
    if tracks and "tracks" in tracks:
        count = tracks.get("count", 0)
        print(f"Total Tracks (via REST): {count}")
        for track in tracks["tracks"]:
            print(
                f"  [{track.get('id')}] {track.get('title')} - {track.get('artist')} ({track.get('album')})"
            )
    else:
        print("No tracks found via REST.")
    print("")

    # 4. List Albums via JSON-RPC (with tags for artwork)
    print("--- JSON-RPC: albums (First 5, tags:jla) ---")
    # tags: j=artwork, l=album, a=artist
    rpc_albums = post_json_rpc("slim.request", ["-", ["albums", 0, 5, "tags:jla"]])

    target_album_id = None

    if rpc_albums and "result" in rpc_albums:
        result = rpc_albums["result"]
        loop = result.get("albums_loop", [])
        print(f"Albums returned: {len(loop)}")

        for album in loop:
            aid = album.get("id")
            title = album.get("album")
            art_url = album.get("artwork_url")
            art_track = album.get("artwork_track_id")

            print(f"  [{aid}] {title}")
            print(f"      Artwork URL: {art_url}")
            print(f"      Artwork Track ID: {art_track}")

            if not target_album_id:
                target_album_id = aid
    else:
        print("No albums found via JSON-RPC.")
    print("")

    # 5. Check Artwork Endpoint
    if target_album_id:
        print(f"--- Checking Artwork URL for Album {target_album_id} ---")
        # Try REST endpoint
        url = f"{BASE_URL}/api/artwork/album/{target_album_id}"
        print(f"Requesting: {url}")
        try:
            with urllib.request.urlopen(url) as response:
                print(f"Response Status: {response.status}")
                print(f"Content-Type: {response.headers.get('Content-Type')}")
                print(f"Content-Length: {response.headers.get('Content-Length')}")
                print("Download successful.")
        except urllib.error.HTTPError as e:
            print(f"Failed to fetch artwork: HTTP {e.code}")
        except Exception as e:
            print(f"Failed to fetch artwork: {e}")

        # Try BlurHash endpoint
        url_bh = f"{BASE_URL}/api/artwork/album/{target_album_id}/blurhash"
        print(f"\nRequesting BlurHash: {url_bh}")
        try:
            with urllib.request.urlopen(url_bh) as response:
                data = json.loads(response.read())
                print(f"Response: {data}")
        except Exception as e:
            print(f"Failed to fetch blurhash: {e}")


if __name__ == "__main__":
    main()
