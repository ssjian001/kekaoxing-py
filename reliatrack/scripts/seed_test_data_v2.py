"""ReliaTrack 测试数据增强脚本 v2 — 追加模式。

在现有数据基础上补充: 待办/Issue 扩容+评论/FA+CAPA 补齐/计划任务扩容/
结果矩阵填满/出入库记录。不动已有数据, 通过 Service 层写入。

运行: cd reliatrack && .venv/bin/python scripts/seed_test_data_v2.py
"""
from __future__ import annotations

import sys
import os
import random

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_PROJECT_ROOT)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from datetime import datetime, timedelta
from src.db.connection import get_connection, close_all_connections
from src.db.schema import init_schema
from src.controllers.app_controller import AppController

random.seed(20260822)


def seed_v2(ctrl: AppController) -> None:
    today = datetime.now()
    d = lambda off=0: (today + timedelta(days=off)).strftime("%Y-%m-%d")

    techs = [t.id for t in ctrl.technician_service.list_all()]
    equips = [e.id for e in ctrl.equipment_service.list_all()]
    projects = [p.id for p in ctrl.project_service.list_all()]
    plans = [pl.id for pl in ctrl.test_plan_service.list_all_plans()]
    print(f"现有: 技术员{len(techs)} 设备{len(equips)} 项目{len(projects)} 计划{len(plans)}")

    # ── 1. 待办事项 (18 条, 覆盖优先级×状态×逾期) ─────────────
    todos = [
        ("跟进 ECU 高温存储变色问题根因分析", 0, "high", "in_progress", "分析", -2, 1),
        ("安排电池模组过充复测", 0, "high", "pending", "测试", 3, 1),
        ("更新显示屏 UV 老化测试报告", 1, "medium", "pending", "文档", 5, 2),
        ("校准振动台传感器", -1, "medium", "in_progress", "设备", -5, 3),
        ("评审连接器端子改型图纸", 1, "high", "pending", "评审", 1, 2),
        ("整理三月试验箱使用记录", -1, "low", "done", "文档", -10, 3),
        ("准备客户审核资料 (长安)", 0, "high", "pending", "审核", 7, 1),
        ("确认盐雾试验腐蚀评级照片", 1, "medium", "in_progress", "分析", 0, 2),
        ("处理焊点裂纹 8D 报告回复", 0, "high", "pending", "报告", -1, 1),
        ("预约第三方 EMC 实验室", -1, "medium", "pending", "外部", 10, 3),
        ("样品柜季度盘点", -1, "low", "pending", "样品", 14, 3),
        ("BMS 固件升级后回归验证", 0, "high", "in_progress", "测试", 2, 1),
        ("核对传感器 HALT 试验数据", 1, "medium", "done", "数据", -7, 2),
        ("更新 FMEA 中的焊点失效模式", 0, "medium", "pending", "文档", 8, 2),
        ("采购新的偏光片样品", 1, "low", "pending", "采购", 20, 3),
        ("培训新员工操作跌落机", -1, "low", "done", "培训", -3, 3),
        ("检查恒温恒湿箱压缩机异响", -1, "high", "in_progress", "设备", -4, 1),
        ("月度 KPI 数据汇总", 0, "medium", "pending", "报告", 6, 2),
    ]
    for title, proj_off, prio, status, cat, due_off, quad in todos:
        pid = projects[proj_off] if proj_off < len(projects) else None
        ctrl.todo_service.create(
            project_id=pid, title=title,
            description=f"{title} — 自动生成演示数据",
            priority=prio, status=status, category=cat,
            due_date=d(due_off), quadrant=quad,
        )
    print(f"  待办: +{len(todos)}")

    # ── 2. Issue 扩容 (补 19 条) + 评论 ───────────────────────
    issue_templates = [
        # (title, mode, stage, sev, status, proj_off, days_ago)
        ("ECU 低温启动超时", "功能失效", "-40°C冷启动", "major", "open", 0, 2),
        ("电池模组循环容量衰减过快", "性能降级", "500循环后", "major", "analyzing", 0, 9),
        ("显示屏高温黑屏", "功能失效", "85°C运行2h", "critical", "open", 0, 1),
        ("传感器信号噪声偏大", "精度异常", "常温标定时", "minor", "open", 1, 12),
        ("连接器端子镀层脱落", "外观异常", "插拔500次后", "minor", "verified", 1, 20),
        ("PCB 板边分层起泡", "结构失效", "回流焊后", "critical", "analyzing", 1, 5),
        ("ECU CAN 总线丢帧", "功能失效", "振动+温循中", "major", "analyzing", 0, 7),
        ("显示屏触摸偏移", "功能失效", "低温试验中", "minor", "open", 2, 3),
        ("密封圈老化变硬", "材料劣化", "双85试验1000h", "minor", "closed", 2, 45),
        ("紧固件盐雾红锈", "腐蚀", "盐雾96h", "major", "verified", 2, 18),
        ("线束表皮磨损露铜", "结构失效", "振动耐久后", "major", "open", 0, 4),
        ("电源模块效率下降", "性能降级", "高温老化500h", "minor", "verified", 1, 15),
        ("摄像头模组进雾", "外观异常", "温循试验后", "major", "analyzing", 2, 8),
        ("蜂鸣器音量衰减", "性能降级", "高温存储后", "minor", "closed", 2, 60),
        ("接插件保持力不足", "结构失效", "装配抽检", "major", "verified", 0, 25),
        ("绝缘片击穿", "电气异常", "耐压测试", "critical", "closed", 1, 35),
        ("标签起翘", "外观异常", "高温高湿后", "minor", "closed", 2, 50),
        ("按键手感变硬", "装配异常", "低温试验后", "minor", "open", 2, 6),
        ("充电接口温升超标", "电气异常", "快充测试", "critical", "analyzing", 0, 3),
    ]
    cause_cats = ["料", "法", "机", "环", "测"]
    new_issues = []
    for title, mode, stage, sev, status, proj_off, days_ago in issue_templates:
        pid = projects[proj_off]
        created = d(-days_ago)
        iid = ctrl.issue_service.create(
            title=title, failure_mode=mode, failure_stage=stage,
            severity=sev, status=status, priority=random.randint(1, 4),
            project_id=pid, plan_id=random.choice(plans) if plans else None,
            description=f"{stage}发现: {title}。自动生成演示数据。",
            root_cause="待分析" if status in ("open", "analyzing") else "已定位具体根因",
            resolution="" if status in ("open", "analyzing") else "已完成对应改善措施",
            failure_code=f"FM-{random.randint(100, 999)}",
            occurrence_count=random.randint(1, 8),
            dri_name=random.choice(["张伟", "李娜", "赵敏", "王磊"]),
            created_at=created,
        )
        new_issues.append((iid, status, days_ago))
        # 评论
        if days_ago >= 5:
            ctrl.issue_service.add_comment(
                iid, "初判为试验条件边界问题, 已安排复测确认。", "张伟")
            if days_ago >= 12:
                ctrl.issue_service.add_comment(
                    iid, "复测仍可复现, 升级给研发分析根因。", "李娜")
        # FA 记录
        ctrl.issue_service.add_fa_record(
            issue_id=iid, step_no=1, step_title="外观检查",
            description="目视+放大镜观察", method="目视/放大镜",
            findings="定位到异常部位", possible_cause="",
            cause_category=random.choice(cause_cats),
            failure_mechanism="性能退化", confirmed=0,
            analyst_id=random.choice(techs),
        )
        if status not in ("open",):
            ctrl.issue_service.add_fa_record(
                issue_id=iid, step_no=2, step_title="深入分析",
                description="切片/ESEM/电测定位", method="SEM+EDX",
                findings="确认失效路径与机理", possible_cause="材料+工艺复合因素",
                cause_category=random.choice(cause_cats),
                failure_mechanism="疲劳/退化", confirmed=1,
                analyst_id=random.choice(techs),
            )
        # CAPA
        if status in ("verified", "closed"):
            ctrl.issue_service.add_capa_record(
                issue_id=iid, action="工程变更+产线验证",
                assignee_name=random.choice(["张伟", "陈刚"]),
                due_date=d(random.randint(-5, 25)),
                status="completed" if status == "closed" else "in_progress",
                root_cause="已确认根因",
                effectiveness="复测合格" if status == "closed" else "",
                follow_up="跟踪3批次" if status == "closed" else "",
                verifier_name="李娜" if status == "closed" else "",
            )
    print(f"  Issue: +{len(new_issues)} (含评论/FA/CAPA)")

    # 给存量 6 个 issue 也补 FA/CAPA
    for old in ctrl.issue_service.list_all()[:6]:
        if old.id in [i for i, _, _ in new_issues]:
            continue
        try:
            ctrl.issue_service.add_fa_record(
                issue_id=old.id, step_no=1, step_title="外观检查",
                description="目视检查", method="目视", findings="已检查",
                possible_cause="", cause_category="料",
                failure_mechanism="性能退化", confirmed=0,
                analyst_id=techs[0] if techs else None,
            )
        except Exception:
            pass
    print("  存量 Issue FA 补齐")

    # ── 3. 新测试计划 + 任务 (3 个新计划) ─────────────────────
    new_plan_specs = [
        (0, "ECU 盐雾与防护验证", "ISO 9227", "P2", [
            ("中性盐雾试验", "环境试验", 4, 1, "96h NSS", "", "腐蚀等级≥4级", 2),
            ("防水试验 IPX7", "环境试验", 1, 6, "1m水深30min", "", "无进水", 1),
            ("防尘试验 IP6X", "环境试验", 2, 8, "滑石粉8h", "", "无粉尘侵入", 2),
        ]),
        (1, "电池模组振动耐久", "GB/T 31467", "P3", [
            ("随机振动-XYZ", "机械试验", 6, 1, "3轴各4h", "", "无结构损伤", 1),
            ("机械冲击", "机械试验", 1, 8, "25g/6ms", "", "无泄漏", 2),
            ("挤压测试", "安全试验", 1, 9, "100kN", "", "不起火", 3),
        ]),
        (2, "显示屏高低温运行全温区", "GB/T 28046", "P3", [
            ("低温运行 -30°C", "环境试验", 2, 1, "冷启动", "", "启动正常", 1),
            ("高温运行 85°C", "环境试验", 3, 3, "满负荷", "", "显示正常", 1),
            ("温度梯度循环", "环境试验", 5, 6, "-30↔85 50cycles", "", "无异常", 2),
        ]),
    ]
    new_tasks = []
    for proj_off, name, std, phase, tasks in new_plan_specs:
        pid = projects[proj_off]
        plan_id = ctrl.test_plan_service.create_plan(
            project_id=pid, name=name, test_standard=std,
            start_date=d(-20), end_date=d(40), status="in_progress",
            apqp_phase=phase,
        )
        for idx, (tname, cat, dur, sday, temp, hum, crit, prio) in enumerate(tasks):
            t_status = ["pending", "in_progress", "completed", "paused", "in_progress"][idx % 5]
            tid = ctrl.test_plan_service.create_task(
                plan_id=plan_id, name=tname, category=cat,
                test_standard=f"{std} §{idx+1}",
                technician_id=random.choice(techs) if techs else None,
                equipment_id=random.choice(equips) if equips else None,
                sample_ids="[]", duration=dur, start_day=sday,
                progress=100.0 if t_status == "completed" else random.uniform(15, 85) if t_status == "in_progress" else 0.0,
                status=t_status, priority=prio,
                temperature=temp, humidity=hum, accept_criteria=crit,
                sort_order=idx,
            )
            new_tasks.append((tid, t_status))
    print(f"  测试计划: +{len(new_plan_specs)}, 任务: +{len(new_tasks)}")

    # ── 4. 样品出入库记录 ──────────────────────────────────────
    all_samples = ctrl.sample_service.list_all() if hasattr(ctrl.sample_service, "get_all") else []
    txn_count = 0
    for i, s in enumerate(all_samples[:12]):
        for j in range(2):
            try:
                ctrl.sample_service.add_transaction(
                    s.id,
                    "check_out" if j == 0 else "return",
                    operator=random.choice(["张伟", "王磊", "赵敏"]),
                    location=f"试验现场{random.randint(1,3)}" if j == 0 else f"样品柜{random.randint(1,3)}",
                    notes=f"演示出入库记录 #{i}-{j}",
                    txn_date=d(-random.randint(1, 30)),
                )
                txn_count += 1
            except Exception:
                pass
    print(f"  出入库记录: +{txn_count}")

    print("\n=== v2 增强数据生成完成 ===")


if __name__ == "__main__":
    # 与 main.py 相同的 dev DB 路径逻辑: 优先 data/reliatrack.db
    _local_db = os.path.join(_parent_dir, "data", "reliatrack.db")
    db_path = _local_db if os.path.exists(_local_db) else ""
    conn = get_connection(db_path)
    init_schema(conn)
    ctrl = AppController(db_path)
    ctrl.initialize()
    seed_v2(ctrl)
    close_all_connections()
