"""数据库备份与恢复服务。

提供全库备份（apsw Backup API）和恢复功能。
备份为完整 SQLite 文件快照，保证 FK 一致性。
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import apsw

from src.db.connection import (
    DEFAULT_BACKUPS_DIR,
    close_connection,
    get_connection,
)
from src.db.schema import SCHEMA_VERSION, _get_current_version

logger = logging.getLogger(__name__)


@dataclass
class BackupInfo:
    """备份文件元信息。"""
    path: Path
    filename: str
    size_mb: float
    modified: datetime
    schema_version: int

    @property
    def display_name(self) -> str:
        return f"{self.filename}  ({self.size_mb:.1f} MB, schema v{self.schema_version})"


class BackupService:
    """数据库备份与恢复。"""

    def __init__(self, db_path: str = "") -> None:
        self._db_path = db_path

    # ── 备份 ──

    def create_backup(self, dest_path: str | Path) -> Path:
        """使用 apsw Backup API 创建一致性备份。

        Args:
            dest_path: 目标文件路径。父目录不存在会自动创建。

        Returns:
            实际写入的文件路径。

        Raises:
            FileExistsError: 目标文件已存在。
            RuntimeError: 备份过程中出错。
        """
        dest_path = Path(dest_path)
        if dest_path.exists():
            raise FileExistsError(f"备份文件已存在: {dest_path}")
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        src_conn = get_connection(self._db_path)
        dest_conn = apsw.Connection(str(dest_path))
        try:
            with src_conn.backup("main", dest_conn, "main") as backup:
                backup.step()
            logger.info("备份已创建: %s", dest_path)
        except Exception:
            dest_conn.close()
            if dest_path.exists():
                dest_path.unlink(missing_ok=True)
            raise RuntimeError("备份失败") from None
        finally:
            dest_conn.close()

        return dest_path

    def create_auto_backup(self) -> Path:
        """创建带时间戳的自动备份到默认备份目录。

        文件名格式: reliatrack_YYYYMMDD_HHMMSS.db
        """
        DEFAULT_BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = DEFAULT_BACKUPS_DIR / f"reliatrack_{ts}.db"
        return self.create_backup(dest)

    # ── 恢复 ──

    @staticmethod
    def validate_backup(backup_path: str | Path) -> BackupInfo:
        """验证备份文件是否为合法的 ReliaTrack 数据库。

        Returns:
            BackupInfo 元信息。

        Raises:
            FileNotFoundError: 文件不存在。
            ValueError: 不是有效的 ReliaTrack 备份。
        """
        backup_path = Path(backup_path)
        if not backup_path.exists():
            raise FileNotFoundError(f"备份文件不存在: {backup_path}")

        try:
            conn = apsw.Connection(str(backup_path))
            try:
                version = _get_current_version(conn)
            finally:
                conn.close()
        except Exception as exc:
            raise ValueError(f"无法读取备份文件: {exc}") from None

        if version == 0:
            raise ValueError("备份文件不是有效的 ReliaTrack 数据库（缺少 schema_version）")

        if version > SCHEMA_VERSION:
            raise ValueError(
                f"备份 schema 版本 (v{version}) 高于当前程序 (v{SCHEMA_VERSION})，"
                f"请先升级 ReliaTrack"
            )

        stat = backup_path.stat()
        return BackupInfo(
            path=backup_path,
            filename=backup_path.name,
            size_mb=round(stat.st_size / (1024 * 1024), 2),
            modified=datetime.fromtimestamp(stat.st_mtime),
            schema_version=version,
        )

    def restore_backup(self, backup_path: str | Path) -> None:
        """从备份文件恢复数据库。

        流程: 验证 → 自动备份当前库 → 关闭连接 → 替换文件 → 重新初始化。

        Raises:
            FileNotFoundError: 备份文件不存在。
            ValueError: 备份不合法。
            RuntimeError: 恢复失败（自动回滚）。
        """
        backup_path = Path(backup_path)

        # 1. 验证
        info = self.validate_backup(backup_path)

        # 2. 自动备份当前库（恢复前的安全网）
        current_db = Path(get_connection(self._db_path).db_filename("main") or self._db_path)
        safety_backup: Path | None = None
        if current_db.exists():
            DEFAULT_BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safety_backup = DEFAULT_BACKUPS_DIR / f"reliatrack_pre_restore_{ts}.db"
            try:
                self.create_backup(safety_backup)
                logger.info("恢复前安全备份: %s", safety_backup)
            except Exception:
                logger.warning("恢复前安全备份失败，继续恢复")

        # 3. 关闭当前连接
        close_connection(self._db_path)

        # 4. 替换文件
        try:
            shutil.copy2(str(backup_path), str(current_db))
            logger.info(
                "数据库已恢复: %s → %s (schema v%d)",
                backup_path, current_db, info.schema_version,
            )
        except Exception:
            # 回滚: 恢复安全备份
            if safety_backup and safety_backup.exists():
                try:
                    shutil.copy2(str(safety_backup), str(current_db))
                    logger.info("回滚成功，已恢复安全备份")
                except Exception:
                    logger.exception("回滚失败！请手动恢复: %s", safety_backup)
            raise RuntimeError("恢复失败") from None

        # 5. 如果备份 schema 版本低于当前，init_schema 会自动迁移
        # 重新获取连接即可，init_schema 在 AppController 中调用

    # ── 列表 ──

    @staticmethod
    def list_backups() -> list[BackupInfo]:
        """列出默认备份目录中的所有备份文件。"""
        DEFAULT_BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        backups: list[BackupInfo] = []
        for f in sorted(DEFAULT_BACKUPS_DIR.glob("reliatrack_*.db"), reverse=True):
            try:
                info = BackupService.validate_backup(f)
                backups.append(info)
            except (ValueError, FileNotFoundError):
                # 跳过损坏的备份文件
                logger.debug("跳过无效备份: %s", f)
        return backups

    @staticmethod
    def delete_backup(backup_path: str | Path) -> None:
        """删除指定备份文件。"""
        Path(backup_path).unlink(missing_ok=True)
