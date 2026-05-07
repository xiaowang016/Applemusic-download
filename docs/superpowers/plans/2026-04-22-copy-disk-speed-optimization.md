# 拷盘代码QQ02 速度优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化 `拷盘代码QQ02.py` 在 NAS 源盘（500万目录）+ USB HDD 目标盘场景下的扫描速度和导盘吞吐量，消除卡顿。

**Architecture:** 将单线程串行扫描改为16线程并行扫描；将每首歌4次网络 I/O 合并为1次（scandir结果缓存为 file_cache 传入所有函数）；将128写入线程降为24以减少 USB HDD 随机 I/O 争抢；stats 改用线程本地计数批量合并减少锁竞争。

**Tech Stack:** Python 3.x, threading, queue, shutil, subprocess, ffmpeg

---

### Task 1: 将 file_cache 引入 is_valid_track / get_track_id_from_json

**Files:**
- Modify: `E:/QQMusicSpider/拷盘代码QQ02.py:85-120`

**目标：** 将 scandir 结果从外部传入，避免函数内部重复扫描目录。

- [ ] **Step 1: 修改 `is_valid_track` 接受可选 `file_cache` 参数**

将原函数替换为：

```python
def is_valid_track(track_path, file_cache=None):
    try:
        if file_cache is not None:
            has_audio = file_cache.get('audio') is not None
            json_file = file_cache.get('json')
            if file_cache.get('has_tmp'):
                return False
        else:
            has_audio, json_file = False, None
            with os.scandir(track_path) as its:
                for it in its:
                    name_low = it.name.lower()
                    if name_low.endswith(".tmp"):
                        return False
                    if name_low.endswith((".flac", ".mp3", ".m4a", ".ogg", ".ape", ".wav")):
                        has_audio = True
                    if name_low.endswith(".json"):
                        json_file = it.name
        if not (has_audio and json_file):
            return False
        json_path = os.path.join(track_path, json_file)
        with open(json_path, 'r', encoding='utf-8', errors='ignore') as f:
            json.load(f)
        return True
    except:
        return False
```

- [ ] **Step 2: 修改 `get_track_id_from_json` 接受可选 `file_cache` 参数**

将原函数替换为：

```python
def get_track_id_from_json(track_path, file_cache=None):
    try:
        json_file = None
        if file_cache is not None:
            json_file = file_cache.get('json')
        else:
            with os.scandir(track_path) as its:
                for it in its:
                    if it.name.lower().endswith(".json"):
                        json_file = it.name
                        break
        if json_file:
            with open(os.path.join(track_path, json_file), 'r', encoding='utf-8', errors='ignore') as f:
                data = json.load(f)
                return str(data.get('song_id') or data.get('song_mid'))
    except:
        pass
    base_name = os.path.basename(track_path)
    if "_" in base_name:
        return base_name.split("_")[-1]
    return base_name
```

- [ ] **Step 3: 新增 `build_file_cache` 辅助函数（放在 is_valid_track 上方）**

```python
def build_file_cache(track_path):
    """一次 scandir 扫出目录内所有关键文件，返回 cache 字典。"""
    cache = {'audio': None, 'json': None, 'has_tmp': False}
    try:
        with os.scandir(track_path) as its:
            for it in its:
                name_low = it.name.lower()
                if name_low.endswith('.tmp'):
                    cache['has_tmp'] = True
                elif name_low.endswith(('.flac', '.mp3', '.m4a', '.ogg', '.ape', '.wav')):
                    if cache['audio'] is None:
                        cache['audio'] = it.name
                elif name_low.endswith('.json'):
                    cache['json'] = it.name
    except OSError:
        pass
    return cache
```

- [ ] **Step 4: 手动验证函数签名正确，无语法错误**

```bash
cd E:/QQMusicSpider && python -c "import ast; ast.parse(open('拷盘代码QQ02.py', encoding='utf-8').read()); print('语法OK')"
```

期望输出：`语法OK`

- [ ] **Step 5: Commit**

```bash
cd E:/QQMusicSpider && git add 拷盘代码QQ02.py && git commit -m "perf: add file_cache to is_valid_track / get_track_id_from_json"
```

---

### Task 2: 重写 claim_and_move 使用 file_cache，消除重复 listdir

**Files:**
- Modify: `E:/QQMusicSpider/拷盘代码QQ02.py:123-206`

- [ ] **Step 1: 将 `claim_and_move` 签名改为接受 `file_cache` 参数**

将函数签名改为：

```python
def claim_and_move(src_dir, target_root, stats, serial, node_name, file_cache=None):
```

- [ ] **Step 2: 替换函数内两处 listdir 为 file_cache**

将函数内寻找音频文件的代码块：

```python
        audio_file = None
        for f in os.listdir(src_dir):
            if f.endswith((".flac", ".m4a", ".ogg", ".mp3", ".ape", ".wav")):
                audio_file = f
                break

        if not audio_file:
            return False
```

替换为：

```python
        audio_file = file_cache['audio'] if file_cache else None
        if not audio_file:
            for f in os.listdir(src_dir):
                if f.endswith((".flac", ".m4a", ".ogg", ".mp3", ".ape", ".wav")):
                    audio_file = f
                    break
        if not audio_file:
            return False
```

将函数内寻找 JSON 文件的代码块：

```python
        # JSON 原样拷贝
        for f in os.listdir(src_dir):
            if f.endswith(".json"):
```

替换为：

```python
        # JSON 原样拷贝
        json_files = ([file_cache['json']] if file_cache and file_cache.get('json')
                      else [f for f in os.listdir(src_dir) if f.endswith('.json')])
        for f in json_files:
```

- [ ] **Step 3: 同步修改函数顶部的 `is_valid_track` 和 `get_track_id_from_json` 调用，传入 cache**

将：

```python
def claim_and_move(src_dir, target_root, stats, serial, node_name, file_cache=None):
    if not is_valid_track(src_dir):
        return False
    track_id = get_track_id_from_json(src_dir)
```

改为：

```python
def claim_and_move(src_dir, target_root, stats, serial, node_name, file_cache=None):
    if not is_valid_track(src_dir, file_cache):
        return False
    track_id = get_track_id_from_json(src_dir, file_cache)
```

- [ ] **Step 4: 验证语法**

```bash
cd E:/QQMusicSpider && python -c "import ast; ast.parse(open('拷盘代码QQ02.py', encoding='utf-8').read()); print('语法OK')"
```

期望输出：`语法OK`

- [ ] **Step 5: Commit**

```bash
cd E:/QQMusicSpider && git add 拷盘代码QQ02.py && git commit -m "perf: claim_and_move uses file_cache, eliminates repeat listdir"
```

---

### Task 3: 并行扫描 + 调整线程数 + 扩大队列

**Files:**
- Modify: `E:/QQMusicSpider/拷盘代码QQ02.py:20,239-310`

- [ ] **Step 1: 修改顶部配置常量**

将：

```python
MAX_WORKERS = 128
```

替换为：

```python
MAX_WORKERS = 24          # USB HDD 写入线程（降低随机 I/O 争抢）
SCAN_WORKERS = 16         # NAS 并行扫描线程
QUEUE_MAXSIZE = 50000     # 扫描/写入完全解耦，避免生产者阻塞
```

- [ ] **Step 2: 修改 `run_task` 的队列初始化**

将：

```python
    q = Queue(maxsize=5000)
```

改为：

```python
    q = Queue(maxsize=QUEUE_MAXSIZE)
```

- [ ] **Step 3: 修改 `run_task` 的 worker 数量**

将：

```python
    workers = [threading.Thread(target=simple_worker, daemon=True) for _ in range(MAX_WORKERS)]
```

保持不变（MAX_WORKERS 已改为24，自动生效）。

- [ ] **Step 4: 将 SHIP 模式的单线程递归扫描改为多线程并行扫描**

将 `run_task` 函数内 SHIP 分支（`if mode == "SHIP":` 及其下的 `recursive_scan`）整体替换为：

```python
    if mode == "SHIP":
        scan_q = Queue()          # 待扫目录队列（无上限，内存可控）
        scan_q.put((SOURCE_DIR_DEFAULT, 0))
        scan_lock = threading.Lock()
        active_scanners = [0]

        def scanner_worker():
            while True:
                try:
                    item = scan_q.get(timeout=2)
                except Exception:
                    with scan_lock:
                        if scan_q.empty():
                            break
                    continue
                base_path, depth = item
                if depth > 5 or stats['stop']:
                    scan_q.task_done()
                    continue
                try:
                    entries = list(os.scandir(base_path))
                except OSError:
                    scan_q.task_done()
                    continue
                for entry in entries:
                    if not entry.is_dir():
                        continue
                    with stats['lock']:
                        stats['found'] += 1
                    cache = build_file_cache(entry.path)
                    if cache['audio'] and cache['json'] and not cache['has_tmp']:
                        q.put((entry.path, target_root,
                               os.path.basename(SOURCE_DIR_DEFAULT), cache))
                    else:
                        scan_q.put((entry.path, depth + 1))
                scan_q.task_done()

        scan_threads = [
            threading.Thread(target=scanner_worker, daemon=True)
            for _ in range(SCAN_WORKERS)
        ]
        for st in scan_threads:
            st.start()
        for st in scan_threads:
            st.join()
```

- [ ] **Step 5: 更新 `simple_worker` 以接收 file_cache（队列元素格式变了）**

将 `simple_worker` 内的 SHIP 分支：

```python
            if mode == "SHIP":
                claim_and_move(t[0], t[1], stats, serial, t[2])
```

改为：

```python
            if mode == "SHIP":
                claim_and_move(t[0], t[1], stats, serial, t[2],
                               file_cache=t[3] if len(t) > 3 else None)
```

- [ ] **Step 6: 验证语法**

```bash
cd E:/QQMusicSpider && python -c "import ast; ast.parse(open('拷盘代码QQ02.py', encoding='utf-8').read()); print('语法OK')"
```

期望输出：`语法OK`

- [ ] **Step 7: Commit**

```bash
cd E:/QQMusicSpider && git add 拷盘代码QQ02.py && git commit -m "perf: parallel NAS scan with 16 threads, queue=50000, workers=24"
```

---

### Task 4: stats 批量合并 + 进度显示优化

**Files:**
- Modify: `E:/QQMusicSpider/拷盘代码QQ02.py:239-310`

- [ ] **Step 1: 在 `run_task` 函数顶部添加线程本地计数支持**

在 `stats = {...}` 定义后面插入：

```python
    _tl = threading.local()

    def _get_local():
        if not hasattr(_tl, 'count'):
            _tl.count = _tl.bytes = _tl.converted = _tl.mp3_kept = 0
        return _tl

    def _flush_local(force=False):
        loc = _get_local()
        total = loc.count + loc.bytes + loc.converted + loc.mp3_kept
        if total == 0:
            return
        if not force and total < 100:
            return
        with stats['lock']:
            stats['count']     += loc.count
            stats['bytes']     += loc.bytes
            stats['converted'] += loc.converted
            stats['mp3_kept']  += loc.mp3_kept
        loc.count = loc.bytes = loc.converted = loc.mp3_kept = 0
```

- [ ] **Step 2: 修改 `claim_and_move` 末尾的 stats 更新，改为写本地计数**

将 `claim_and_move` 中：

```python
        with stats['lock']:
            stats['count'] += 1
            stats['bytes'] += track_size
            if converted:
                stats['converted'] = stats.get('converted', 0) + 1
                stats['type'] = "MP3→FLAC 转码入库"
            elif is_mp3:
                stats['mp3_kept'] = stats.get('mp3_kept', 0) + 1
                stats['type'] = "MP3 原样入库"
            else:
                stats['type'] = "极简交付入库"
        return True
```

改为接受额外参数 `_flush_fn=None, _tl_fn=None`，但由于 claim_and_move 是独立函数不方便注入，**改为保留原有 lock 写法，仅优化进度显示**（批量合并收益在500万量级中等，不强制注入复杂度）。

> 注：此步保留原 lock 写法，重点优化在进度显示。

- [ ] **Step 3: 优化进度显示，增加队列深度和首/s 指标**

将 `run_monitor` 函数替换为：

```python
    last_count = [0]
    last_time  = [start_time]

    def run_monitor():
        while not stats['done']:
            with stats['lock']:
                f  = stats['found']
                c  = stats['count']
                b  = stats['bytes']
                cv = stats['converted']
                mk = stats['mp3_kept']
            now = time.time()
            el  = now - start_time
            dt  = now - last_time[0]
            dc  = c - last_count[0]
            sp  = (b / 1024 / 1024) / el if el > 0 else 0
            rate = dc / dt if dt > 0 else 0
            last_count[0] = c
            last_time[0]  = now
            qs = q.qsize()
            sys.stdout.write(
                f"\r扫到:{f} 队列:{qs} 成功:{c} 转FLAC:{cv} 留MP3:{mk}"
                f" | {b/(1024**3):.2f}GB | {sp:.1f}MB/s | {rate:.0f}首/s   "
            )
            sys.stdout.flush()
            time.sleep(1.0)
```

- [ ] **Step 4: 验证语法**

```bash
cd E:/QQMusicSpider && python -c "import ast; ast.parse(open('拷盘代码QQ02.py', encoding='utf-8').read()); print('语法OK')"
```

期望输出：`语法OK`

- [ ] **Step 5: Commit**

```bash
cd E:/QQMusicSpider && git add 拷盘代码QQ02.py && git commit -m "perf: improved progress display with queue depth and songs/s rate"
```

---

### Task 5: 集成验证

**Files:**
- Read: `E:/QQMusicSpider/拷盘代码QQ02.py`

- [ ] **Step 1: 完整语法检查**

```bash
cd E:/QQMusicSpider && python -c "import ast; ast.parse(open('拷盘代码QQ02.py', encoding='utf-8').read()); print('语法OK')"
```

期望输出：`语法OK`

- [ ] **Step 2: 导入检查（不执行 main）**

```bash
cd E:/QQMusicSpider && python -c "
import importlib.util, sys
spec = importlib.util.spec_from_file_location('m', '拷盘代码QQ02.py')
mod  = importlib.util.module_from_spec(spec)
sys.argv = ['x', 'D:']
try:
    spec.loader.exec_module(mod)
except SystemExit:
    pass
except Exception as e:
    print('导入错误:', e)
else:
    print('导入OK')
"
```

期望输出：`导入OK` 或因找不到磁盘正常退出（无 traceback）

- [ ] **Step 3: 确认关键函数签名正确**

```bash
cd E:/QQMusicSpider && python -c "
import ast, sys
tree = ast.parse(open('拷盘代码QQ02.py', encoding='utf-8').read())
fns = {n.name: [a.arg for a in n.args.args] for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
for name in ['build_file_cache','is_valid_track','get_track_id_from_json','claim_and_move']:
    print(name, fns.get(name, 'NOT FOUND'))
"
```

期望输出：
```
build_file_cache ['track_path']
is_valid_track ['track_path', 'file_cache']
get_track_id_from_json ['track_path', 'file_cache']
claim_and_move ['src_dir', 'target_root', 'stats', 'serial', 'node_name', 'file_cache']
```

- [ ] **Step 4: 最终 Commit**

```bash
cd E:/QQMusicSpider && git add 拷盘代码QQ02.py && git commit -m "perf: QQ02 NAS scan optimization complete - 16 scan threads, file_cache, queue=50000"
```
