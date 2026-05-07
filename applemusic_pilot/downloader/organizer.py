from __future__ import annotations
import json
import shutil
from pathlib import Path

from applemusic_pilot.downloader.models import DownloadResult


def organize_pair(origin: DownloadResult, cover: DownloadResult, output_dir: Path) -> Path:
    folder_name = _safe_dirname(origin.song_name or f"unknown_{origin.song_id}")
    folder = output_dir / folder_name
    folder.mkdir(parents=True, exist_ok=True)

    _place_wav(origin, folder, "original")
    _place_wav(cover, folder, "cover")
    _write_meta(origin, folder)
    _write_meta(cover, folder)

    return folder


def _place_wav(result: DownloadResult, folder: Path, prefix: str) -> None:
    src: Path = getattr(result, "_wav_path", None)
    if src and src.exists():
        dst = folder / f"{prefix}_{result.song_id}.wav"
        shutil.move(str(src), dst)


def _write_meta(result: DownloadResult, folder: Path) -> None:
    if result.song_id and result.meta:
        meta_path = folder / f"{result.song_id}.json"
        meta_path.write_text(
            json.dumps(result.meta, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _safe_dirname(name: str) -> str:
    for ch in r'\/:*?"<>|':
        name = name.replace(ch, "_")
    return name.strip()
