from __future__ import annotations
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from applemusic_pilot.downloader.models import DownloadResult
from applemusic_pilot.downloader.organizer import organize_pair


def test_organize_pair(tmp_path):
    origin_wav = tmp_path / "origin.wav"
    cover_wav = tmp_path / "cover.wav"
    origin_wav.write_bytes(b"RIFF")
    cover_wav.write_bytes(b"RIFF")

    origin = DownloadResult(
        url="https://music.apple.com/ca/album/circles/1477886950?i=1477887285",
        role="origin",
        success=True,
        m4a_path=tmp_path / "origin.m4a",
        song_id="1477887285",
        song_name="Circles",
        artist_name="Post Malone",
        meta={"song_id": "1477887285", "song_name": "Circles", "artist_name": "Post Malone",
              "original_url": "https://music.apple.com/ca/album/circles/1477886950?i=1477887285"},
    )
    origin._wav_path = origin_wav

    cover = DownloadResult(
        url="https://music.apple.com/ca/album/circles-cover/1756821964?i=1756821965",
        role="cover",
        success=True,
        m4a_path=tmp_path / "cover.m4a",
        song_id="1756821965",
        song_name="Circles (Cover)",
        artist_name="2 Souls & Layzee Gold",
        meta={"song_id": "1756821965", "song_name": "Circles (Cover)", "artist_name": "2 Souls & Layzee Gold",
              "original_url": "https://music.apple.com/ca/album/circles-cover/1756821964?i=1756821965"},
    )
    cover._wav_path = cover_wav

    output_dir = tmp_path / "output"
    organize_pair(origin, cover, output_dir)

    folder = output_dir / "Circles"
    assert folder.is_dir()
    assert (folder / "original_1477887285.wav").exists()
    assert (folder / "cover_1756821965.wav").exists()

    origin_meta = json.loads((folder / "1477887285.json").read_text())
    assert origin_meta["song_id"] == "1477887285"

    cover_meta = json.loads((folder / "1756821965.json").read_text())
    assert cover_meta["song_id"] == "1756821965"
