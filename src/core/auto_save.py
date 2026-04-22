"""自动保存 + 版本快照管理器

- 每 30 秒检查未保存修改，备份 .bak 副本
- 崩溃恢复：启动时检测 .bak 是否比 .db 更新
- 版本快照：保留最近 10 个，自动清理旧快照
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

SNAPSHOT_DIR = "snapshots"
MAX_SNAPSHOTS = 10
METADATA_FILE = "snapshots.json"
SNAPSHOT_PREFIX = "kekaoxing_snapshot"


class AutoSaveManager(QObject):
    """自动保存和版本快照管理器"""

    save_triggered = Signal()  # 自动保存触发信号
    snapshot_created = Signal(str)  # 快照创建信号（传快照路径）

    def __init__(self, db_path: str, parent=None):
        super().__init__(parent)

        self.db_path = Path(db_path)
        self.bak_path = self.db_path.with_suffix(self.db_path.suffix + ".bak")
        self.snapshot_dir = self.db_path.parent / SNAPSHOT_DIR
        self.metadata_path = self.snapshot_dir / METADATA_FILE

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._auto_save)

        # 确保快照目录存在
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

        # 初始化元数据文件
        self._load_metadata()

    # ── 元数据持久化 ──────────────────────────────────────────

    def _load_metadata(self) -> list[dict]:
        """从 JSON 文件加载快照元数据"""
        if self.metadata_path.exists():
            try:
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                logging.warning("加载快照元数据失败: %s", self.metadata_path, exc_info=True)
        return []

    def _save_metadata(self, metadata: list[dict]) -> None:
        """将快照元数据写入 JSON 文件"""
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    # ── 自动保存 ──────────────────────────────────────────────

    def start(self, interval_ms: int = 30000) -> None:
        """启动自动保存定时器"""
        self._timer.start(interval_ms)

    def stop(self) -> None:
        """停止自动保存"""
        self._timer.stop()

    def _auto_save(self) -> None:
        """定时器回调：使用 SQLite backup API 创建 .bak 副本。

        使用 backup API 确保在 WAL 模式下也能完整复制数据。
        """
        if not self.db_path.exists():
            return
        try:
            import apsw
            bak_str = str(self.bak_path)
            # 删除旧的备份文件（apsw backup 会创建新文件）
            if self.bak_path.exists():
                self.bak_path.unlink()
            src = apsw.Connection(str(self.db_path))
            dst = apsw.Connection(bak_str)
            backup = dst.backup("main", src, "main")
            backup.step(-1)  # -1 = 全部复制
            backup.finish()
            dst.close()
            src.close()
            self.save_triggered.emit()
        except Exception:
            logging.warning("自动保存失败", exc_info=True)

    # ── 崩溃恢复 ──────────────────────────────────────────────

    def check_crash_recovery(self) -> Optional[str]:
        """检查是否需要崩溃恢复，返回 .bak 路径或 None

        条件：.bak 文件存在 且 比 .db 更新（修改时间更晚）且 .db 也存在。
        """
        if not self.bak_path.exists() or not self.db_path.exists():
            return None
        if self.bak_path.stat().st_mtime > self.db_path.stat().st_mtime:
            return str(self.bak_path)
        return None

    def recover_from_backup(self) -> bool:
        """从 .bak 恢复数据库文件"""
        if not self.bak_path.exists():
            return False
        try:
            shutil.copy2(self.bak_path, self.db_path)
            return True
        except OSError:
            return False

    # ── 版本快照 ──────────────────────────────────────────────

    def create_snapshot(self, label: str = "") -> str:
        """创建版本快照，返回快照路径。

        快照命名格式: kekaoxing_snapshot_20260421_193000.db
        超过 MAX_SNAPSHOTS 数量时自动清理最旧的快照。
        """
        if not self.db_path.exists():
            raise FileNotFoundError(f"数据库文件不存在: {self.db_path}")

        timestamp = datetime.now()
        ts_str = timestamp.strftime("%Y%m%d_%H%M%S") + f"_{timestamp.microsecond:06d}"
        snapshot_name = f"{SNAPSHOT_PREFIX}_{ts_str}.db"
        snapshot_path = self.snapshot_dir / snapshot_name

        # 使用 SQLite backup API 复制（确保 WAL 模式下数据完整）
        import apsw
        bak_str = str(snapshot_path)
        if snapshot_path.exists():
            snapshot_path.unlink()
        src = apsw.Connection(str(self.db_path))
        dst = apsw.Connection(bak_str)
        backup = dst.backup("main", src, "main")
        backup.step(-1)  # -1 = all pages
        dst.close()
        src.close()

        # 构建元数据条目
        size_mb = snapshot_path.stat().st_size / (1024 * 1024)
        entry = {
            "path": str(snapshot_path),
            "label": label or f"快照 {timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "timestamp": timestamp.isoformat(),
            "size_mb": round(size_mb, 2),
        }

        # 加载、追加、保存元数据
        metadata = self._load_metadata()
        metadata.append(entry)
        metadata = self._cleanup_old_snapshots(metadata)
        self._save_metadata(metadata)

        self.snapshot_created.emit(str(snapshot_path))
        return str(snapshot_path)

    def _cleanup_old_snapshots(self, metadata: list[dict]) -> list[dict]:
        """清理旧快照，保留最近 MAX_SNAPSHOTS 个。"""
        if len(metadata) <= MAX_SNAPSHOTS:
            return metadata

        # 按时间戳降序排列，保留最新的
        sorted_meta = sorted(metadata, key=lambda m: m["timestamp"], reverse=True)
        kept = sorted_meta[:MAX_SNAPSHOTS]
        removed = sorted_meta[MAX_SNAPSHOTS:]

        # 删除多余快照文件
        for entry in removed:
            fpath = Path(entry["path"])
            if fpath.exists():
                try:
                    fpath.unlink()
                except OSError:
                    logging.debug("清理旧快照文件失败: %s", fpath, exc_info=True)

        return kept

    def list_snapshots(self) -> list[dict]:
        """列出所有快照 [{path, label, timestamp, size_mb}, ...]

        按时间戳降序排列（最新在前）。
        同时校验文件是否存在，不存在则跳过。
        """
        metadata = self._load_metadata()
        result = []
        for entry in metadata:
            p = Path(entry["path"])
            if p.exists():
                result.append(entry)
        # 降序：最新在前
        result.sort(key=lambda m: m["timestamp"], reverse=True)
        return result

    def restore_snapshot(self, snapshot_path: str) -> bool:
        """从快照恢复数据库。

        会先创建一个"恢复前快照"以便回退。
        """
        src = Path(snapshot_path)
        if not src.exists():
            return False

        # 恢复前先创建一个自动快照，以便用户可以反悔
        try:
            pre_label = f"恢复前自动快照 {datetime.now().strftime('%H:%M:%S')}"
            self.create_snapshot(label=pre_label)
        except (OSError, FileNotFoundError):
            logging.debug("恢复前自动快照创建失败（不阻断恢复）", exc_info=True)

        try:
            import apsw
            # 用 SQLite backup API 替换，正确处理 WAL 模式
            # 以只读模式打开快照源，避免创建 -wal/-shm 影响读取
            snap_conn = apsw.Connection(str(src), flags=apsw.SQLITE_OPEN_READONLY)
            dst_conn = apsw.Connection(str(self.db_path))
            backup = dst_conn.backup("main", snap_conn, "main")
            backup.step(-1)
            backup.finish()
            dst_conn.close()
            snap_conn.close()
            return True
        except (OSError, apsw.SQLError):
            return False
