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
import os
import sys
from pathlib import Path
from typing import Optional

AMD_DIR = Path(__file__).resolve().parents[1] / "AppleMusicDecrypt-2"


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
        os.chdir(amd_dir)  # AMD 读取 config.toml 依赖 cwd

        from creart import it, add_creator
        from src.logger import LoggerCreator
        from src.config import ConfigCreator, Config
        add_creator(LoggerCreator)
        add_creator(ConfigCreator)
        _ = it(Config)  # 必须在 grpc/api import 前完成注册

        from src.api import APICreator, WebAPI
        from src.grpc.manager import WMCreator, WrapperManager
        from src.measurer import MeasurerCreator
        from src.rip import Ripper

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
        from src.config import Config
        from src.utils import safely_create_task

        cfg = self._it(Config)
        self._it(self._WebAPI).init()
        self._loop.run_until_complete(
            self._it(self._WrapperManager).init(cfg.instance.url, cfg.instance.secure)
        )
        self._ripper = self._Ripper()
        # decrypt_init 是无限流，必须作为后台 task 启动，不能 await
        self._loop.run_until_complete(self._start_decrypt_stream())

    async def _start_decrypt_stream(self) -> None:
        """启动解密流后台 task，等待 KEEPALIVE 确认连接建立。"""
        import asyncio
        ready = asyncio.Event()

        orig_success = self._ripper.on_decrypt_success
        orig_failure = self._ripper.on_decrypt_failed

        async def on_success_wrap(adam_id, key, sample, idx):
            ready.set()
            await orig_success(adam_id, key, sample, idx)

        async def on_failure_wrap(adam_id, key, sample, idx):
            ready.set()
            await orig_failure(adam_id, key, sample, idx)

        # 在后台启动无限流
        asyncio.ensure_future(
            self._it(self._WrapperManager).decrypt_init(
                on_success=on_success_wrap,
                on_failure=on_failure_wrap,
            ),
            loop=self._loop,
        )
        # 等第一个 keepalive/回调到来，确认流已建立（最多 15 秒）
        try:
            await asyncio.wait_for(ready.wait(), timeout=15)
        except asyncio.TimeoutError:
            pass  # keepalive 还没触发也没关系，流已经在跑了

    def download_song(self, url: str, tmp_dir: Path) -> tuple[Path, dict]:
        """下载单首歌到 tmp_dir，返回 (m4a_path, meta_dict)。失败时抛出异常。"""
        from src.config import Config
        from src.url import AppleMusicURL
        from src.flags import Flags
        from src.task import Status

        cfg = self._it(Config)
        original_fmt = cfg.download.dirPathFormat
        cfg.download.dirPathFormat = str(tmp_dir / "{album_artist}" / "{album}")

        song_url = AppleMusicURL.parse_url(url)
        if song_url is None:
            raise ValueError(f"Cannot parse Apple Music URL: {url}")

        task_ref: list = []
        done_event = asyncio.Event()

        async def _run_with_wait():
            original_unregister = self._ripper.download_manager.unregister_task

            async def patched_unregister(task):
                await original_unregister(task)
                if task.adamId == song_url.id:
                    task_ref.append(task)
                    done_event.set()

            self._ripper.download_manager.unregister_task = patched_unregister
            await self._ripper.rip_song(song_url, "alac", Flags())
            await done_event.wait()
            self._ripper.download_manager.unregister_task = original_unregister

        self._loop.run_until_complete(_run_with_wait())
        cfg.download.dirPathFormat = original_fmt

        if not task_ref:
            raise RuntimeError(f"No task result for {url}")

        task = task_ref[0]
        if task.status != Status.DONE:
            raise RuntimeError(str(task.error) if task.error else f"Download failed for {url}")

        m4a_files = list(tmp_dir.rglob("*.m4a"))
        if not m4a_files:
            raise RuntimeError(f"No .m4a file found in {tmp_dir} after download")

        meta = _build_meta_dict(task.metadata) if task.metadata else {}
        meta["original_url"] = url
        return m4a_files[0], meta

    def close(self) -> None:
        self._loop.close()
