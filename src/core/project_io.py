"""项目文件导入导出 (.kekaoxing JSON 格式)"""

from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.db.database import Database
from src.models import (
    Task, Resource, Section, ResourceType,
    EquipmentRequirement, UnavailablePeriod,
)

PROJECT_VERSION = "1.0"
PROJECT_MAGIC = "kekaoxing-project"


def export_project(db: Database, path: str) -> None:
    """将当前数据库导出为 .kekaoxing JSON 文件"""
    tasks = db.get_all_tasks()
    resources = db.get_all_resources()

    sections = db.get_all_sections()

    # Build task id→num mapping for foreign key remapping
    task_num_map = {t.id: t.num for t in tasks}

    # Export test results
    test_results = []
    for r in db.conn.execute(
        "SELECT id, task_id, test_date, result, test_data, notes, tester, "
        "attachments, created_at FROM test_results ORDER BY id"
    ).fetchall():
        test_results.append({
            "id": r[0], "task_num": task_num_map.get(r[1], ""),
            "test_date": r[2], "result": r[3], "test_data": r[4],
            "notes": r[5], "tester": r[6], "attachments": r[7], "created_at": r[8],
        })

    # Export test issues
    issues = []
    for i in db.conn.execute(
        "SELECT id, task_id, title, description, issue_type, severity, status, "
        "priority, phase, assignee, found_date, resolved_date, resolution, "
        "cause, countermeasure, tags, created_at, updated_at "
        "FROM test_issues ORDER BY id"
    ).fetchall():
        issues.append({
            "id": i[0], "task_num": task_num_map.get(i[1], ""),
            "title": i[2], "description": i[3], "issue_type": i[4], "severity": i[5],
            "status": i[6], "priority": i[7], "phase": i[8], "assignee": i[9],
            "found_date": i[10], "resolved_date": i[11], "resolution": i[12],
            "cause": i[13], "countermeasure": i[14], "tags": i[15],
            "created_at": i[16], "updated_at": i[17],
        })

    # Export issue history
    issue_history = []
    for h in db.conn.execute(
        "SELECT id, issue_id, field, old_value, new_value, changed_at, remark "
        "FROM issue_history ORDER BY id"
    ).fetchall():
        issue_history.append({
            "id": h[0], "old_issue_id": h[1],
            "field": h[2], "old_value": h[3], "new_value": h[4],
            "changed_at": h[5], "remark": h[6],
        })

    project = {
        "magic": PROJECT_MAGIC,
        "version": PROJECT_VERSION,
        "exported_at": datetime.now().isoformat(),
        "sections": sections,
        "tasks": [_task_to_dict(t) for t in tasks],
        "resources": [_resource_to_dict(r) for r in resources],
        "test_results": test_results,
        "test_issues": issues,
        "issue_history": issue_history,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False, indent=2)


def import_project(db: Database, path: str, merge: bool = False) -> dict:
    """从 .kekaoxing JSON 文件导入项目

    Args:
        db: 数据库实例
        path: 文件路径
        merge: True=合并（保留现有数据）, False=替换（清空现有数据）

    Returns:
        dict with keys: task_count, resource_count, warnings
    """
    with open(path, "r", encoding="utf-8") as f:
        project = json.load(f)

    # 验证格式
    if project.get("magic") != PROJECT_MAGIC:
        raise ValueError("不是有效的可测排程项目文件")

    warnings = []

    # 先导入分类（sections），确保外键/分类引用一致
    section_count = 0
    for sd in project.get("sections", []):
        try:
            db.insert_section(
                key=sd["key"],
                label=sd.get("label", sd["key"]),
                color=sd.get("color", ""),
                sort_order=sd.get("sort_order", 0),
            )
            section_count += 1
        except Exception:
            # key 已存在（UNIQUE 约束），跳过
            logging.debug("导入section跳过(已存在): key=%s", sd.get("key"), exc_info=True)

    if not merge:
        # 清空现有数据（先清理依赖表，再清理主表）
        db.conn.execute("DELETE FROM issue_history")
        db.conn.execute("DELETE FROM test_issues")
        db.conn.execute("DELETE FROM test_results")
        db.conn.execute("DELETE FROM tasks")
        db.conn.execute("DELETE FROM resources")

    task_count = 0
    for td in project.get("tasks", []):
        task = _dict_to_task(td)
        try:
            db.insert_task(task)
            task_count += 1
        except Exception as e:
            warnings.append(f"任务 {td.get('num', '?')} 导入失败: {e}")

    resource_count = 0
    for rd in project.get("resources", []):
        resource = _dict_to_resource(rd)
        try:
            db.insert_resource(resource)
            resource_count += 1
        except Exception as e:
            warnings.append(f"资源 {rd.get('name', '?')} 导入失败: {e}")

    # Build num→new_id mapping for task_id remapping
    num_to_new_id = {}
    for t in db.get_all_tasks():
        num_to_new_id[t.num] = t.id

    # Import test issues (before issue_history since history references issue IDs)
    issue_id_map = {}  # old_id → new_id
    issue_count = 0
    for idata in project.get("test_issues", []):
        new_task_id = num_to_new_id.get(idata.get("task_num", ""))
        if not new_task_id:
            warnings.append(
                f"Issue \"{idata.get('title', '?')}\" 跳过："
                f"找不到对应任务 {idata.get('task_num', '?')}"
            )
            continue
        old_issue_id = idata.get("id", 0)
        try:
            new_issue_id = db.insert_issue(
                task_id=new_task_id,
                title=idata["title"],
                description=idata.get("description", ""),
                issue_type=idata.get("issue_type", "bug"),
                severity=idata.get("severity", "medium"),
                status=idata.get("status", "open"),
                priority=idata.get("priority", 3),
                phase=idata.get("phase", ""),
                assignee=idata.get("assignee", ""),
                cause=idata.get("cause", ""),
                countermeasure=idata.get("countermeasure", ""),
                tags=idata.get("tags", "[]"),
            )
            issue_id_map[old_issue_id] = new_issue_id
            issue_count += 1
        except Exception as e:
            warnings.append(f"Issue \"{idata.get('title', '?')}\" 导入失败: {e}")

    # Import issue history
    history_count = 0
    for hdata in project.get("issue_history", []):
        old_issue_id = hdata.get("old_issue_id", 0)
        new_issue_id = issue_id_map.get(old_issue_id)
        if not new_issue_id:
            continue
        try:
            db.insert_issue_history(
                issue_id=new_issue_id,
                field=hdata.get("field", ""),
                old_value=hdata.get("old_value", ""),
                new_value=hdata.get("new_value", ""),
                remark=hdata.get("remark", ""),
            )
            history_count += 1
        except Exception:
            logging.debug("导入issue history跳过: old_issue_id=%s", old_issue_id, exc_info=True)

    # Import test results
    result_count = 0
    for rdata in project.get("test_results", []):
        new_task_id = num_to_new_id.get(rdata.get("task_num", ""))
        if not new_task_id:
            continue
        try:
            db.insert_test_result(
                task_id=new_task_id,
                result=rdata.get("result", "pending"),
                test_data=rdata.get("test_data", ""),
                notes=rdata.get("notes", ""),
                tester=rdata.get("tester", ""),
                attachments=rdata.get("attachments", "[]"),
            )
            result_count += 1
        except Exception:
            logging.debug("导入test result跳过: task_num=%s", rdata.get("task_num"), exc_info=True)

    return {
        "section_count": section_count,
        "task_count": task_count,
        "resource_count": resource_count,
        "issue_count": issue_count,
        "history_count": history_count,
        "result_count": result_count,
        "warnings": warnings,
    }


def _task_to_dict(t: Task) -> dict:
    section_val = t.section.value if isinstance(t.section, Section) else t.section
    return {
        "id": t.id,
        "num": t.num,
        "name_en": t.name_en,
        "name_cn": t.name_cn,
        "section": section_val,
        "duration": t.duration,
        "start_day": t.start_day,
        "progress": t.progress,
        "priority": t.priority,
        "done": t.done,
        "is_serial": t.is_serial,
        "serial_group": t.serial_group,
        "sample_pool": t.sample_pool,
        "sample_qty": t.sample_qty,
        "setup_time": t.setup_time,
        "teardown_time": t.teardown_time,
        "dependencies": t.dependencies,
        "requirements": [
            {"resource_id": r.resource_id, "quantity": r.quantity}
            for r in t.requirements
        ],
    }


def _dict_to_task(td: dict, preserve_id: bool = False) -> Task:
    return Task(
        id=td.get("id", 0) if preserve_id else 0,
        num=td["num"],
        name_en=td.get("name_en", ""),
        name_cn=td.get("name_cn", ""),
        section=Section(td.get("section", "env")),
        duration=td.get("duration", 1),
        start_day=td.get("start_day", 0),
        progress=td.get("progress", 0.0),
        priority=td.get("priority", 3),
        done=td.get("done", False),
        is_serial=td.get("is_serial", False),
        serial_group=td.get("serial_group") or "",
        sample_pool=td.get("sample_pool", "product"),
        sample_qty=td.get("sample_qty", 3),
        setup_time=td.get("setup_time", 0),
        teardown_time=td.get("teardown_time", 0),
        dependencies=td.get("dependencies", []),
        requirements=[
            EquipmentRequirement(resource_id=r["resource_id"], quantity=r.get("quantity", 1))
            for r in td.get("requirements", [])
        ],
    )


def _resource_to_dict(r: Resource) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "type": r.type.value,
        "category": r.category,
        "unit": r.unit,
        "available_qty": r.available_qty,
        "icon": r.icon,
        "description": r.description,
        "unavailable_periods": [
            {"start_day": p.start_day, "end_day": p.end_day, "reason": p.reason}
            for p in r.unavailable_periods
        ],
    }


def _dict_to_resource(rd: dict, preserve_id: bool = False) -> Resource:
    return Resource(
        id=rd.get("id", 0) if preserve_id else 0,
        name=rd["name"],
        type=ResourceType(rd.get("type", "equipment")),
        category=rd.get("category", ""),
        unit=rd.get("unit", "台"),
        available_qty=rd.get("available_qty", 1),
        icon=rd.get("icon", "📦"),
        description=rd.get("description", ""),
        unavailable_periods=[
            UnavailablePeriod(**p) for p in rd.get("unavailable_periods", [])
        ],
    )
