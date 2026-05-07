from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from applemusic_pilot.downloader.models import PairTask, DownloadResult


def test_pair_task_fields():
    task = PairTask(
        idx=1,
        origin_url="https://music.apple.com/us/album/x/1?i=111",
        cover_url="https://music.apple.com/us/album/x/1?i=222",
    )
    assert task.idx == 1
    assert task.origin_url == "https://music.apple.com/us/album/x/1?i=111"
    assert task.cover_url == "https://music.apple.com/us/album/x/1?i=222"


def test_download_result_success():
    result = DownloadResult(
        url="https://music.apple.com/us/album/x/1?i=111",
        role="origin",
        success=True,
        m4a_path=Path("/tmp/song.m4a"),
        song_id="111",
        song_name="Time of Dying",
        artist_name="Three Days Grace",
        meta={},
    )
    assert result.success is True
    assert result.error is None


def test_download_result_failure():
    result = DownloadResult(
        url="https://music.apple.com/us/album/x/1?i=999",
        role="cover",
        success=False,
        error="Song not found on Apple Music",
    )
    assert result.success is False
    assert result.m4a_path is None
