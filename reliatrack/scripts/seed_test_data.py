"""ReliaTrack 测试数据生成脚本。

通过 Service 层直接插入，生成一套覆盖所有 Tab 的完整测试数据。
运行方式: cd reliatrack && source ../.venv/bin/activate && python scripts/seed_test_data.py
"""
from __future__ import annotations

import sys
import os
import random
from datetime import datetime, timedelta

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_PROJECT_ROOT)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from src.db.connection import get_connection, close_all_connections
from src.db.schema import init_schema
from src.controllers.app_controller import AppController


def seed(controller: AppController) -> None:
    today = datetime.now()
    d = lambda offset=0: (today + timedelta(days=offset)).strftime("%Y-%m-%d")
    dt = lambda offset=0: (today + timedelta(days=offset)).strftime("%Y-%m-%d %H:%M:%S")

    ctrl = controller

    # ── 1. 技术员 ──────────────────────────────────────────────
    techs = []
    for name, emp_id, role, dept in [
        ("张伟", "EMP001", "高级测试工程师", "测试部"),
        ("李娜", "EMP002", "DQE", "质量部"),
        ("王磊", "EMP003", "测试员", "测试部"),
        ("赵敏", "EMP004", "QE", "质量部"),
        ("陈刚", "EMP005", "实验室主管", "测试部"),
    ]:
        tid = ctrl.technician_service.create(
            name=name, employee_id=emp_id, role=role, department=dept,
            phone="138" + f"{random.randint(10000000, 99999999)}",
            email=f"{emp_id.lower()}@example.com",
        )
        techs.append(tid)
    print(f"  技术员: {len(techs)} 条")

    # ── 2. 设备 ────────────────────────────────────────────────
    equips = []
    for name, etype, model, mfr, loc, cal_offset in [
        ("高低温试验箱 A", "环境试验箱", "GDW-1000L", "重庆银河", "A区-01", -30),
        ("高低温试验箱 B", "环境试验箱", "GDW-500L", "重庆银河", "A区-02", -60),
        ("冷热冲击试验箱", "冷热冲击箱", "TS-80", "爱斯佩克", "A区-03", -90),
        ("电磁振动台", "振动台", "VT-1000", "苏试", "B区-01", -120),
        ("跌落试验机", "跌落机", "DT-500", "高铁检测", "B区-02", -150),
        ("恒温恒湿箱", "恒温恒湿箱", "THS-800", "宏展", "A区-04", -45),
        ("盐雾试验箱", "盐雾箱", "YW-400", "联往", "C区-01", -20),
        ("万能材料试验机", "拉力机", "UTM-50KN", "三思", "B区-03", -180),
    ]:
        eid = ctrl.equipment_service.create(
            name=name, type=etype, model=model, manufacturer=mfr, location=loc,
            asset_no=f"EQ-{len(equips)+1:03d}",
            calibration_date=d(cal_offset),
            next_calibration_date=d(cal_offset + 365),
            calibration_interval_months=12,
            accuracy="±0.5°C" if "温" in name or "湿" in name else "±1%",
        )
        equips.append(eid)
    print(f"  设备: {len(equips)} 条")

    # ── 3. 项目 ────────────────────────────────────────────────
    projects = []
    proj_data = [
        ("ECU控制器可靠性验证", "ECU-V2", "长安汽车", "新一代车载ECU控制器全系列可靠性验证", "active"),
        ("动力电池模组测试", "BATT-PACK-75Ah", "宁德时代", "75Ah磷酸铁锂电池模组环境与安全测试", "active"),
        ("车载显示屏耐久性测试", "LCD-12.3INCH", "京东方", "12.3英寸车载中控屏耐久性验证", "active"),
        ("传感器模组 HALT 测试", "SENSOR-2026", "博世", "压力传感器高加速寿命测试", "paused"),
        ("连接器振动温循测试", "CONN-HD50", "安波福", "50pin 高速连接器振动+温循综合测试", "closed"),
    ]
    for name, product, customer, desc, status in proj_data:
        pid = ctrl.project_service.create(
            name=name, product=product, customer=customer,
            description=desc, status=status,
        )
        projects.append(pid)
    print(f"  项目: {len(projects)} 条")

    # ── 4. 样品 ────────────────────────────────────────────────
    samples = []
    sn_counter = 1000
    for pid_idx, pid in enumerate(projects[:3]):  # 前3个项目有样品
        proj_name = proj_data[pid_idx][0]
        for i in range(5):
            sn_counter += 1
            batch = f"B2026-{pid_idx+1:02d}-{random.randint(1,9)}"
            status = random.choice(["in_stock", "in_stock", "checked_out", "in_test", "in_stock"])
            sid = ctrl.sample_service.create(
                sn=f"SN-{sn_counter:05d}",
                batch_no=batch,
                spec=proj_data[pid_idx][1] + f"-Rev{chr(65+i)}",
                project_id=pid,
                status=status,
                location=f"样品柜{pid_idx+1}-{i+1:02d}",
                supplier=proj_data[pid_idx][2],
                notes=f"{proj_name}第{i+1}号样品",
            )
            samples.append((sid, pid))
    print(f"  样品: {len(samples)} 条")

    # ── 5. 测试计划 + 任务 ────────────────────────────────────
    plans = []
    task_ids = []
    plan_configs = [
        # (proj_idx, name, standard, phase, tasks)
        (0, "ECU高温寿命验证计划", "MIL-STD-810H", "P3", [
            ("高温存储试验", "环境试验", 5, 2, "150°C, 1000h", "", "外观无变化,电性能合格", 1),
            ("温度循环试验", "环境试验", 3, 3, "-40°C~125°C, 100 cycles", "", "无开裂/脱层", 1),
            ("湿热试验", "环境试验", 4, 2, "85°C/85%RH, 500h", "85%RH", "绝缘电阻>100MΩ", 2),
            ("冷热冲击试验", "环境试验", 2, 4, "-40°C↔125°C, 50 cycles", "", "功能正常", 1),
            ("振动试验-正弦", "机械试验", 3, 5, "5-500Hz, 2g, X/Y/Z三轴", "", "结构完整,焊点无裂纹", 2),
            ("机械冲击试验", "机械试验", 1, 6, "30g, 11ms, 半正弦", "", "无机械损伤", 3),
        ]),
        (0, "ECU电磁兼容预测试", "ISO 11452", "P2", [
            ("辐射发射测试", "EMC测试", 3, 1, "150kHz-1GHz", "", "CISPR 25 Class 5", 1),
            ("传导抗扰度", "EMC测试", 2, 2, "BCI 100mA", "", "功能无异常", 1),
        ]),
        (1, "电池模组安全测试计划", "GB/T 31485", "P3", [
            ("过充试验", "安全试验", 1, 1, "1.5倍额定电压", "", "不起火不爆炸", 1),
            ("短路试验", "安全试验", 1, 2, "外部短路<5mΩ", "", "不起火不爆炸", 1),
            ("热失控扩展测试", "安全试验", 2, 3, "针刺+加热", "", "5min内无明火", 1),
            ("跌落试验", "机械试验", 1, 5, "1m自由跌落,6面", "", "无泄漏/变形", 3),
        ]),
        (2, "显示屏环境耐久测试", "IEC 60068", "P3", [
            ("高低温运行试验", "环境试验", 5, 1, "-30°C~85°C 运行", "", "显示正常", 1),
            ("UV老化试验", "表面处理", 7, 2, "UV-A 340nm, 1000h", "", "色差ΔE<3", 2),
            ("耐磨试验", "表面处理", 3, 3, "Taber 500g/1000次", "", "透光率变化<5%", 2),
        ]),
    ]

    for proj_idx, plan_name, standard, phase, tasks in plan_configs:
        pid = projects[proj_idx]
        start_off = random.randint(-30, -10)
        plan_id = ctrl.test_plan_service.create_plan(
            project_id=pid, name=plan_name, test_standard=standard,
            start_date=d(start_off), end_date=d(start_off + 60),
            status="in_progress", apqp_phase=phase,
        )
        plans.append(plan_id)

        for idx, (tname, cat, dur, sday, temp, hum, criteria, prio) in enumerate(tasks):
            # 分配设备和人员
            equip_id = equips[idx % len(equips)]
            tech_id = techs[idx % len(techs)]
            # 取该项目的前几个样品
            proj_samples = [s[0] for s in samples if s[1] == pid]
            sids = proj_samples[:3] if proj_samples else []

            # 状态随机
            statuses = ["pending", "in_progress", "completed", "completed", "in_progress"]
            t_status = statuses[idx % len(statuses)]

            tid = ctrl.test_plan_service.create_task(
                plan_id=plan_id, name=tname, category=cat,
                test_standard=f"{standard} §{idx+1}.{random.randint(1,9)}",
                technician_id=tech_id, equipment_id=equip_id,
                sample_ids=str(sids),
                duration=dur, start_day=sday,
                progress=100.0 if t_status == "completed" else (random.uniform(20, 80) if t_status == "in_progress" else 0.0),
                status=t_status, priority=prio,
                temperature=temp, humidity=hum,
                accept_criteria=criteria,
                sort_order=idx,
            )
            task_ids.append((tid, plan_id, pid, tech_id, sids, t_status))

    print(f"  测试计划: {len(plans)} 条")
    print(f"  测试任务: {len(task_ids)} 条")

    # ── 6. 测试结果 ────────────────────────────────────────────
    result_count = 0
    for tid, plan_id, pid, tech_id, sids, t_status in task_ids:
        if t_status == "completed" and sids:
            for sid in sids[:2]:
                r = random.choice(["pass", "pass", "pass", "pass", "fail"])
                ctrl.test_plan_service.save_result(
                    task_id=tid, sample_id=sid, result=r,
                    test_date=d(random.randint(-20, -1)),
                    measured_value=f"{random.uniform(0.1, 99.9):.2f}" if r == "pass" else "FAIL",
                    notes="符合标准要求" if r == "pass" else "超出规格限",
                    tester_id=tech_id,
                    environment='{"temp":"' + str(random.randint(-40, 125)) + '°C"}',
                )
                result_count += 1
        elif t_status == "in_progress" and sids:
            # 只填部分结果
            sid = sids[0]
            ctrl.test_plan_service.save_result(
                task_id=tid, sample_id=sid, result="pending",
                test_date="", notes="测试进行中",
                tester_id=tech_id,
            )
            result_count += 1
    print(f"  测试结果: {result_count} 条")

    # ── 7. Issue + FA + CAPA ───────────────────────────────────
    issues = []
    issue_data = [
        ("ECU高温存储外壳变色", "外观异常", "1000h高温后", "critical", "open", 1,
         "壳体表面出现明显黄变", "材料耐温等级不足",
         "更换耐高温材料,壳体增加散热涂层",
         "料"),
        ("电池模组过充保护失效", "功能失效", "1.5C过充时", "critical", "analyzing", 2,
         "BMS过充保护未触发", "BMS固件版本过旧,过充阈值设置偏高",
         "升级BMS固件,调低过充阈值至4.25V/cell",
         "法"),
        ("显示屏UV老化后色差超标", "性能降级", "800h UV照射后", "major", "open", 2,
         "色差ΔE达到5.2(标准<3)", "偏光片UV耐候性不足",
         "更换UV级偏光片,增加表面UV涂层",
         "料"),
        ("振动试验焊点裂纹", "结构失效", "Z轴振动2h后", "major", "verified", 1,
         "BGA焊点出现裂纹", "焊锡膏成分不达标,回流曲线需优化",
         "更换SAC305焊锡膏,调整回流温度曲线",
         "法"),
        ("传感器零点漂移", "精度异常", "HALT 48h后", "minor", "closed", 3,
         "零点偏移超过±2%FS", "封装应力导致芯片微变形",
         "增加封装前退火工序,优化点胶工艺",
         "环"),
        ("连接器插拔力偏大", "装配异常", "首次装配时", "minor", "closed", 4,
         "插拔力达8N(标准<5N)", "端子过盈量设计过大",
         "减小端子过盈量0.02mm",
         "法"),
        ("ECU温循后绝缘下降", "电气异常", "50次温循后", "major", "analyzing", 1,
         "绝缘电阻降至50MΩ(标准>100MΩ)", "PCB基材吸湿导致绝缘劣化",
         "增加三防漆涂覆,优化PCB板材CTI等级",
         "料"),
    ]

    for title, mode, stage, sev, status, proj_idx, desc, root, resolution, cause_cat in issue_data:
        pid = projects[min(proj_idx, len(projects) - 1)]
        # 找该项目的任务和样品
        proj_tasks = [(t, s) for t, _, p, _, s, _ in task_ids if p == pid]
        t_id = proj_tasks[0][0] if proj_tasks else None
        proj_samples = [s[0] for s in samples if s[1] == pid]
        s_id = proj_samples[0] if proj_samples else None
        plan_id = next((p for p in plans if any(t[1] == p for t in task_ids if t[2] == pid)), None)

        iid = ctrl.issue_service.create(
            title=title, failure_mode=mode, failure_stage=stage,
            severity=sev, status=status, priority=random.randint(1, 3),
            project_id=pid, plan_id=plan_id, task_id=t_id, sample_id=s_id,
            description=desc, root_cause=root, resolution=resolution,
            failure_code=f"FM-{random.randint(100,999)}",
            occurrence_count=random.randint(1, 5),
            dri_name=random.choice(["张伟", "李娜", "赵敏"]),
            assignee_id=techs[proj_idx % len(techs)],
        )
        issues.append(iid)

        # FA 记录 (2-3步)
        fa_steps = [
            ("外观检查", "目视/放大镜", "观察失效部位外观特征", "发现异常区域", cause_cat, "疲劳断裂" if "裂纹" in desc else "性能退化"),
            ("切片分析/电测", "金相显微镜/电参数测试", "分析失效机理", "确认失效路径", cause_cat, "确认根因"),
        ]
        for step, (step_title, method, finding_desc, finding, cat, mech) in enumerate(fa_steps, 1):
            ctrl.issue_service.add_fa_record(
                issue_id=iid,
                step_no=step,
                step_title=step_title,
                description=method,
                method=method,
                findings=finding,
                possible_cause=root if step == 2 else "",
                cause_category=cat,
                failure_mechanism=mech,
                confirmed=1 if step == 2 else 0,
                analyst_id=techs[step % len(techs)],
            )

        # CAPA 记录
        if status in ("verified", "closed", "analyzing"):
            ctrl.issue_service.add_capa_record(
                issue_id=iid,
                action=resolution,
                assignee_name=random.choice(["张伟", "陈刚"]),
                due_date=d(random.randint(10, 30)),
                status="completed" if status == "closed" else "in_progress",
                root_cause=root,
                effectiveness="改善后复测合格" if status == "closed" else "",
                follow_up="持续监控3批次" if status == "closed" else "",
                verifier_name="李娜" if status != "analyzing" else "",
            )

    print(f"  Issue: {len(issues)} 条 (含 FA/CAPA)")

    # ── 8. 知识库 ──────────────────────────────────────────────
    knowledge = [
        ("焊点热疲劳失效", "焊接", "温度循环导致焊点热疲劳裂纹,典型表现为BGA/CSP焊点开裂。IPC-9701标准提供疲劳寿命预测方法。", "焊点,疲劳,BGA,温度循环,裂纹", "IPC-9701, MIL-STD-883"),
        ("电池热失控机理", "电池", "锂离子电池热失控通常由SEI膜分解起始(120°C),随后电解液分解(200°C),正极材料分解释氧(250°C+),最终导致起火爆炸。", "热失控,电池,安全,针刺,过充", "GB/T 31485, GB 38031"),
        ("盐雾腐蚀等级判定", "表面处理", "按ISO 9227中性盐雾试验后,依据表面腐蚀面积百分比评级。0级(无腐蚀)到5级(>40%腐蚀)。汽车外饰件要求≥4级(腐蚀<10%)。", "盐雾,腐蚀,表面处理,氧化,涂层", "ISO 9227, ASTM B117"),
        ("HASS/HALT 测试方法", "可靠性方法", "HALT(高加速寿命测试)通过快速温变+随机振动激发设计缺陷;HASS(高加速应力筛选)在生产阶段剔除早期缺陷。温变速率通常≥40°C/min。", "HALT,HASS,加速试验,可靠性,应力筛选", "IEC 62506, GMW3172"),
        ("连接器接触电阻劣化", "连接器", "连接器接触电阻劣化主要原因:接触面氧化、磨损、应力松弛、微动腐蚀。镀金层厚度需≥0.8μm保证耐久性。微动腐蚀在高振动环境下加剧。", "连接器,接触电阻,微动,氧化,磨损", "EIA-364, USCAR-2"),
        ("PCB CAF 生长机理", "PCB", "导电阳极丝(CAF)是PCB内部沿玻纤/树脂界面生长的铜丝,在偏压+湿度条件下缓慢生长,最终导致绝缘电阻下降甚至短路。高压(>48V)和高湿环境需特别关注。", "CAF,PCB,绝缘,短路,吸湿", "IPC-9691"),
    ]
    for title, category, content, keywords, refs in knowledge:
        ctrl.knowledge_service.create(
            title=title, category=category, content=content,
            keywords=keywords, references=refs,
        )
    print(f"  知识库: {len(knowledge)} 条")

    print("\n=== 测试数据生成完成 ===")


if __name__ == "__main__":
    conn = get_connection()
    init_schema(conn)
    ctrl = AppController()
    ctrl.initialize()
    seed(ctrl)
    close_all_connections()
