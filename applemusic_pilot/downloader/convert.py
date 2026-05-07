from __future__ import annotations
import subprocess
from pathlib import Path


class ConvertError(RuntimeError):
    pass


def convert_to_wav(src: Path, dst: Path) -> None:
    if not src.exists():
        raise ConvertError(f"Source file does not exist: {src}")
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-c:a", "pcm_s24le", str(dst)],
        capture_output=True,
    )
    if result.returncode != 0:
        raise ConvertError(
            f"ffmpeg conversion failed (exit {result.returncode}): "
            f"{result.stderr.decode(errors='replace')}"
        )
