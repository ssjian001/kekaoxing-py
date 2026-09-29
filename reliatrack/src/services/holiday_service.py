"""节假日服务 — 从 DB holidays 表读取/管理节假日数据。

提供按年查询、增删改的接口，替代 scheduler.py 中的硬编码节假日。
排程引擎通过 get_holidays_set() 获取日期集合。
"""

from __future__ import annotations

import logging
from datetime import date

import apsw

logger = logging.getLogger(__name__)


def _is_valid_iso_date(date_str: object) -> bool:
    """严格校验 YYYY-MM-DD。

    date.fromisoformat 在 3.11+ 也接受紧凑格式（"20240101"），而排程侧
    比较的是 d.isoformat() 生成的带连字符字符串——紧凑格式照样匹配不上
    任何日期（同样导致漏假），所以这里按长度 + 连字符位置严格判定。
    """
    if not isinstance(date_str, str) or len(date_str) != 10:
        return False
    if date_str[4] != "-" or date_str[7] != "-":
        return False
    try:
        date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return False
    return True


def _validate_iso_date(date_str: str) -> None:
    """校验日期为合法 ISO 格式（YYYY-MM-DD），否则抛 ValueError。

    审计 #17：holidays 表无 CHECK 约束，非法格式（"2024/01/01"、
    "2024-13-99"）入库后会被 get_holidays_set 的字符串区间过滤
    静默隐藏，导致排程漏假。
    """
    if not _is_valid_iso_date(date_str):
        raise ValueError(
            f"节假日日期格式非法: {date_str!r}（要求 YYYY-MM-DD）"
        )


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

        审计 P3-6：修复前入库的非法日期行（'2024/01/01'、'2024-13-99'）
        会被原样放进集合——永远匹配不上任何 ISO 日期 → 排程静默漏假；
        另有部分格式被字符串区间过滤直接吞掉。这里逐行校验：非法日期
        跳过并记 warning 日志（不静默、不修改用户数据），需要人工清洗时
        用 list_invalid_holidays() 列出待处理行。
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
        holidays: set[str] = set()
        invalid: list[str] = []
        for r in rows:
            date_str = str(r[0])
            if not _is_valid_iso_date(date_str):
                invalid.append(date_str)
                continue
            holidays.add(date_str)
        if invalid:
            logger.warning(
                "holidays 表有 %d 条非法日期行已跳过（排程无法识别，需人工清洗）: %s",
                len(invalid), invalid[:10],
            )
        return holidays

    def list_invalid_holidays(self) -> list[dict[str, object]]:
        """列出 holidays 表中日期格式非法的存量行（只读，不修改数据）。

        供启动诊断/提醒使用：这些行会被 get_holidays_set 跳过（排程漏假），
        但清洗是用户决定——本方法只报告，不删除、不改写。
        """
        rows = self._conn.execute(
            "SELECT id, date, name, source FROM [holidays] ORDER BY date"
        ).fetchall()
        invalid: list[dict[str, object]] = []
        for r in rows:
            date_str = str(r[1])
            if _is_valid_iso_date(date_str):
                continue
            invalid.append(
                {"id": r[0], "date": r[1], "name": r[2], "source": r[3]}
            )
        return invalid

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
        # 审计 #17：日期零校验会让 "2024/01/01" 这类非法格式入库后被
        # 字符串区间过滤静默隐藏（排程漏假）。入库前强制 ISO 格式校验。
        _validate_iso_date(date_str)
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
        # 审计 #17：批量导入同样强制 ISO 格式校验（先整体校验再入库）
        for date_str, _name, _source in records:
            _validate_iso_date(date_str)
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
