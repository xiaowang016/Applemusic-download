from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from applemusic_pilot.downloader.batch import parse_pairs


def test_parse_two_pairs():
    text = """
https://music.apple.com/us/album/a/1?i=111
https://music.apple.com/us/album/b/2?i=222

https://music.apple.com/us/album/c/3?i=333
https://music.apple.com/us/album/d/4?i=444
"""
    pairs = parse_pairs(text)
    assert len(pairs) == 2
    assert pairs[0].idx == 1
    assert pairs[0].origin_url == "https://music.apple.com/us/album/a/1?i=111"
    assert pairs[0].cover_url == "https://music.apple.com/us/album/b/2?i=222"
    assert pairs[1].idx == 2
    assert pairs[1].origin_url == "https://music.apple.com/us/album/c/3?i=333"


def test_parse_ignores_blank_lines():
    text = "\nhttps://a.com/1\n\nhttps://a.com/2\n\n\n"
    pairs = parse_pairs(text)
    assert len(pairs) == 1


def test_parse_odd_number_raises():
    text = "https://a.com/1\nhttps://a.com/2\nhttps://a.com/3\n"
    import pytest
    with pytest.raises(ValueError, match="odd"):
        parse_pairs(text)
