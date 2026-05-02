# 可靠性工程师视角审查报告

> 日期：2026-05-02
> 审查范围：ReliaTrack 全栈（schema/models/services/views/dialogs）
> 视角：一线可靠性测试工程师日常使用

## 审查结论

框架扎实（样品追踪、任务排程、甘特图、Issue 管理都有），但距离"可靠性工程师离了 Excel 就能用"还有差距。核心差距：**缺少测试类型的专业参数化**和**判定/闭环的结构化管理**。

---

## 🔴 P0 — 关键缺陷（影响专业可用性）

### P0-1: 缺少测试类型模板体系

**现状：** `test_tasks.category` 只有 4 个自由文本分类（环境试验/机械试验/表面处理/包装），无结构化测试类型模板。

**问题：** 可靠性实验室的标准测试类型是固定的 — HALT、HASS、ALT、温循(TC)、恒温恒湿(THB)、机械振动(Random/Sine)、跌落、冲击、盐雾、UV老化等。每种测试有特定必填参数（如温循的温度范围和循环次数、振动的PSD谱和加速度、HALT的温度步进和驻留时间）。当前 `category` 只是自由文本标签，无法关联到具体测试条件的预设模板。

**建议：** 增加 `test_type_templates` 配置（JSON 文件或 DB 表），每种测试类型预定义：必填参数字段、环境条件范围、样品数量要求、判定标准引用。创建任务时先选测试类型，自动填充参数模板。

### P0-2: 无判定标准/接收准则

**现状：** `test_tasks` 有 `test_standard`（引用标准号）但没有具体判定条件。`TestResult` 只有 pass/fail/conditional/pending/skip 五值枚举，没有关联到具体接收准则（AQL、C=0、R=1 等）。

**问题：** 可靠性测试报告必须明确写出"样品数量 × 通过数量 = 判定结果"的逻辑。例如"高温存储 85°C/1000h，5/0 收/拒，5 个样品全通过 → 判定合格"。当前只记录 pass/fail，不记录判定规则。

**建议：**
- `test_tasks` 增加 `accept_criteria` 字段（JSON，如 `{"sample_size": 5, "accept": 5, "reject": 0}`）
- 结果汇总时自动判定（如 5 个样品中 4 pass 1 fail → 根据准则自动判定 conditional/fail）
- 导出报告中体现判定逻辑

### P0-3: FA 分析不满足 FRACAS 基本要求

**现状：** `FARecord` 只有 step_no/step_title/description/method/findings 五个字段。Issue 只有 root_cause 和 resolution 两个文本字段。

**问题：** 合格 FRACAS 系统至少需要：
- 5-Why 结构化因果链记录
- 鱼骨图分类：人/机/料/法/环/测
- CAPA 跟踪：措施、责任人、截止日期、验证结果
- 复发检测：同一 failure_mode 是否历史出现过

当前 FA 是扁平步骤列表，与知识库无自动关联，无法形成"失效→分析→纠正→知识沉淀"闭环。

**建议：**
- Issue 增加 CAPA 相关字段或单独 `capa_records` 表：action/assignee_id/due_date/verification_result/verified_by
- FA 分析增加"可能原因"和"确认/排除"的结构化记录
- 创建 Issue 时自动匹配 `knowledge_entries` 中相同 failure_mode 的历史案例

---

## 🟡 P1 — 功能缺失（限制专业使用场景）

### P1-1: 无样品-任务-结果三维矩阵视图

**现状：** 数据模型已有 `test_tasks.sample_ids` 和 `test_results(task_id, sample_id)`，但 UI 没有矩阵视图。

**问题：** 可靠性工程师最常用的视角是"样品×测试项"矩阵 — 横轴测试项、纵轴样品 SN、单元格 pass/fail。当前只能在每个任务里看结果列表，无法横向对比。

**建议：** 测试计划 Tab 增加"结果矩阵"子 Tab（与"测试项""甘特图"并列），用 QTableWidget 构建。

### P1-2: Dashboard 缺少可靠性专业 KPI

**现状：** 7 个通用 KPI，没有可靠性专业指标。

**问题：** 可靠性工程师关注：通过率、首次通过率(FPY)、Issue 闭环率、MTBF/MTTF、测试进度偏差。

**建议：** Dashboard 增加第二行 KPI 卡片：通过率、Issue 闭环率、测试进度偏差。

### P1-3: 设备校准管理不完整

**现状：** Equipment 有 calibration_date 和 next_calibration_date，但没有校准周期配置、到期提醒、超期校验。

**问题：** ISO 17025 / IATF 16949 要求设备校准状态受控。设备超期使用的测试数据需特殊标记。

**建议：**
- Equipment 增加 `calibration_interval_months` 字段
- Dashboard 增加校准预警卡片
- 录入测试结果时检查设备校准状态

### P1-4: 测试结果缺少环境参数记录

**现状：** `test_results.environment`（JSON）字段存在但 UI 无输入。环境参数只在任务级别。

**问题：** 同一任务的不同样品可能在不同温湿度条件下测试（如温度步进试验）。

**建议：** TestResultDialog 的 _ResultRow 增加温度/湿度输入框（可选）。

### P1-5: 导出报告不够专业

**现状：** PDF 有封面、概览、任务表、Issue 表，但缺少样品信息表、结果矩阵、设备清单、判定结论、签署栏。

**问题：** 客户审核（尤其汽车行业 PPAP 提交）需要完整 DVP&R 格式报告。

**建议：** PDF 导出模板对标 DVP&R 格式。

---

## 💡 P2/P3 — 优化建议

### P2-1: 知识库与 Issue/FA 自动关联

创建/编辑 Issue 的 failure_mode 字段时，实时搜索知识库匹配条目。Issue 关闭时一键导入 FA 结论到知识库。

### P2-2: 测试任务关联引用标准具体条款

预置常用可靠性测试标准及测试方法下拉（IEC 60068-2-1/Aa、IEC 60068-2-14/Na、JESD22-A103D 等），减少手动输入错误。

### P2-3: 样品生命周期追踪增强

- 增加 `test_hours` 字段（累计测试时长）
- 增加 `current_task_id` 字段
- 出库关联任务后样品状态自动推进

### P3-1: 排程引擎增加节假日支持

排程只区分工作日/周末，不支持法定节假日和实验室自定义休息日。增加 `holidays` 设置。

---

## 实施建议

### Phase 3 — 专业能力补齐（P0 三项）

P0-1（测试类型模板）和 P0-2（判定标准）紧密关联，建议一起做：

1. **新增 `test_type_templates` JSON 配置文件**（不动 DB schema，低风险）
   - 定义 15-20 种常见可靠性测试类型的参数模板
   - 创建任务弹窗增加"测试类型"下拉，选择后自动填充 category/test_standard/temperature/humidity/duration/accept_criteria

2. **`test_tasks` 增加 `accept_criteria` 字段**（schema v7）
   - JSON 格式，存储判定逻辑
   - 测试结果汇总时自动判定并展示

3. **CAPA 表和 FA 增强**（schema v7）
   - 新增 `capa_records` 表
   - `fa_records` 增加 `possible_cause / cause_category / confirmed` 字段
   - Issue 创建时自动搜索知识库匹配

### Phase 4 — 专业视图和报告（P1 五项）

4. **结果矩阵子 Tab**
5. **Dashboard 专业 KPI 第二行**
6. **校准管控增强**
7. **结果环境参数输入**
8. **DVP&R 格式 PDF 导出**

### Phase 5 — 体验优化（P2/P3）

9-12. 知识库关联、标准条款、样品增强、节假日

---

## 当前代码质量评估

| 维度 | 评分 | 说明 |
|------|------|------|
| 架构分层 | ⭐⭐⭐⭐⭐ | Handler/Service/Repository 三层清晰，Handler 按域拆分 |
| 数据完整性 | ⭐⭐⭐⭐ | FK/CASCADE/事务覆盖好，缺判定标准和 CAPA 结构 |
| UI 一致性 | ⭐⭐⭐⭐ | Catppuccin 主题统一，搜索/排序/右键/双击全覆盖 |
| 测试覆盖 | ⭐⭐⭐⭐ | 56 E2E + 40 边界 + 39 Service 单元，缺可靠性业务场景测试 |
| 专业深度 | ⭐⭐⭐ | 框架到位，缺测试类型参数化、判定逻辑、CAPA 闭环 |
