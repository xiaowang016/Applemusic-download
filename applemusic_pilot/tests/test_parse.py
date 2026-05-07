from __future__ import annotations

import sys
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from applemusic_pilot.parse import (
    extract_artist_name,
    extract_song_id_from_url,
    extract_song_name,
    infer_song_id,
    parse_song_page,
)


class ParseTests(unittest.TestCase):
    def test_extract_song_id_from_url(self) -> None:
        self.assertEqual(
            extract_song_id_from_url(
                "https://music.apple.com/ca/album/closer-feat-halsey/1136768287?i=1136768508"
            ),
            "1136768508",
        )

    def test_extract_artist_name_from_song_description(self) -> None:
        body = """
        <meta
            name="description"
            content="Listen to Closer (feat. Halsey) by The Chainsmokers on Apple Music. 2016. Duration: 4:04"
        >
        """
        self.assertEqual(extract_artist_name(body), "The Chainsmokers")

    def test_extract_artist_name_from_album_description(self) -> None:
        body = """
        <meta
            name="description"
            content="Listen to Blinding Lights - Single by Loi on Apple Music. 2021. 1 Song. Duration: 2 minutes."
        >
        """
        self.assertEqual(extract_artist_name(body), "Loi")

    def test_extract_song_name_from_song_meta_title(self) -> None:
        body = """
        <meta name="apple:title" content="Closer (feat. Halsey)">
        """
        self.assertEqual(
            extract_song_name(
                body,
                song_id="1136768508",
                prefer_track_context=False,
            ),
            "Closer (feat. Halsey)",
        )

    def test_extract_song_name_from_single_track_album_body(self) -> None:
        body = """
        <html><body>
        {"items":[{"id":"track-lockup - 1584826306 - 1584826307","title":"Blinding Lights","contentDescriptor":{"kind":"song","identifiers":{"storeAdamID":"1584826307"}}}]}
        </body></html>
        """
        self.assertEqual(
            extract_song_name(
                body,
                song_id="1584826307",
                prefer_track_context=True,
            ),
            "Blinding Lights",
        )

    def test_infer_song_id_from_single_track_album_page(self) -> None:
        body = """
        <html><body>
        <a href="https://music.apple.com/ca/album/blinding-lights-single/1584826306?i=1584826307">song</a>
        <link rel="alternate" href="https://music.apple.com/api/oembed?url=https%3A%2F%2Fmusic.apple.com%2Fca%2Falbum%2Fblinding-lights-single%2F1584826306">
        </body></html>
        """
        self.assertEqual(
            infer_song_id(
                "https://music.apple.com/ca/album/blinding-lights-single/1584826306",
                body,
            ),
            "1584826307",
        )

    def test_infer_song_id_rejects_multi_track_album_pages(self) -> None:
        body = """
        <html><body>
        <a href="/ca/album/example/123?i=1">track 1</a>
        <a href="/ca/album/example/123?i=2">track 2</a>
        </body></html>
        """
        with self.assertRaises(ValueError):
            infer_song_id("https://music.apple.com/ca/album/example/123", body)

    def test_parse_song_page(self) -> None:
        body = """
        <html>
          <head>
            <title>‎Closer (feat. Halsey) – Song by The Chainsmokers – Apple Music</title>
            <meta
              name="description"
              content="Listen to Closer (feat. Halsey) by The Chainsmokers on Apple Music. 2016. Duration: 4:04"
            >
          </head>
        </html>
        """
        record = parse_song_page(
            body,
            "https://music.apple.com/ca/album/closer-feat-halsey/1136768287?i=1136768508",
        )
        self.assertEqual(record.song_id, "1136768508")
        self.assertEqual(record.song_name, "Closer (feat. Halsey)")
        self.assertEqual(record.artist_name, "The Chainsmokers")
        self.assertEqual(
            record.original_url,
            "https://music.apple.com/ca/album/closer-feat-halsey/1136768287?i=1136768508",
        )


if __name__ == "__main__":
    unittest.main()
