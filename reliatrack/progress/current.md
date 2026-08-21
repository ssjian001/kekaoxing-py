# ReliaTrack 进度 — 2026-08-21 全面体检

## 本次产物
- 全面体检报告（见会话记录）：测试/静态/DB/依赖/CI/运行时 7 维度
- **CI 从 6 连红修到绿**（run 32468142053 ok），4 个 commit：
  - 4d4ff4b: test_sample_tag 去 numpy 硬依赖 + CI 补 pytest-qt
  - 57bb695: E2E/performance 路径引导(tests/manual 需上跳3级) + 过时 API 对齐 + **生产 bug: sample_repo ESCAPE 子句双字符转义符**
  - 07ba7e6: performance 脚本对齐 v23 状态机
- 附带恢复：Clash Verge GUI/mihomo 未自启导致代理断，已拉起

## 发现但未处理（观察项）
- reportlab 4.5.1 vs PyPI 5.0.1 大版本落后（requirements 有意 pin <5.0）
- ~/.reliatrack/reliatrack.db(Aug12) 与 data/reliatrack.db(Aug14) 并存，旧文件易混淆
- PIL 在测试中靠 reportlab 传递依赖存在
- gc ResourceWarning(3 uncollectable) 无害噪音
- performance 基线警告 MainWindow 构造 11.4s（offscreen 软件渲染环境，非回归）

## 下次可复用
- E2E/performance 手动脚本跑法: QT_QPA_PLATFORM=offscreen .venv/bin/python tests/manual/test_e2e_full.py
- 服务方法存在性批量核对脚本（AST+反射）在会话记录中

## 需人工确认
- 无阻塞项。reportlab 升级需评估 API 变化后再动
