from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class PairTask:
    idx: int
    origin_url: str
    cover_url: str


@dataclass
class DownloadResult:
    url: str
    role: str          # "origin" 或 "cover"
    success: bool
    m4a_path: Optional[Path] = None
    song_id: Optional[str] = None
    song_name: Optional[str] = None
    artist_name: Optional[str] = None
    meta: dict = field(default_factory=dict)
    error: Optional[str] = None
