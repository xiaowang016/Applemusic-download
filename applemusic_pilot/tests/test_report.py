from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from applemusic_pilot.downloader.report import Reporter


def test_report_all_success(tmp_path):
    r = Reporter(total_pairs=3)
    r.record_success(1)
    r.record_success(2)
    r.record_success(3)
    out = tmp_path / "异常信息.txt"
    r.write(out)
    text = out.read_text(encoding="utf-8")
    assert "总计: 3 对" in text
    assert "成功: 3" in text
    assert "失败: 0" in text


def test_report_with_failures(tmp_path):
    r = Reporter(total_pairs=3)
    r.record_success(1)
    r.record_failure(2, "origin", "https://music.apple.com/x?i=111", "Song not found")
    r.record_failure(3, "cover", "https://music.apple.com/x?i=222", "ffmpeg failed")
    out = tmp_path / "异常信息.txt"
    r.write(out)
    text = out.read_text(encoding="utf-8")
    assert "失败: 2" in text
    assert "pair #2" in text
    assert "Song not found" in text
    assert "pair #3" in text
    assert "ffmpeg failed" in text
