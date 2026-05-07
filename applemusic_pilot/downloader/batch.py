from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import List

from applemusic_pilot.downloader.amd_bridge import AMDBridge
from applemusic_pilot.downloader.convert import convert_to_wav, ConvertError
from applemusic_pilot.downloader.models import DownloadResult, PairTask
from applemusic_pilot.downloader.organizer import organize_pair
from applemusic_pilot.downloader.report import Reporter


def parse_pairs(text: str) -> List[PairTask]:
    urls = [line.strip() for line in text.splitlines() if line.strip()]
    if len(urls) % 2 != 0:
        raise ValueError(f"URL list has odd number of entries ({len(urls)}); expected pairs")
    pairs = []
    for i, (origin, cover) in enumerate(zip(urls[::2], urls[1::2]), start=1):
        pairs.append(PairTask(idx=i, origin_url=origin, cover_url=cover))
    return pairs


def _download_one(bridge: AMDBridge, url: str, role: str, tmp_dir: Path) -> DownloadResult:
    try:
        m4a_path, meta = bridge.download_song(url, tmp_dir)
        wav_path = m4a_path.with_suffix(".wav")
        convert_to_wav(m4a_path, wav_path)
        result = DownloadResult(
            url=url,
            role=role,
            success=True,
            m4a_path=m4a_path,
            song_id=meta.get("song_id"),
            song_name=meta.get("song_name"),
            artist_name=meta.get("artist_name"),
            meta=meta,
        )
        result._wav_path = wav_path
        return result
    except Exception as exc:
        return DownloadResult(url=url, role=role, success=False, error=str(exc))


def run_batch(pairs: List[PairTask], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    reporter = Reporter(total_pairs=len(pairs))
    bridge = AMDBridge()
    bridge.start()

    try:
        for pair in pairs:
            print(f"[{pair.idx}/{len(pairs)}] Downloading pair #{pair.idx}...")
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                origin = _download_one(bridge, pair.origin_url, "origin", tmp_path / "origin")
                cover = _download_one(bridge, pair.cover_url, "cover", tmp_path / "cover")

            if origin.success and cover.success:
                organize_pair(origin, cover, output_dir)
                reporter.record_success(pair.idx)
                print(f"  OK pair #{pair.idx}: {origin.song_name}")
            else:
                if not origin.success:
                    reporter.record_failure(pair.idx, "origin", pair.origin_url, origin.error or "unknown")
                    print(f"  FAIL pair #{pair.idx} origin: {origin.error}")
                if not cover.success:
                    reporter.record_failure(pair.idx, "cover", pair.cover_url, cover.error or "unknown")
                    print(f"  FAIL pair #{pair.idx} cover: {cover.error}")
    finally:
        bridge.close()

    report_path = output_dir / "异常信息.txt"
    reporter.write(report_path)
    print(f"\n完成。异常报告: {report_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch download Apple Music lossless pairs")
    parser.add_argument("list_file", type=Path, help="URL list file (two lines per pair)")
    parser.add_argument("--output-dir", type=Path, default=Path("output"), help="Output directory")
    args = parser.parse_args()

    text = args.list_file.read_text(encoding="utf-8")
    pairs = parse_pairs(text)
    print(f"Loaded {len(pairs)} pairs from {args.list_file}")
    run_batch(pairs, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
