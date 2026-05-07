from __future__ import annotations
import sys, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from applemusic_pilot.downloader.convert import convert_to_wav, ConvertError


def test_convert_missing_file(tmp_path):
    with pytest.raises(ConvertError, match="does not exist"):
        convert_to_wav(tmp_path / "nonexistent.m4a", tmp_path / "out.wav")


def test_convert_success(tmp_path):
    src = tmp_path / "silence.m4a"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
         "-t", "1", "-c:a", "aac", str(src)],
        check=True, capture_output=True,
    )
    dst = tmp_path / "silence.wav"
    convert_to_wav(src, dst)
    assert dst.exists()
    assert dst.stat().st_size > 0
