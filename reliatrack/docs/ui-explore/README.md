# ReliaTrack UI 美化探索 — 2026-08-22

分支：`explore/ui-polish`（基于 main @ f510818）

## 做了什么

1. **基线截图**：offscreen 双主题 × 8 视图共 18 张（工作区 `/home/zouxp/ui-explore/baseline/`）
2. **视觉短板分析**（主模型 ox-alpha 视觉 + zai-vision 交叉）：
   - 视觉层次弱：核心 KPI 与次要数据无字号/颜色区分，焦点分散
   - 间距拥挤：卡片间距 ~10px、字段间距不足、信息密度过高
   - 交互反馈缺失：行无 hover/选中态、按钮无 hover 效果
   - 颜色过载：Issue 行 8 种颜色（严重度 3 + 状态 2 + 优先级 3）
   - 表头重蓝底（#1890ff）视觉疲劳；斑马纹对比弱；侧栏选中态弱
   - 暗色主题：紫色"待开始"对比度 3.8:1 不足；浅蓝 CAPA 率 3.5:1 不足
3. **三方向 HTML 原型**（`docs/ui-explore/*.html`，Chromium 1280×800 渲染验证）：

| 方案 | 风格 | 核心差异 | 主模型评分（密度/工具感/舒适度） |
|---|---|---|---|
| A | 现有布局精修 | Catppuccin 保留、卡片打磨、hover/选中态、状态胶囊 | 5 / 5 / 9 |
| B | Linear 工具风 | 深侧栏+搜索、高密度表格、筛选 chip、优先级圆点 | **9 / 9 / 7** |
| C | 软卡片 Dashboard | 大圆角渐变、图标卡片、阶段时间线 | 7 / 6 / 8 |

## 主模型推荐

**B 为骨架**（信息密度 + 专业工具感最高，匹配工程师日常"扫超期/筛选/快更新"动作），
**吸收 C 的项目阶段时间线**做可切换汇报视图。

## 约束提醒（动手前必读）

- 用户 UI 偏好：明亮主题、紧凑布局、800×600 适配、无 emoji 按钮、不擅自移动/合并现有 UI 元素
  （mockup 里的 emoji 图标仅示意，落地时用现有 `styles/icon.py` 线性图标体系）
- 双主题（Latte/Mocha）任何颜色改动都要亮暗各验一次
- 侧栏是自绘 `SidebarTabBar`（main.py:78），改样式先读 paintEvent
- 805×600 最小窗口下 B 的深色宽侧栏（200px）可能挤占内容区 → 落地时侧栏保持窄条或做折叠

## 产物清单

- `docs/ui-explore/A_refined.html|png` — 方案 A
- `docs/ui-explore/B_linear.html|png` — 方案 B
- `docs/ui-explore/C_soft.html|png` — 方案 C
- `docs/ui-explore/compare_all.png` — 三方案纵向对比图
- `docs/ui-explore/baseline_{light,dark}_dashboard.png` — 现状基线
- 截图脚本：`/home/zouxp/ui-explore/screenshot_baseline.py`（offscreen，双主题全视图）
- 视觉分析脚本：`/home/zouxp/ui-explore/ox-vision.py`（主模型直调 vision）

## 下一步（待用户选型）

1. 用户从 A/B/C 选方向（或混搭：B 骨架 + C 时间线）
2. 出所选方案的 800×600 紧凑版 mockup 复核
3. 在本分支做 theme.py/constants.py 层面的第一轮实装（不动布局结构，先色彩/间距/反馈态）
