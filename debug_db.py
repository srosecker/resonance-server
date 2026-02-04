import os
import sqlite3
from pathlib import Path

DB_PATH = Path("resonance-library.sqlite3")


def check_db():
    if not DB_PATH.exists():
        print(f"ERROR: Database file not found at {DB_PATH.absolute()}")
        return

    print(f"Opening database: {DB_PATH.absolute()}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # 1. General Stats
        print("\n=== General Stats ===")
        cursor.execute("SELECT COUNT(*) FROM tracks")
        total_tracks = cursor.fetchone()[0]
        print(f"Total Tracks: {total_tracks}")

        cursor.execute("SELECT COUNT(*) FROM tracks WHERE has_artwork = 1")
        tracks_with_art = cursor.fetchone()[0]
        print(f"Tracks with 'has_artwork=1': {tracks_with_art}")

        cursor.execute("SELECT COUNT(*) FROM albums")
        total_albums = cursor.fetchone()[0]
        print(f"Total Albums: {total_albums}")

        # 2. Inspect Tracks Sample
        print("\n=== Track Sample (First 5) ===")
        cursor.execute("SELECT id, path, album, album_id, has_artwork FROM tracks LIMIT 5")
        rows = cursor.fetchall()
        for row in rows:
            print(f"ID: {row['id']}, Path: {row['path']}")
            print(
                f"  -> Album: '{row['album']}', Album ID: {row['album_id']}, Has Art: {row['has_artwork']}"
            )

        # 3. Inspect Album Sample
        print("\n=== Album Sample (First 5) ===")
        cursor.execute("SELECT id, title, artist_id FROM albums LIMIT 5")
        rows = cursor.fetchall()
        for row in rows:
            print(f"ID: {row['id']}, Title: '{row['title']}', Artist ID: {row['artist_id']}")

        # 4. Check for Orphans (Tracks with Album string but no Album ID)
        print("\n=== Orphans Check ===")
        cursor.execute(
            "SELECT COUNT(*) FROM tracks WHERE album IS NOT NULL AND album != '' AND album_id IS NULL"
        )
        orphans = cursor.fetchone()[0]
        print(f"Tracks with album name but no album_id: {orphans}")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    check_db()
