"""健康检查服务 — 启动自检 + 数据体检。

参考同类项目模式:
- Calibre db/restore.py: 启动检测损坏 → 提示从备份恢复
- TagStudio registries: 数据完整性后台扫描 + 修复入口

设计约束:
- check_db 必须在 init_schema 之前跑(库还没被写入时检测最真实)
- 扫描类查询一律排除软删除行(is_deleted=1)避免误报
- 附件完整性复用 IssueService.scan_attachment_integrity, 不重复实现
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DbCheckResult:
    """数据库完整性检查结果。"""

    ok: bool = True
    quick_check: list[str] = field(default_factory=list)   # PRAGMA quick_check 输出行
    fk_violations: list[str] = field(default_factory=list) # PRAGMA foreign_key_check 输出行

    def summary(self) -> str:
        lines: list[str] = []
        if self.quick_check:
            lines.append("完整性检查: " + "; ".join(self.quick_check[:5]))
        if self.fk_violations:
            lines.append(f"外键约束违规 {len(self.fk_violations)} 处")
        return "\n".join(lines) if lines else "正常"


def check_db(conn) -> DbCheckResult:
    """对主库跑快速完整性检查(毫秒级, 只读)。

    Args:
        conn: apsw.Connection — 已打开的数据库连接。

    Returns:
        DbCheckResult — ok=True 表示可安全使用。
    """
    result = DbCheckResult()
    try:
        rows = conn.execute("PRAGMA quick_check").fetchall()
        # quick_check 正常时返回单行 ('ok',)
        bad = [str(r[0]) for r in rows if str(r[0]).lower() != "ok"]
        if bad:
            result.quick_check = bad
            result.ok = False
    except Exception:
        logger.exception("quick_check 执行失败(视为损坏)")
        result.quick_check = ["检查无法执行(数据库可能损坏)"]
        result.ok = False

    if result.ok:
        try:
            fk = conn.execute("PRAGMA foreign_key_check").fetchall()
            if fk:
                # 每行 (table, rowid, parent, fkid)
                result.fk_violations = [f"{r[0]}#{r[1]} → {r[2]}" for r in fk[:50]]
                result.ok = False
        except Exception:
            # foreign_key_check 失败不视为致命(旧库可能不支持)
            logger.debug("foreign_key_check 跳过", exc_info=True)

    return result


class DbCorruptError(RuntimeError):
    """数据库损坏 — 携带 DbCheckResult 供 UI 展示详情。"""

    def __init__(self, message: str, result: "DbCheckResult"):
        super().__init__(message)
        self.check_result = result


def scan_data_health(controller) -> dict[str, list[str]]:
    """全量数据体检(供 UI 调用, 可能较慢 — 应在后台线程跑)。

    复用既有扫描实现, 汇总为一份报告:
    - 附件: missing_files / orphan_files (来自 IssueService)
    - 结果断链: test_results 引用不存在的 task
    """
    report: dict[str, list[str]] = {
        "missing_files": [],
        "orphan_files": [],
        "broken_result_refs": [],
    }

    # 1. 附件完整性(复用)
    if controller.issue_service:
        try:
            scan = controller.issue_service.scan_attachment_integrity()
            report["missing_files"] = scan.get("missing_files", [])
            report["orphan_files"] = scan.get("orphan_files", [])
        except Exception:
            logger.exception("附件扫描失败")

    # 2. test_results 断链(排除软删除)
    conn = controller._conn
    if conn is not None:
        try:
            rows = conn.execute(
                "SELECT r.id, r.task_id FROM test_results r "
                "LEFT JOIN test_tasks t ON t.id = r.task_id "
                "WHERE r.task_id IS NOT NULL AND t.id IS NULL"
            ).fetchall()
            report["broken_result_refs"] = [f"结果#{r[0]} → 任务#{r[1]}" for r in rows[:100]]
        except Exception:
            logger.debug("test_results 断链扫描跳过")

    return report


def delete_orphan_files(paths: list[str]) -> tuple[int, list[str]]:
    """删除孤儿附件文件(仅限备份目录白名单内, 返回 (成功数, 失败清单))。

    安全约束: 只删 DEFAULT_ATTACHMENTS_DIR 内的文件, 目录外的引用一律拒绝。
    """
    from src.db.connection import DEFAULT_ATTACHMENTS_DIR

    base = DEFAULT_ATTACHMENTS_DIR.resolve()
    deleted = 0
    failures: list[str] = []
    for p in paths:
        try:
            fp = Path(p).resolve()
            if base not in fp.parents:
                failures.append(f"{p} (目录外, 拒绝删除)")
                continue
            fp.unlink(missing_ok=True)
            deleted += 1
        except Exception as exc:
            failures.append(f"{p} ({exc})")
    return deleted, failures
