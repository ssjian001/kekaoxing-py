"""节假日服务 — 从 DB holidays 表读取/管理节假日数据。

提供按年查询、增删改的接口，替代 scheduler.py 中的硬编码节假日。
排程引擎通过 get_holidays_set() 获取日期集合。
"""

from __future__ import annotations

import logging
from datetime import date

import apsw

logger = logging.getLogger(__name__)


class HolidayService:
    """节假日 CRUD + 查询。"""

    def __init__(self, conn: apsw.Connection) -> None:
        self._conn = conn

    def get_holidays_set(
        self, year: int | None = None, future_only: bool = False,
    ) -> set[str]:
        """获取节假日日期集合（供 scheduler 使用）。

        Args:
            year: 指定年份，None 表示全部。
            future_only: 只返回今天及以后的日期。
        """
        conditions: list[str] = []
        params: list[object] = []
        if year is not None:
            conditions.append("date >= ?")
            conditions.append("date < ?")
            params.append(f"{year}-01-01")
            params.append(f"{year + 1}-01-01")
        if future_only:
            conditions.append("date >= ?")
            params.append(date.today().isoformat())
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = self._conn.execute(
            f"SELECT date FROM [holidays]{where} ORDER BY date", params
        ).fetchall()
        return {r[0] for r in rows}

    def get_holidays(
        self, year: int | None = None,
    ) -> list[dict[str, object]]:
        """获取节假日列表（含 name/source）。

        Returns:
            [{"id": n, "date": "...", "name": "...", "source": "..."}, ...]
        """
        if year is not None:
            rows = self._conn.execute(
                "SELECT id, date, name, source FROM [holidays] "
                "WHERE date >= ? AND date < ? ORDER BY date",
                (f"{year}-01-01", f"{year + 1}-01-01"),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, date, name, source FROM [holidays] ORDER BY date"
            ).fetchall()
        return [
            {"id": r[0], "date": r[1], "name": r[2], "source": r[3]}
            for r in rows
        ]

    def add_holiday(self, date_str: str, name: str, source: str = "custom") -> int:
        """添加自定义节假日。返回记录 ID；已存在时返回 0。"""
        before = self._conn.execute("SELECT COUNT(*) FROM [holidays]").fetchone()[0]
        self._conn.execute(
            "INSERT OR IGNORE INTO holidays (date, name, source) VALUES (?, ?, ?)",
            (date_str, name, source),
        )
        after = self._conn.execute("SELECT COUNT(*) FROM [holidays]").fetchone()[0]
        if after == before:
            # INSERT 被忽略 — 日期已存在
            return 0
        row = self._conn.execute(
            "SELECT id FROM [holidays] WHERE date = ?", (date_str,)
        ).fetchone()
        return row[0] if row else 0

    def delete_holiday(self, holiday_id: int) -> None:
        """删除节假日。"""
        self._conn.execute("DELETE FROM [holidays] WHERE id = ?", (holiday_id,))

    def import_holidays(self, records: list[tuple[str, str, str]]) -> int:
        """批量导入节假日 [(date, name, source), ...]，返回插入行数。

        使用 executemany + 事务包裹替代逐行 execute + changes()，
        减少 N+1 查询问题。
        """
        if not records:
            return 0
        # 事务前后 count 差值 = 实际插入行数
        before = self._conn.execute("SELECT COUNT(*) FROM [holidays]").fetchone()[0]
        self._conn.execute("BEGIN")
        try:
            self._conn.executemany(
                "INSERT OR IGNORE INTO holidays (date, name, source) VALUES (?, ?, ?)",
                records,
            )
            self._conn.execute("COMMIT")
        except Exception:
            logger.exception("Holiday service error")
            self._conn.execute("ROLLBACK")
            raise
        after = self._conn.execute("SELECT COUNT(*) FROM [holidays]").fetchone()[0]
        return after - before

    def seed_year_if_missing(self, year: int, records: list[tuple[str, str]]) -> int:
        """如果指定年份数据为空，则插入种子数据。返回插入行数。"""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM [holidays] WHERE date >= ? AND date < ?",
            (f"{year}-01-01", f"{year + 1}-01-01"),
        ).fetchone()
        if row and row[0] > 0:
            return 0  # 已有数据，不覆盖
        return self.import_holidays([(d, n, "builtin") for d, n in records])

    def has_year_data(self, year: int) -> bool:
        """指定年份是否已有节假日数据（供启动检测/排程提示）。"""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM [holidays] WHERE date >= ? AND date < ?",
            (f"{year}-01-01", f"{year + 1}-01-01"),
        ).fetchone()
        return bool(row and row[0] > 0)

    def ensure_current_year_seeded(self) -> bool:
        """启动时检查当年+下一年节假日数据是否齐全。

        Returns:
            True 数据齐全；False 当年/下一年缺失（调用方应提示用户手动维护）。
        """
        today_year = date.today().year
        return self.has_year_data(today_year) and self.has_year_data(today_year + 1)
