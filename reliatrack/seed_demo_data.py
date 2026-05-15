#!/usr/bin/env python3
"""生成 ReliaTrack 演示数据，覆盖所有模块各状态。"""

import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import apsw
from src.db.connection import get_connection
from src.db.schema import init_schema
from datetime import datetime, timedelta

DB = "data/reliatrack.db"
NOW = datetime.now()

conn = get_connection(DB)
init_schema(conn)
conn.execute("PRAGMA foreign_keys = OFF")  # 批量导入时关闭 FK 检查

def d(offset_days, h=8, m=0):
    """生成相对日期的 ISO 字符串。"""
    return (NOW + timedelta(days=offset_days)).strftime("%Y-%m-%d %H:%M:%S")

def date_str(offset_days):
    return (NOW + timedelta(days=offset_days)).strftime("%Y-%m-%d")

# ══════════════════════════════════════════════════════════════════════
# 1. 项目 (4个)
# ══════════════════════════════════════════════════════════════════════
projects = [
    (1, "BMS-3.0 电池管理系统", "BMS", "宁德时代", "第三代BMS可靠性验证", "active", d(-90), d(-30)),
    (2, "VCU-H 整车控制器改款", "VCU", "比亚迪", "高压平台升级后的DVP验证", "active", d(-60), d(-5)),
    (3, "MCU-P3 电机控制器", "MCU", "汇川科技", "SiC功率模块可靠性评估", "paused", d(-120), d(-60)),
    (4, "OBC-12 车载充电机", "OBC", "威迈斯", "12kW双向充电机DV验证", "active", d(-30), d(30)),
]
for p in projects:
    conn.execute("INSERT OR REPLACE INTO projects (id,name,product,customer,description,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)", p)

# ══════════════════════════════════════════════════════════════════════
# 2. 设备 (6台)
# ══════════════════════════════════════════════════════════════════════
equipment = [
    (1, "高低温试验箱", "环境试验", "GDW-500L", "A栋101室", "available", "EQ-2024-001", "重庆银河", "±0.5°C", "2025-01-15", "2026-01-15", 12, d(-365)),
    (2, "振动台", "力学试验", "VD-50T", "A栋102室", "available", "EQ-2024-002", "苏州东菱", "±2%", "2025-03-01", "2026-03-01", 12, d(-365)),
    (3, "三综合试验箱", "环境试验", "SZH-300L", "A栋103室", "maintenance", "EQ-2024-003", "重庆银河", "±0.8°C", "2024-06-01", "2025-06-01", 12, d(-400)),
    (4, "示波器", "电测", "MSO-58", "B栋201室", "available", "EQ-2025-001", "Tektronix", "±1%", "2025-05-01", "2025-11-01", 6, d(-200)),
    (5, "绝缘耐压仪", "电测", "TH-9201", "B栋202室", "available", "EQ-2025-002", "常州同惠", "±1.5%", "2025-02-01", "2026-02-01", 12, d(-300)),
    (6, "盐雾试验箱", "环境试验", "YW-1200L", "A栋104室", "offline", "EQ-2023-001", "广州爱斯佩克", "±1°C", "2023-06-01", "2024-06-01", 12, d(-500)),
]
for e in equipment:
    conn.execute("INSERT OR REPLACE INTO equipment (id,name,type,model,location,status,asset_no,manufacturer,accuracy,calibration_date,next_calibration_date,calibration_interval_months,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", e)

# ══════════════════════════════════════════════════════════════════════
# 3. 技术员 (5人)
# ══════════════════════════════════════════════════════════════════════
technicians = [
    (1, "陈工", "T-001", "高级工程师", "可靠性部", "13800001111", "chen@reliatrack.com", d(-365)),
    (2, "李磊", "T-002", "工程师", "测试部", "13800002222", "lilei@reliatrack.com", d(-180)),
    (3, "王芳", "T-003", "工程师", "环境室", "13800003333", "wangfang@reliatrack.com", d(-240)),
    (4, "张强", "T-004", "助理工程师", "测试部", "13800004444", "zhangq@reliatrack.com", d(-60)),
    (5, "赵敏", "T-005", "技术员", "电测室", "13800005555", "zhaom@reliatrack.com", d(-90)),
]
for t in technicians:
    conn.execute("INSERT OR REPLACE INTO technicians (id,name,employee_id,role,department,phone,email,created_at) VALUES (?,?,?,?,?,?,?,?)", t)

# ══════════════════════════════════════════════════════════════════════
# 4. 样品 (15个)
# ══════════════════════════════════════════════════════════════════════
samples = [
    (1, "BMS-001-A", "BATCH-2401", "BMS v3.0 主控板", 1, "in_stock", "C04架3层", 0.0, "", "", "供应商A", "", d(-90)),
    (2, "BMS-002-A", "BATCH-2401", "BMS v3.0 从控板", 1, "checked_out", "A栋101", 168.5, "", "", "供应商A", "", d(-90)),
    (3, "BMS-003-A", "BATCH-2401", "BMS v3.0 高压板", 1, "in_test", "高低温箱3#", 120.0, "", "", "供应商A", "", d(-90)),
    (4, "VCU-001-B", "BATCH-2402", "VCU-H 主控板", 2, "in_test", "振动台1#", 48.0, "", "", "供应商B", "", d(-60)),
    (5, "VCU-002-B", "BATCH-2402", "VCU-H 电源板", 2, "in_stock", "C05架1层", 0.0, "", "", "供应商B", "", d(-60)),
    (6, "MCU-001-C", "BATCH-2301", "MCU-P3 功率板", 3, "suspended", "仓库D", 200.0, "", "", "供应商C", "SiC模块来料异常", d(-120)),
    (7, "MCU-002-C", "BATCH-2301", "MCU-P3 驱动板", 3, "scrapped", "报废区", 320.0, "", "", "供应商C", "功率管击穿失效", d(-120)),
    (8, "OBC-001-D", "BATCH-2403", "OBC-12 功率板", 4, "in_stock", "C06架2层", 0.0, "", "", "供应商D", "", d(-30)),
    (9, "OBC-002-D", "BATCH-2403", "OBC-12 控制板", 4, "checked_out", "电测室", 24.0, "", "", "供应商D", "", d(-30)),
    (10, "BMS-004-B", "BATCH-2401", "BMS v3.0 采集板", 1, "returned", "A栋201", 72.0, "", "", "供应商E", "", d(-90)),
    (11, "VCU-003-B", "BATCH-2402", "VCU-H 接口板", 2, "in_test", "盐雾箱", 96.0, "", "", "供应商B", "", d(-60)),
    (12, "BMS-005-B", "BATCH-2404", "BMS v3.0 样机#1", 1, "in_stock", "C04架1层", 0.0, "", "", "供应商A", "", d(-15)),
    (13, "BMS-006-B", "BATCH-2404", "BMS v3.0 样机#2", 1, "in_stock", "C04架1层", 0.0, "", "", "供应商A", "", d(-15)),
    (14, "OBC-003-D", "BATCH-2403", "OBC-12 辅助源板", 4, "in_test", "高低温箱1#", 36.0, "", "", "供应商D", "", d(-30)),
    (15, "OBC-004-D", "BATCH-2403", "OBC-12 整机", 4, "in_stock", "C06架3层", 0.0, "", "", "供应商D", "", d(-30)),
]
for s in samples:
    conn.execute("INSERT OR REPLACE INTO samples (id,sn,batch_no,spec,project_id,status,location,test_hours,qr_code,notes,supplier,scrapped_reason,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", s)

# 样品出入库记录
transactions = [
    (1, 2, "check_out", 1, "高温老化测试-项目1", 1, date_str(-30), date_str(-28), "", d(-30)),
    (2, 2, "return", 1, "高温老化归还", None, "", date_str(-28), "168h完成", d(-28)),
    (3, 3, "check_out", 1, "高温老化测试-样机2", 1, date_str(-30), "", "", d(-30)),
    (4, 9, "check_out", 5, "电性能测试", 4, date_str(-5), "", "", d(-5)),
    (5, 11, "check_out", 3, "盐雾试验", 4, date_str(-10), "", "", d(-10)),
    (6, 14, "check_out", 3, "温度循环测试", 3, date_str(-7), "", "", d(-7)),
]
for tx in transactions:
    conn.execute("INSERT OR REPLACE INTO sample_transactions (id,sample_id,type,operator_id,purpose,related_task_id,expected_return,actual_return,notes,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)", tx)

# ══════════════════════════════════════════════════════════════════════
# 5. 测试计划 (4个)
# ══════════════════════════════════════════════════════════════════════
plans = [
    (1, 1, "BMS-3.0 DVP&R 完整验证", "GB/T 38046-2023", date_str(-85), date_str(-5), "in_progress", "DVP&R", d(-85), d(-30)),
    (2, 2, "VCU-H 功能可靠性测试", "QC/T 1088-2023", date_str(-55), date_str(10), "in_progress", "DVP&R", d(-55), d(-10)),
    (3, 3, "MCU-P3 SiC 专项评估", "IEC 60747-9", date_str(-100), date_str(-60), "paused", "设计验证", d(-100), d(-60)),
    (4, 4, "OBC-12 DV 验证", "ISO 26262", date_str(-25), date_str(35), "in_progress", "DVP&R", d(-25), d(0)),
]
for p in plans:
    conn.execute("INSERT OR REPLACE INTO test_plans (id,project_id,name,test_standard,start_date,end_date,status,apqp_phase,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)", p)

# ══════════════════════════════════════════════════════════════════════
# 6. 测试任务 (12个)
# ══════════════════════════════════════════════════════════════════════
tasks = [
    (1, 1, "高温工作寿命测试(HTOL)", "环境", "GB/T 38046-2023 §5.2", 1, 1, json.dumps([2,3]), 168, 0, 100.0, "completed", 1, '{"temp":85,"humidity":50}', "", json.dumps([]), "85°C/50%RH 额定电压持续工作", "", "", "±10%输出电压偏差", 1, date_str(-80), date_str(-70), d(-85), d(-70)),
    (2, 1, "低温启动测试", "环境", "GB/T 38046-2023 §5.3", 1, 1, json.dumps([3]), 72, 3, 100.0, "completed", 2, '{"temp":-40}', "", json.dumps([1]), "-40°C存储后开机", "", "", "正常启动无故障", 2, date_str(-80), date_str(-70), d(-85), d(-70)),
    (3, 1, "温度循环测试(TC)", "环境", "GB/T 38046-2023 §5.4", 3, 1, json.dumps([2]), 240, 5, 65.0, "in_progress", 1, '{"temp_high":85,"temp_low":-40,"cycles":500}', "", json.dumps([1,2]), "500次温度循环(-40↔85°C)", "", "", "功能全程正常", 3, date_str(-60), "", d(-60), d(-30)),
    (4, 1, "随机振动测试", "力学", "GB/T 38046-2023 §5.5", 2, 2, json.dumps([3]), 8, 0, 100.0, "completed", 1, '{"psd":"0.01g²/Hz","freq":"10-2000Hz"}', "", json.dumps([]), "三轴向随机振动X/Y/Z各2h", "", "", "无机械损伤", 4, date_str(-75), date_str(-70), d(-80), d(-70)),
    (5, 1, "绝缘耐压测试", "电测", "GB/T 38046-2023 §5.6", 5, 5, json.dumps([1,2,3]), 1, 0, 100.0, "completed", 2, '{"voltage":2500}', "", json.dumps([]), "2500V AC 1min 漏电流<5mA", "", "", "漏电流<5mA", 5, date_str(-85), date_str(-85), d(-85), d(-85)),
    (6, 2, "VCU 高低温工作测试", "环境", "QC/T 1088-2023 §4.1", 1, 1, json.dumps([4,11]), 168, 0, 40.0, "in_progress", 1, '{"temp":85}', "", json.dumps([]), "高温85°C 额定电压168h", "", "", "功能正常", 6, date_str(-20), "", d(-30), d(-10)),
    (7, 2, "VCU 振动耐久测试", "力学", "QC/T 1088-2023 §4.2", 2, 2, json.dumps([4]), 24, 2, 10.0, "in_progress", 2, '{"psd":"0.02g²/Hz"}', "", json.dumps([6]), "24h 随机振动", "", "", "无损坏", 7, date_str(-15), "", d(-20), d(-10)),
    (8, 2, "VCU 盐雾测试", "环境", "QC/T 1088-2023 §4.3", 3, 6, json.dumps([11]), 96, 4, 30.0, "in_progress", 3, '{"concentration":"5%"}', "", json.dumps([]), "96h 中性盐雾", "", "", "腐蚀面积<5%", 8, date_str(-10), "", d(-12), d(-5)),
    (9, 4, "OBC 效率测试", "电测", "ISO 26262 §8", 4, 4, json.dumps([8,9,14,15]), 8, 0, 0.0, "pending", 2, '{"load":"0-100%"}', "", json.dumps([]), "全负载范围效率曲线", "", "", "满载效率>94%", 9, "", "", d(-5), d(-2)),
    (10, 4, "OBC 保护功能测试", "电测", "ISO 26262 §9", 5, 5, json.dumps([9]), 4, 1, 0.0, "pending", 1, '{"overvoltage":1}', "", json.dumps([9]), "过压/过流/过温保护", "", "", "保护动作正常", 10, "", "", d(-3), d(-2)),
    (11, 4, "OBC 温度循环测试", "环境", "ISO 26262 §10", 3, 1, json.dumps([14]), 120, 3, 0.0, "pending", 3, '{"cycles":200}', "", json.dumps([]), "200次温度循环", "", "", "无损坏", 11, "", "", d(-3), d(-2)),
    (12, 3, "MCU SiC 高温反偏测试(HTRB)", "环境", "IEC 60747-9", 1, 1, json.dumps([6]), 1000, 0, 50.0, "paused", 1, '{"vds":800,"temp":150}', "", json.dumps([]), "1000h 高温反偏", "", "", "漏电流<100μA", 12, date_str(-100), date_str(-60), d(-100), d(-60)),
]
for t in tasks:
    conn.execute("""INSERT OR REPLACE INTO test_tasks 
    (id,plan_id,name,category,test_standard,technician_id,equipment_id,sample_ids,duration,start_day,progress,
     status,priority,environment,log_file,dependencies,notes,temperature,humidity,accept_criteria,sort_order,
     actual_start_date,actual_end_date,created_at,updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", t)

# ══════════════════════════════════════════════════════════════════════
# 7. 测试结果 (8条)
# ══════════════════════════════════════════════════════════════════════
results = [
    (1, 1, 2, "pass", date_str(-75), 1, '{"temp":85,"humidity":50}', "168h 全程正常，输出电压稳定5.01V±0.02V", "[]", "5.01V", d(-75)),
    (2, 1, 3, "pass", date_str(-75), 1, '{"temp":85,"humidity":50}', "168h 通过，纹波<50mV", "[]", "4.98V", d(-75)),
    (3, 2, 3, "pass", date_str(-72), 1, '{"temp":-40}', "-40°C 存储后正常启动", "[]", "正常", d(-72)),
    (4, 4, 3, "pass", date_str(-73), 2, '{"psd":"0.01g²/Hz"}', "三轴向振动后功能正常", "[]", "通过", d(-73)),
    (5, 5, 1, "pass", date_str(-85), 5, '{"voltage":2500}', "2500V 1min 漏电流1.2mA", "[]", "1.2mA", d(-85)),
    (6, 5, 2, "pass", date_str(-85), 5, '{"voltage":2500}', "2500V 1min 漏电流0.8mA", "[]", "0.8mA", d(-85)),
    (7, 5, 3, "fail", date_str(-85), 5, '{"voltage":2500}', "漏电流8.5mA 超限！检查发现绝缘片有划痕", "[]", "8.5mA", d(-85)),
    (8, 1, 3, "conditional", date_str(-30), 1, '{"temp_high":85,"temp_low":-40}', "150次循环后功能正常，但连接器有轻微氧化", "[]", "条件通过", d(-30)),
]
for r in results:
    conn.execute("INSERT OR REPLACE INTO test_results (id,task_id,sample_id,result,test_date,tester_id,environment,notes,attachments,measured_value,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)", r)

# ══════════════════════════════════════════════════════════════════════
# 8. Issues (6个)
# ══════════════════════════════════════════════════════════════════════
issues = [
    (1, 1, 1, 5, 3, "绝缘耐压测试失败 — 绝缘片划痕",
     "绝缘失效", "电性能测试", "BMS高压板在2500V耐压测试中漏电流8.5mA远超5mA限值，检查发现绝缘片有机械划痕",
     "major", "open", 1, "ME",
     "绝缘片供应商来料划痕", "更换绝缘片后重测通过",
     "陈工", "INS-001", 1, d(-85), d(-30)),
    (2, 1, 1, 1, 3, "温度循环后连接器氧化",
     "接触不良", "环境测试", "250次温度循环后，连接器端子表面发现轻微氧化，影响接触电阻",
     "minor", "analyzing", 2, "ME",
     "连接器镀层不足（厂商材料变更未通知）", "评估中",
     "陈工", "TC-001", 2, d(-40), d(-5)),
    (3, 2, 2, 8, 11, "盐雾测试72h后外观异常",
     "腐蚀", "环境测试", "VCU接口板在盐雾测试72h后，接口端子出现绿色腐蚀产物，不满足96h要求",
     "major", "analyzing", 1, "ME",
     "端子材料未使用不锈钢", "更改为不锈钢端子",
     "王芳", "SALT-001", 2, d(-8), d(-3)),
    (4, 1, 1, 3, 2, "样品#2 温度循环后数据异常",
     "参数超差", "环境测试", "样品#2在300次温度循环后，输出电压偏差达到8%（限值±5%）",
     "major", "open", 2, "EE",
     "采样电阻温漂过大", "待分析",
     "李磊", "TC-002", 1, d(-25), d(-10)),
    (5, 3, 3, 12, 6, "SiC 模块HTRB测试异常",
     "漏电流超标", "环境测试", "SiC MOSFET在HTRB测试500h后漏电流从10μA升至80μA，接近限值",
     "critical", "open", 1, "EE",
     "晶格缺陷在高温高偏压下扩展", "与供应商联合分析中",
     "陈工", "SiC-001", 1, d(-100), d(-60)),
    (6, 4, 4, 9, 8, "OBC 效率裕量不足",
     "参数超差", "电性能测试", "仿真显示满载效率93.2%，未达到94%目标值，需优化驱动参数",
     "major", "open", 3, "EE",
     "死区时间设置偏保守", "已调整驱动时序",
     "张强", "OBC-EFF-001", 1, d(-10), d(-3)),
]
for iss in issues:
    conn.execute("""INSERT OR REPLACE INTO issues 
    (id,project_id,plan_id,task_id,sample_id,title,failure_mode,failure_stage,description,
     severity,status,priority,category,root_cause,resolution,
     reporter_name,failure_code,occurrence_count,created_at,updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", iss)

# ══════════════════════════════════════════════════════════════════════
# 9. 知识库 (4条)
# ══════════════════════════════════════════════════════════════════════
knowledge = [
    (1, "环境测试", "高温老化失效", "电容ESR增大导致输出纹波超标", "更换高温级电容（125°C规格）", "GB/T 38046-2023 §5.2",
     json.dumps(["高温", "老化", "电容", "ESR"]), "高温老化测试常见失效分析及对策",
     "电容在高温下电解液蒸发加速，导致ESR增大", "更换为固态电容或高温电解电容",
     json.dumps([1]), d(-200)),
    (2, "力学测试", "振动失效", "夹具共振放大导致焊点开裂", "优化夹具设计，增加阻尼材料", "GB/T 2423.56-2018",
     json.dumps(["振动", "焊点", "夹具", "共振"]), "振动测试夹具设计规范与注意事项",
     "夹具一阶共振频率应在测试频率范围以上", "使用有限元分析优化夹具刚度",
     json.dumps([4]), d(-180)),
    (3, "电测", "绝缘失效", "PCB 爬电距离不足导致闪络", "增加绝缘槽/使用三防漆", "GB/T 16935.1-2023",
     json.dumps(["绝缘", "爬电距离", "PCB", "闪络"]), "高压PCB绝缘设计指南",
     "海拔/污染等级/材料组别影响爬电距离要求", "设计阶段进行绝缘距离复核",
     json.dumps([1, 5]), d(-150)),
    (4, "工艺", "连接器退化", "连接器镀层磨损导致接触电阻增大", "增加插拔次数验证，选择高耐久度连接器", "QC/T 1088-2023 §4.5",
     json.dumps(["连接器", "镀层", "接触电阻", "插拔"]), "连接器选型与可靠性验证",
     "镀金层厚度应≥0.76μm（30μinch）", "确认供应商镀层工艺稳定性",
     json.dumps([2, 3]), d(-100)),
]
for k in knowledge:
    conn.execute("""INSERT OR REPLACE INTO knowledge_entries 
    (id,category,failure_mode,cause_analysis,improvement,reference_standard,
     keywords,summary,root_cause,resolution,related_issues,created_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", k)

# ══════════════════════════════════════════════════════════════════════
# 10. 节假日 (内置2026年节假日)
# ══════════════════════════════════════════════════════════════════════
from src.db.schema import _SEED_HOLIDAYS_2025, _SEED_HOLIDAYS_2026
for h in _SEED_HOLIDAYS_2025 + _SEED_HOLIDAYS_2026:
    conn.execute("INSERT OR IGNORE INTO holidays (date, name, source) VALUES (?, ?, 'builtin')", (h[0], h[1]))

# 设置
settings_data = [
    ("daily_start_limit", "3"),
    ("default_temperature", "25"),
    ("last_plan_id", "1"),
]
for k, v in settings_data:
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, v))

conn.close()

# ── 验证 ──
v = apsw.Connection(DB)
tables = ["projects","equipment","technicians","samples","sample_transactions",
          "test_plans","test_tasks","test_results","issues","knowledge_entries","settings"]
total = 0
for t in tables:
    cnt = list(v.execute(f"SELECT COUNT(*) FROM [{t}]"))[0][0]
    total += cnt
    print(f"  {t}: {cnt}")
print(f"\n✅ 总计 {total} 行数据写入完毕")
v.close()
