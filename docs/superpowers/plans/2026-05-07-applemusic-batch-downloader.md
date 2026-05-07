# Apple Music 批量无损下载器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `applemusic_pilot/downloader/` 新增批量下载模块，读取两行一对的 URL list，调用 AppleMusicDecrypt 下载 ALAC，ffmpeg 转 WAV，按样例目录结构输出，生成 meta JSON 和异常报告。

**Architecture:** Python 编排层调用 AppleMusicDecrypt（git submodule）的 `Ripper.rip_song()` async API 下载解密，`save()` 写出 .m4a 到临时目录，ffmpeg 转 WAV，最后整理到 `{output_dir}/{song_name}/` 结构。AppleMusicDecrypt 作为 git submodule 放在 `E:/QQMusicSpider/AppleMusicDecrypt/`，通过 `sys.path` 注入使用。

**Tech Stack:** Python 3.11+, asyncio, AppleMusicDecrypt (submodule), ffmpeg (系统 PATH), mutagen (读 m4a tag)

---

## 文件结构

```
E:/QQMusicSpider/
├── AppleMusicDecrypt/                    ← git submodule（已存在或需克隆）
│   └── config.toml                       ← 运行时配置（wrapper地址等）
└── applemusic_pilot/
    └── downloader/
        ├── __init__.py                   ← 空
        ├── models.py                     ← PairTask, DownloadResult dataclass
        ├── amd_bridge.py                 ← 初始化 AppleMusicDecrypt 环境，封装单首下载
        ├── convert.py                    ← ffmpeg m4a→wav
        ├── organizer.py                  ← 整理输出目录结构，写 meta JSON
        ├── report.py                     ← 收集失败记录，写 异常信息.txt
        └── batch.py                      ← 主入口 CLI，读 list，编排并发
```

---

## Task 1: 克隆 AppleMusicDecrypt submodule 并验证可导入

**Files:**
- Create: `E:/QQMusicSpider/AppleMusicDecrypt/` (git clone)
- Create: `E:/QQMusicSpider/AppleMusicDecrypt/config.toml`

- [ ] **Step 1: 克隆仓库**

```bash
cd E:/QQMusicSpider
git clone --proxy http://127.0.0.1:7890 https://github.com/WorldObservationLog/AppleMusicDecrypt.git AppleMusicDecrypt
```

Expected: 目录 `E:/QQMusicSpider/AppleMusicDecrypt/` 存在，含 `main.py`

- [ ] **Step 2: 安装依赖**

```bash
cd E:/QQMusicSpider/AppleMusicDecrypt
pip install poetry
poetry install
```

Expected: 无报错，`poetry run python -c "from src.rip import Ripper; print('ok')"` 输出 `ok`

- [ ] **Step 3: 创建 config.toml**

复制示例配置并填写 wrapper 地址：

```bash
cp E:/QQMusicSpider/AppleMusicDecrypt/config.example.toml E:/QQMusicSpider/AppleMusicDecrypt/config.toml
```

编辑 `config.toml`，将 `[instance]` 的 url 改为实际 wrapper-manager 地址（如公共测试实例 `wm.wol.moe`，`secure = true`）：

```toml
[instance]
url = "wm.wol.moe"
secure = true

[download]
parallelNum = 2
dirPathFormat = "downloads/{album_artist}/{album}"
songNameFormat = "{disk}-{tracknum:02d} {title}"
```

- [ ] **Step 4: 验证 wrapper 连通性**

```bash
cd E:/QQMusicSpider/AppleMusicDecrypt
poetry run python main.py
# 在交互式 shell 中输入: status
# 预期输出: Regions available on wrapper-manager instance: us, jp 等
# 输入: exit
```

---

## Task 2: models.py — 数据结构定义

**Files:**
- Create: `E:/QQMusicSpider/applemusic_pilot/downloader/__init__.py`
- Create: `E:/QQMusicSpider/applemusic_pilot/downloader/models.py`
- Create: `E:/QQMusicSpider/applemusic_pilot/tests/test_downloader_models.py`

- [ ] **Step 1: 写失败测试**

```python
# E:/QQMusicSpider/applemusic_pilot/tests/test_downloader_models.py
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
```

- [ ] **Step 2: 运行，确认失败**

```bash
cd E:/QQMusicSpider
python -m pytest applemusic_pilot/tests/test_downloader_models.py -v
```

Expected: `ImportError: cannot import name 'PairTask'`

- [ ] **Step 3: 创建 `__init__.py` 和 `models.py`**

```python
# E:/QQMusicSpider/applemusic_pilot/downloader/__init__.py
```

```python
# E:/QQMusicSpider/applemusic_pilot/downloader/models.py
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
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest applemusic_pilot/tests/test_downloader_models.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd E:/QQMusicSpider
git add applemusic_pilot/downloader/__init__.py applemusic_pilot/downloader/models.py applemusic_pilot/tests/test_downloader_models.py
git commit -m "feat: add downloader models PairTask and DownloadResult"
```

---

## Task 3: convert.py — ffmpeg m4a→wav

**Files:**
- Create: `E:/QQMusicSpider/applemusic_pilot/downloader/convert.py`
- Create: `E:/QQMusicSpider/applemusic_pilot/tests/test_convert.py`

- [ ] **Step 1: 写失败测试**

```python
# E:/QQMusicSpider/applemusic_pilot/tests/test_convert.py
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
    # 生成 1 秒静音 m4a 作为测试素材
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
```

- [ ] **Step 2: 运行，确认失败**

```bash
python -m pytest applemusic_pilot/tests/test_convert.py -v
```

Expected: `ImportError: cannot import name 'convert_to_wav'`

- [ ] **Step 3: 实现 convert.py**

```python
# E:/QQMusicSpider/applemusic_pilot/downloader/convert.py
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
        raise ConvertError(f"ffmpeg conversion failed (exit {result.returncode}): {result.stderr.decode(errors='replace')}")
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest applemusic_pilot/tests/test_convert.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add applemusic_pilot/downloader/convert.py applemusic_pilot/tests/test_convert.py
git commit -m "feat: add ffmpeg m4a->wav converter"
```

---

## Task 4: organizer.py — 输出目录整理 + meta JSON

**Files:**
- Create: `E:/QQMusicSpider/applemusic_pilot/downloader/organizer.py`
- Create: `E:/QQMusicSpider/applemusic_pilot/tests/test_organizer.py`

- [ ] **Step 1: 写失败测试**

```python
# E:/QQMusicSpider/applemusic_pilot/tests/test_organizer.py
from __future__ import annotations
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from applemusic_pilot.downloader.models import DownloadResult
from applemusic_pilot.downloader.organizer import organize_pair


def test_organize_pair(tmp_path):
    # 准备假 wav 文件
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
```

- [ ] **Step 2: 运行，确认失败**

```bash
python -m pytest applemusic_pilot/tests/test_organizer.py -v
```

Expected: `ImportError: cannot import name 'organize_pair'`

- [ ] **Step 3: 实现 organizer.py**

```python
# E:/QQMusicSpider/applemusic_pilot/downloader/organizer.py
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
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest applemusic_pilot/tests/test_organizer.py -v
```

Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add applemusic_pilot/downloader/organizer.py applemusic_pilot/tests/test_organizer.py
git commit -m "feat: add organizer for output directory structure and meta JSON"
```

---

## Task 5: report.py — 异常信息.txt

**Files:**
- Create: `E:/QQMusicSpider/applemusic_pilot/downloader/report.py`
- Create: `E:/QQMusicSpider/applemusic_pilot/tests/test_report.py`

- [ ] **Step 1: 写失败测试**

```python
# E:/QQMusicSpider/applemusic_pilot/tests/test_report.py
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
```

- [ ] **Step 2: 运行，确认失败**

```bash
python -m pytest applemusic_pilot/tests/test_report.py -v
```

Expected: `ImportError: cannot import name 'Reporter'`

- [ ] **Step 3: 实现 report.py**

```python
# E:/QQMusicSpider/applemusic_pilot/downloader/report.py
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class _FailEntry:
    pair_idx: int
    role: str
    url: str
    reason: str


@dataclass
class Reporter:
    total_pairs: int
    _successes: int = field(default=0, init=False)
    _failures: List[_FailEntry] = field(default_factory=list, init=False)

    def record_success(self, pair_idx: int) -> None:
        self._successes += 1

    def record_failure(self, pair_idx: int, role: str, url: str, reason: str) -> None:
        self._failures.append(_FailEntry(pair_idx, role, url, reason))

    def write(self, path: Path) -> None:
        lines = [
            f"总计: {self.total_pairs} 对，成功: {self._successes}，失败: {len(self._failures)}",
            "",
        ]
        for entry in self._failures:
            lines.append(
                f"[FAILED] pair #{entry.pair_idx} {entry.role:<6} {entry.url} → {entry.reason}"
            )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest applemusic_pilot/tests/test_report.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add applemusic_pilot/downloader/report.py applemusic_pilot/tests/test_report.py
git commit -m "feat: add Reporter for 异常信息.txt generation"
```

---

## Task 6: amd_bridge.py — 封装 AppleMusicDecrypt 单首下载

**Files:**
- Create: `E:/QQMusicSpider/applemusic_pilot/downloader/amd_bridge.py`

> 注意：此模块无法用纯单元测试覆盖（需要真实 wrapper），集成测试在 Task 8 进行。

- [ ] **Step 1: 实现 amd_bridge.py**

```python
# E:/QQMusicSpider/applemusic_pilot/downloader/amd_bridge.py
"""
封装 AppleMusicDecrypt 的初始化和单首歌下载。

使用前提：
  1. E:/QQMusicSpider/AppleMusicDecrypt/ 已 git clone
  2. 依赖已通过 poetry install 安装
  3. config.toml 已配置 wrapper-manager 地址
  4. wrapper-manager 正在运行
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path
from typing import Optional

AMD_DIR = Path(__file__).resolve().parents[3] / "AppleMusicDecrypt"


def _ensure_amd_on_path() -> None:
    amd_str = str(AMD_DIR)
    if amd_str not in sys.path:
        sys.path.insert(0, amd_str)


def _build_meta_dict(metadata) -> dict:
    return {
        "song_id": metadata.song_id,
        "song_name": metadata.title,
        "artist_name": metadata.artist,
        "album": metadata.album,
        "album_artist": metadata.album_artist,
        "genre": metadata.genre,
        "isrc": metadata.isrc,
        "upc": metadata.upc,
        "composer": metadata.composer,
        "created": metadata.created,
        "copyright": metadata.copyright,
        "record_company": metadata.record_company,
        "tracknum": metadata.tracknum,
        "disk": metadata.disk,
    }


class AMDBridge:
    """初始化一次，复用下载多首歌。"""

    def __init__(self, amd_dir: Path = AMD_DIR):
        _ensure_amd_on_path()
        # 延迟导入，避免在 AMD 未安装时 import 本模块报错
        import os
        os.chdir(amd_dir)  # AMD 读取 config.toml 依赖 cwd

        from creart import it, add_creator
        from src.logger import LoggerCreator
        from src.config import ConfigCreator
        from src.api import APICreator, WebAPI
        from src.grpc.manager import WMCreator, WrapperManager
        from src.measurer import MeasurerCreator
        from src.rip import Ripper
        from src.utils import check_dep

        add_creator(LoggerCreator)
        add_creator(ConfigCreator)
        add_creator(APICreator)
        add_creator(WMCreator)
        add_creator(MeasurerCreator)

        self._it = it
        self._Ripper = Ripper
        self._WebAPI = WebAPI
        self._WrapperManager = WrapperManager
        self._loop = asyncio.new_event_loop()
        self._ripper: Optional[Ripper] = None

    def start(self) -> None:
        from src.utils import run_sync
        self._loop.run_until_complete(run_sync(self._it(self._WebAPI).init))
        from src.config import Config
        cfg = self._it(Config)
        self._loop.run_until_complete(
            self._it(self._WrapperManager).init(cfg.instance.url, cfg.instance.secure)
        )
        self._ripper = self._Ripper()
        self._loop.run_until_complete(
            self._it(self._WrapperManager).decrypt_init(
                on_success=self._ripper.on_decrypt_success,
                on_failure=self._ripper.on_decrypt_failed,
            )
        )

    def download_song(self, url: str, tmp_dir: Path) -> tuple[Path, dict]:
        """
        下载单首歌到 tmp_dir，返回 (m4a_path, meta_dict)。
        失败时抛出异常。
        """
        from src.config import Config
        from src.url import AppleMusicURL
        from src.flags import Flags
        from src.task import Status

        cfg = self._it(Config)
        # 临时把 dirPathFormat 改为 tmp_dir，让 save() 写到我们指定的位置
        original_fmt = cfg.download.dirPathFormat
        cfg.download.dirPathFormat = str(tmp_dir / "{album_artist}" / "{album}")

        song_url = AppleMusicURL.parse_url(url)
        if song_url is None:
            raise ValueError(f"Cannot parse Apple Music URL: {url}")

        task_ref: list = []

        async def _run():
            await self._ripper.rip_song(song_url, "alac", Flags())
            task = self._ripper.download_manager.adam_id_task_mapping.get(song_url.id)
            task_ref.append(task)

        # rip_song 会自动 unregister，所以在 gather 完成后从已结束任务找结果
        # 改用监听方式：注入 done event
        done_event = asyncio.Event()

        async def _run_with_wait():
            original_unregister = self._ripper.download_manager.unregister_task

            async def patched_unregister(task):
                await original_unregister(task)
                if task.adamId == song_url.id:
                    task_ref.append(task)
                    done_event.set()

            self._ripper.download_manager.unregister_task = patched_unregister
            from src.flags import Flags as F
            await self._ripper.rip_song(song_url, "alac", F())
            await done_event.wait()
            self._ripper.download_manager.unregister_task = original_unregister

        self._loop.run_until_complete(_run_with_wait())
        cfg.download.dirPathFormat = original_fmt

        if not task_ref:
            raise RuntimeError(f"No task result for {url}")

        task = task_ref[0]
        from src.task import Status
        if task.status != Status.DONE:
            raise RuntimeError(str(task.error) if task.error else f"Download failed for {url}")

        # 找到生成的 m4a 文件
        m4a_files = list(tmp_dir.rglob("*.m4a"))
        if not m4a_files:
            raise RuntimeError(f"No .m4a file found in {tmp_dir} after download")

        meta = _build_meta_dict(task.metadata) if task.metadata else {}
        meta["original_url"] = url
        return m4a_files[0], meta

    def close(self) -> None:
        self._loop.close()
```

- [ ] **Step 2: Commit**

```bash
git add applemusic_pilot/downloader/amd_bridge.py
git commit -m "feat: add AMDBridge wrapping AppleMusicDecrypt Ripper"
```

---

## Task 7: batch.py — 主入口 CLI

**Files:**
- Create: `E:/QQMusicSpider/applemusic_pilot/downloader/batch.py`
- Create: `E:/QQMusicSpider/applemusic_pilot/tests/test_batch_parse.py`

- [ ] **Step 1: 写 URL list 解析的失败测试**

```python
# E:/QQMusicSpider/applemusic_pilot/tests/test_batch_parse.py
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
```

- [ ] **Step 2: 运行，确认失败**

```bash
python -m pytest applemusic_pilot/tests/test_batch_parse.py -v
```

Expected: `ImportError: cannot import name 'parse_pairs'`

- [ ] **Step 3: 实现 batch.py**

```python
# E:/QQMusicSpider/applemusic_pilot/downloader/batch.py
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
    except (ConvertError, RuntimeError, ValueError, Exception) as exc:
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
                print(f"  ✓ pair #{pair.idx}: {origin.song_name}")
            else:
                if not origin.success:
                    reporter.record_failure(pair.idx, "origin", pair.origin_url, origin.error or "unknown")
                    print(f"  ✗ pair #{pair.idx} origin failed: {origin.error}")
                if not cover.success:
                    reporter.record_failure(pair.idx, "cover", pair.cover_url, cover.error or "unknown")
                    print(f"  ✗ pair #{pair.idx} cover failed: {cover.error}")
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
```

- [ ] **Step 4: 运行解析测试，确认通过**

```bash
python -m pytest applemusic_pilot/tests/test_batch_parse.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add applemusic_pilot/downloader/batch.py applemusic_pilot/tests/test_batch_parse.py
git commit -m "feat: add batch CLI entry point with pair parsing and orchestration"
```

---

## Task 8: 集成测试 — 真实下载 1 对

**Files:**
- Create: `E:/QQMusicSpider/applemusic_pilot/tests/test_integration_download.py`

> 此测试需要 wrapper-manager 运行中，标记为 `@pytest.mark.integration`，默认不执行。

- [ ] **Step 1: 写集成测试**

```python
# E:/QQMusicSpider/applemusic_pilot/tests/test_integration_download.py
"""集成测试：需要 wrapper-manager 运行中。运行方式：pytest -m integration"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from applemusic_pilot.downloader.batch import run_batch, parse_pairs

# Closer (feat. Halsey) 原唱 + 翻唱
TEST_PAIRS = """\
https://music.apple.com/ca/album/closer-feat-halsey/1136768287?i=1136768508
https://music.apple.com/ca/album/closer-cover/1369347671?i=1369347677
"""


@pytest.mark.integration
def test_download_one_pair(tmp_path):
    pairs = parse_pairs(TEST_PAIRS)
    run_batch(pairs, tmp_path / "output")

    folder = tmp_path / "output" / "Closer (feat. Halsey)"
    assert folder.is_dir(), f"Expected folder {folder} not found"

    wavs = list(folder.glob("*.wav"))
    assert len(wavs) == 2, f"Expected 2 wav files, got {wavs}"

    origin_wav = folder / f"original_1136768508.wav"
    assert origin_wav.exists()

    jsons = list(folder.glob("*.json"))
    assert len(jsons) == 2
```

- [ ] **Step 2: 确认单元测试全部仍然通过**

```bash
python -m pytest applemusic_pilot/tests/ -v --ignore=applemusic_pilot/tests/test_integration_download.py
```

Expected: 全部 passed（不含集成测试）

- [ ] **Step 3: 在 wrapper-manager 运行时执行集成测试**

```bash
cd E:/QQMusicSpider
python -m pytest applemusic_pilot/tests/test_integration_download.py -v -m integration
```

Expected: 1 passed，`output/Closer (feat. Halsey)/` 含 2 个 wav + 2 个 json

- [ ] **Step 4: Commit**

```bash
git add applemusic_pilot/tests/test_integration_download.py
git commit -m "test: add integration test for one pair download"
```

---

## Task 9: 验证样例格式一致性

- [ ] **Step 1: 用样例数据对比输出**

准备一个包含 Circles pair 的 list 文件：

```
# E:/QQMusicSpider/test_pairs.txt
https://music.apple.com/ca/album/circles/1477886950?i=1477887285
https://music.apple.com/ca/album/circles-cover/1756821964?i=1756821965
```

运行：

```bash
cd E:/QQMusicSpider
python -m applemusic_pilot.downloader.batch test_pairs.txt --output-dir ./test_output
```

- [ ] **Step 2: 对比输出结构与样例**

```bash
ls test_output/Circles/
# 期望: cover_1756821965.wav  original_1477887285.wav  1477887285.json  1756821965.json
```

检查 JSON 内容与样例一致：

```bash
cat test_output/Circles/1477887285.json
# 期望: {"song_id": "1477887285", "song_name": "Circles", "artist_name": "Post Malone", ...}
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: verify output matches sample format"
```
