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
