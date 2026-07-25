"""可靠性测试类型模板 — 覆盖常见环境/机械/寿命/表面测试。

每种测试类型预定义：名称、类别、引用标准、环境条件默认值、
典型工期、建议样品数、常见判定准则。

用途：TaskEditDialog 选择测试类型后自动填充任务字段。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TestTypeTemplate:
    """单个测试类型模板。"""
    __test__ = False

    name: str                          # 显示名称（中文）
    category: str                      # 对应 _CATEGORIES 之一
    test_standard: str = ""            # 引用标准号
    duration: int = 1                  # 典型工期（工作日）
    temperature: str = ""              # 默认温度条件
    humidity: str = ""                 # 默认湿度条件
    environment: str = ""              # JSON 环境条件（兼容旧字段）
    suggested_samples: int = 5         # 建议样品数
    accept_criteria: str = ""          # 判定准则描述
    notes: str = ""                    # 默认备注/说明
    keywords: list[str] = field(default_factory=list)  # 搜索关键词


# ═══════════════════════════════════════════════════════════════════
#  环境试验
# ═══════════════════════════════════════════════════════════════════

TEMPLATES: list[TestTypeTemplate] = [
    # ── 高温 ──
    TestTypeTemplate(
        name="高温存储 (HTS)",
        category="环境试验",
        test_standard="IEC 60068-2-2 / GB/T 2423.2",
        duration=30,
        temperature="85°C",
        humidity="",
        suggested_samples=5,
        accept_criteria="C=0 (全部通过)",
        notes="稳态高温，连续放置至规定时间后检测功能/外观",
        keywords=["高温", "HTS", "高温存储", "高温寿命", "heat", "storage"],
    ),
    TestTypeTemplate(
        name="高温寿命 (HTOL)",
        category="环境试验",
        test_standard="JESD22-A108 / MIL-STD-883 1005",
        duration=60,
        temperature="125°C / 150°C",
        humidity="",
        suggested_samples=77,
        accept_criteria="按 TMCL 计算，失效数≤允许数",
        notes="加电高温老化寿命测试，用于评估 MTBF",
        keywords=["HTOL", "高温老化", "寿命", "老化", "burn-in"],
    ),

    # ── 低温 ──
    TestTypeTemplate(
        name="低温存储",
        category="环境试验",
        test_standard="IEC 60068-2-1 / GB/T 2423.1",
        duration=5,
        temperature="-40°C",
        humidity="",
        suggested_samples=5,
        accept_criteria="C=0 (全部通过)",
        notes="稳态低温存储，检测材料脆化/功能异常",
        keywords=["低温", "冷存储", "cold", "low temperature"],
    ),

    # ── 温循 ──
    TestTypeTemplate(
        name="温度循环 (TC)",
        category="环境试验",
        test_standard="IEC 60068-2-14 / GB/T 2423.22 Na",
        duration=7,
        temperature="-40°C ~ 85°C",
        humidity="",
        suggested_samples=5,
        accept_criteria="C=0 (全部通过), 常见 100/200/500 cycles",
        notes="温度变化速率 10~15°C/min，驻留时间 15~30min",
        keywords=["温循", "TC", "温度循环", "thermal cycle", "温度冲击"],
    ),
    TestTypeTemplate(
        name="快速温变 (TS)",
        category="环境试验",
        test_standard="IEC 60068-2-14 / GB/T 2423.22 Nb",
        duration=5,
        temperature="-40°C ~ 125°C",
        humidity="",
        suggested_samples=5,
        accept_criteria="C=0 (全部通过), 常见 20~50 cycles",
        notes="温变率≥15°C/min，考核焊点/封装可靠性",
        keywords=["快速温变", "TS", "thermal shock", "温度冲击"],
    ),

    # ── 恒温恒湿 ──
    TestTypeTemplate(
        name="恒温恒湿 (THB)",
        category="环境试验",
        test_standard="IEC 60068-2-78 / GB/T 2423.50",
        duration=14,
        temperature="85°C",
        humidity="85%RH",
        suggested_samples=5,
        accept_criteria="C=0 (全部通过)",
        notes="85°C/85%RH，常用于评估封装/PCB 耐潮湿性能",
        keywords=["恒温恒湿", "THB", "85/85", "湿热", "damp heat"],
    ),
    TestTypeTemplate(
        name="高加速寿命试验 (HALT)",
        category="环境试验",
        test_standard="IEC 62506 / GB/T 34986",
        duration=5,
        temperature="起始 20°C, 每步 +10°C 至失效",
        humidity="",
        suggested_samples=5,
        accept_criteria="记录失效温度和模式，无固定判定",
        notes="找出设计极限和破坏极限，非 pass/fail 测试",
        keywords=["HALT", "高加速寿命", "步进应力", "设计极限"],
    ),
    TestTypeTemplate(
        name="高加速应力筛选 (HASS)",
        category="环境试验",
        test_standard="IEC 62506 / GB/T 34986",
        duration=2,
        temperature="基于 HALT 结果设定（通常极限的 80%~90%）",
        humidity="",
        suggested_samples=10,
        accept_criteria="C=0 (全部通过)",
        notes="量产筛选，通常 HALT 确定条件后执行",
        keywords=["HASS", "HASS", "筛选", "stress screen"],
    ),

    # ── 盐雾 ──
    TestTypeTemplate(
        name="盐雾试验",
        category="表面处理",
        test_standard="ISO 9227 / GB/T 10125",
        duration=5,
        temperature="35°C",
        humidity="",
        suggested_samples=3,
        accept_criteria="按产品规格（如白锈/红锈等级）",
        notes="NSS 中性盐雾 / CASS 铜加速盐雾 / ASS 乙酸盐雾",
        keywords=["盐雾", "NSS", "CASS", "腐蚀", "salt spray"],
    ),

    # ── UV 老化 ──
    TestTypeTemplate(
        name="UV 老化",
        category="表面处理",
        test_standard="ISO 4892-3 / GB/T 16422.3",
        duration=30,
        temperature="60°C (UVA-340)",
        humidity="50%RH",
        suggested_samples=3,
        accept_criteria="按产品规格（色差ΔE / 光泽度衰减 / 粉化等级）",
        notes="模拟太阳光 UV 段，评估材料耐候性",
        keywords=["UV", "老化", "紫外", "耐候", "weathering"],
    ),

    # ═══════════════════════════════════════════════════════════════
    #  机械试验
    # ═══════════════════════════════════════════════════════════════

    TestTypeTemplate(
        name="随机振动",
        category="机械试验",
        test_standard="IEC 60068-2-64 / GB/T 2423.56",
        duration=1,
        temperature="",
        humidity="",
        suggested_samples=5,
        accept_criteria="C=0 (全部通过)",
        notes="宽带随机振动，常见 5~500Hz, 0.04~0.4 g²/Hz PSD",
        keywords=["振动", "随机振动", "random vibration", "PSD"],
    ),
    TestTypeTemplate(
        name="正弦振动",
        category="机械试验",
        test_standard="IEC 60068-2-6 / GB/T 2423.10",
        duration=1,
        temperature="",
        humidity="",
        suggested_samples=5,
        accept_criteria="C=0 (全部通过)",
        notes="扫频正弦振动，10~500~10Hz, 0.5~2g, 1 oct/min",
        keywords=["正弦振动", "sine vibration", "扫频"],
    ),
    TestTypeTemplate(
        name="机械冲击",
        category="机械试验",
        test_standard="IEC 60068-2-27 / GB/T 2423.5",
        duration=1,
        temperature="",
        humidity="",
        suggested_samples=5,
        accept_criteria="C=0 (全部通过)",
        notes="半正弦波，常见 30g/11ms / 50g/11ms, 三轴六向",
        keywords=["冲击", "机械冲击", "shock", "半正弦"],
    ),
    TestTypeTemplate(
        name="自由跌落",
        category="包装",
        test_standard="IEC 60068-2-31 / GB/T 2423.8",
        duration=1,
        temperature="",
        humidity="",
        suggested_samples=5,
        accept_criteria="C=0 (全部通过), 常见 6 面跌落",
        notes="裸机/包装状态跌落，高度按产品重量确定",
        keywords=["跌落", "drop", "自由跌落", "drop test"],
    ),

    # ═══════════════════════════════════════════════════════════════
    #  寿命/可靠性专项
    # ═══════════════════════════════════════════════════════════════

    TestTypeTemplate(
        name="加速寿命试验 (ALT)",
        category="环境试验",
        test_standard="IEC 62506 / JESD74A",
        duration=60,
        temperature="按 Arrhenius 模型设定",
        humidity="",
        suggested_samples=50,
        accept_criteria="按 Weibull/对数正态分布计算 MTBF 下限",
        notes="加速应力下的寿命评估，需统计分析",
        keywords=["ALT", "加速寿命", "accelerated life", "MTBF"],
    ),

    # ═══════════════════════════════════════════════════════════════
    #  其他
    # ═══════════════════════════════════════════════════════════════

    TestTypeTemplate(
        name="防水 (IP等级)",
        category="表面处理",
        test_standard="IEC 60529 / GB/T 4208",
        duration=1,
        temperature="",
        humidity="",
        suggested_samples=3,
        accept_criteria="无进水/功能正常",
        notes="IPX1~IPX8 各等级对应不同试验条件",
        keywords=["防水", "IP", "IPX", "ingress protection"],
    ),
    TestTypeTemplate(
        name="粉尘试验",
        category="表面处理",
        test_standard="IEC 60529 / GB/T 4208",
        duration=1,
        temperature="",
        humidity="",
        suggested_samples=3,
        accept_criteria="粉尘侵入量符合 IP 等级要求",
        notes="IP5X/6X 防尘测试",
        keywords=["粉尘", "防尘", "IP5X", "IP6X", "dust"],
    ),
    TestTypeTemplate(
        name="综合环境 (温湿度+振动)",
        category="环境试验",
        test_standard="IEC 60068-2-53 / GB/T 2423.36",
        duration=5,
        temperature="-40°C ~ 85°C",
        humidity="85%RH",
        suggested_samples=5,
        accept_criteria="C=0 (全部通过)",
        notes="温湿度+振动三综合试验，模拟运输/使用环境",
        keywords=["综合", "三综合", "combined", "温振"],
    ),

    # ═══════════════════════════════════════════════════════════════
    #  电磁兼容 (EMC)
    # ═══════════════════════════════════════════════════════════════

    TestTypeTemplate(
        name="静电放电 (ESD)",
        category="环境试验",
        test_standard="IEC 61000-4-2 / GB/T 17626.2",
        duration=1,
        temperature="",
        humidity="",
        suggested_samples=5,
        accept_criteria="接触放电±4kV / 空气放电±8kV 无异常",
        notes="HBM 模型，常见等级 1~4 级；需记录放电点位置",
        keywords=["ESD", "静电", "静电放电", "electrostatic discharge"],
    ),
    TestTypeTemplate(
        name="辐射抗扰度 (RS)",
        category="环境试验",
        test_standard="IEC 61000-4-3 / GB/T 17626.3",
        duration=1,
        temperature="",
        humidity="",
        suggested_samples=3,
        accept_criteria="80MHz~1GHz, 3V/m~10V/m 无异常",
        notes="射频电磁场辐射抗扰度",
        keywords=["RS", "辐射抗扰", "radiated immunity"],
    ),
    TestTypeTemplate(
        name="浪涌 (Surge)",
        category="环境试验",
        test_standard="IEC 61000-4-5 / GB/T 17626.5",
        duration=1,
        temperature="",
        humidity="",
        suggested_samples=3,
        accept_criteria="±1kV~±4kV 无损坏",
        notes="雷击浪涌抗扰度，线-线/线-地分别测试",
        keywords=["浪涌", "surge", "雷击", "surge immunity"],
    ),

    # ═══════════════════════════════════════════════════════════════
    #  机械寿命/耐久
    # ═══════════════════════════════════════════════════════════════

    TestTypeTemplate(
        name="插拔寿命",
        category="机械试验",
        test_standard="EIA-364-09 / USB-IF USB-C",
        duration=3,
        temperature="",
        humidity="",
        suggested_samples=5,
        accept_criteria="≥5000次（或按产品规格），接触电阻合格",
        notes="连接器/端子插拔耐久性，记录插拔力变化",
        keywords=["插拔", "mating", "插拔寿命", "durability", "连接器"],
    ),
    TestTypeTemplate(
        name="按键寿命",
        category="机械试验",
        test_standard="企业标准 / 客户规格",
        duration=5,
        temperature="",
        humidity="",
        suggested_samples=5,
        accept_criteria="≥100万次（或按产品规格），手感/功能正常",
        notes="开关/按键机械耐久性，记录力度衰减曲线",
        keywords=["按键", "按键寿命", "key life", "耐久", "开关"],
    ),
    TestTypeTemplate(
        name="弯折/挠曲",
        category="机械试验",
        test_standard="IPC-TM-650 2.4.3 / JIS C 5016",
        duration=3,
        temperature="",
        humidity="",
        suggested_samples=5,
        accept_criteria="≥5000次无断路/短路",
        notes="FPC/线材弯折耐久，记录弯曲半径/角度/频率",
        keywords=["弯折", "挠曲", "FPC", "flex", "bending"],
    ),

    # ═══════════════════════════════════════════════════════════════
    #  半导体专项
    # ═══════════════════════════════════════════════════════════════

    TestTypeTemplate(
        name="恒温恒湿偏压 (THB+Bias)",
        category="环境试验",
        test_standard="JESD22-A101 / IEC 60068-2-78",
        duration=14,
        temperature="85°C",
        humidity="85%RH",
        suggested_samples=25,
        accept_criteria="加电状态下，偏压电流/功能无异常",
        notes="THB 加偏压，评估 IC 封装耐湿能力",
        keywords=["THB", "偏压", "Bias", "HAST", "湿热偏压"],
    ),
    TestTypeTemplate(
        name="无铅回流焊 (MSL)",
        category="工艺试验",
        test_standard="IPC/JEDEC J-STD-020 / J-STD-033",
        duration=1,
        temperature="峰值 260°C",
        humidity="",
        suggested_samples=10,
        accept_criteria="MSL 等级对应回流次数后无剥离/分层",
        notes="湿度敏感等级评估，需先按 MSL 等级预处理",
        keywords=["MSL", "回流焊", "reflow", "湿度敏感", "分层"],
    ),
    TestTypeTemplate(
        name="PCB 离子清洁度",
        category="工艺试验",
        test_standard="IPC-TM-650 2.3.25 / J-STD-001",
        duration=1,
        temperature="",
        humidity="",
        suggested_samples=5,
        accept_criteria="NaCl当量 ≤1.56μg/cm² (Class 3)",
        notes="离子污染度测试，清洁度等级按 IPC 标准",
        keywords=["清洁度", "离子", "ion", "cleanliness", "污染"],
    ),

    # ═══════════════════════════════════════════════════════════════
    #  运输/包装
    # ═══════════════════════════════════════════════════════════════

    TestTypeTemplate(
        name="随机振动 (运输模拟)",
        category="包装",
        test_standard="ASTM D4728 / ISTA 2A",
        duration=1,
        temperature="",
        humidity="",
        suggested_samples=3,
        accept_criteria="包装无破损，产品功能正常",
        notes="模拟公路/铁路运输振动谱",
        keywords=["运输", "运输模拟", "ISTA", "ASTM", "包装振动"],
    ),
    TestTypeTemplate(
        name="包装抗压 (堆码)",
        category="包装",
        test_standard="ASTM D642 / GB/T 4857.4",
        duration=1,
        temperature="",
        humidity="",
        suggested_samples=3,
        accept_criteria="抗压强度≥计算值，变形≤允许值",
        notes="仓库堆码条件下的包装抗压能力",
        keywords=["抗压", "堆码", "compression", "包装强度"],
    ),
]


# ═══════════════════════════════════════════════════════════════════
#  查询 API
# ═══════════════════════════════════════════════════════════════════


def get_template_names() -> list[str]:
    """返回所有模板名称列表（用于下拉框）。"""
    return ["（自定义）"] + [t.name for t in TEMPLATES]


def get_template_by_name(name: str) -> Optional[TestTypeTemplate]:
    """按名称查找模板，未找到返回 None。"""
    for t in TEMPLATES:
        if t.name == name:
            return t
    return None


def search_templates(keyword: str) -> list[TestTypeTemplate]:
    """按关键词搜索模板（匹配名称/标准/keywords）。"""
    keyword_lower = keyword.lower()
    results: list[TestTypeTemplate] = []
    for t in TEMPLATES:
        searchable = (
            t.name
            + " "
            + t.test_standard
            + " "
            + " ".join(t.keywords)
        ).lower()
        if keyword_lower in searchable:
            results.append(t)
    return results
