# Apple Music 批量无损下载器 设计文档

## 概述

在 `applemusic_pilot` 模块内新增 `downloader` 子包，实现批量下载 Apple Music 无损音频（ALAC→WAV）、提取 meta JSON、生成异常报告的完整流水线。底层下载解密依赖 `AppleMusicDecrypt`（Python 库，作为 git submodule 集成）。

---

## 输入格式

纯文本文件，两行一对，奇数行=原唱，偶数行=翻唱，空行忽略：

```
https://music.apple.com/us/album/.../...?i=111
https://music.apple.com/us/album/.../...?i=222

https://music.apple.com/us/album/.../...?i=333
https://music.apple.com/us/album/.../...?i=444
```

---

## 输出结构

```
{output_dir}/
  {song_name}/                    ← 原唱 song_name 作为文件夹名
    original_{song_id}.wav
    cover_{song_id}.wav
    {origin_song_id}.json
    {cover_song_id}.json
  异常信息.txt                    ← 记录失败条目
```

---

## 模块结构

```
applemusic_pilot/downloader/
  __init__.py
  models.py       — PairTask dataclass（origin_url, cover_url, idx）
  rip.py          — 封装 AppleMusicDecrypt Ripper，下载单首到临时目录，返回 .m4a 路径
  convert.py      — ffmpeg: .m4a(ALAC) → .wav
  meta.py         — 从 AppleMusicDecrypt WebAPI 拉取 meta → dict → {song_id}.json
  report.py       — 收集 FailedEntry，写 异常信息.txt
  batch.py        — 主入口：读 list → 编排每对任务 → 整理输出目录

AppleMusicDecrypt/              ← git submodule
```

---

## 数据流

```
pairs.txt
  ↓ batch.py: 解析成 List[PairTask]
  ↓ 对每对：asyncio.gather(rip origin, rip cover)  ← 对内并发
  ↓ rip.py: 调用 AppleMusicDecrypt Ripper.rip_song() → 临时目录 .m4a
  ↓ convert.py: ffmpeg -i *.m4a -c:a pcm_s24le *.wav
  ↓ meta.py: 读 embedded tag / WebAPI → {song_id}.json
  ↓ 整理到 {output_dir}/{song_name}/
  ↓ report.py: 汇总失败 → 异常信息.txt
```

---

## 并发策略

- **对内**：origin + cover 两首 `asyncio.gather` 并发下载
- **对间**：`asyncio.Semaphore(concurrency)` 控制，默认 `concurrency=2`（可 CLI 参数覆盖）
- 目的：避免触发 Apple Music 限流

---

## CLI

```bash
python -m applemusic_pilot.downloader.batch pairs.txt \
    --output-dir ./output \
    --concurrency 2 \
    --amd-dir ./AppleMusicDecrypt
```

| 参数 | 说明 | 默认 |
|------|------|------|
| `pairs.txt` | 输入 list 文件 | 必填 |
| `--output-dir` | 输出根目录 | `./output` |
| `--concurrency` | 并发对数 | `2` |
| `--amd-dir` | AppleMusicDecrypt 路径 | `./AppleMusicDecrypt` |

---

## 异常处理

- 单首下载失败：记录到 report，继续处理其余对
- 整对失败：文件夹不创建，两条均记录异常
- ffmpeg 不存在：启动时检测，立即报错退出
- AppleMusicDecrypt wrapper 未启动：启动时检测连接，立即报错退出

---

## 异常信息.txt 格式

```
总计: 10 对，成功: 8，失败: 2

[FAILED] pair #3 origin https://music.apple.com/... → Song not found on Apple Music
[FAILED] pair #5 cover  https://music.apple.com/... → ffmpeg conversion failed: exit code 1
```

---

## 依赖

- `AppleMusicDecrypt`（submodule）及其依赖（poetry install）
- `ffmpeg`（系统 PATH）
- `MP4Box`（系统 PATH，AppleMusicDecrypt 需要）
- Python 3.11+
