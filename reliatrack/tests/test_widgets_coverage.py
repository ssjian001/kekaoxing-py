"""低覆盖率 widget 模块补充测试。

目标模块与测试内容:
- src/views/widgets/analysis_widget.py (18%):
    构造占位、refresh 空/无结果/有结果分支、按类别通过率统计、
    失效 Top-N 表格内容（含 UserRole/样品 SN 回退、Issue 计数、严重度）、
    未关联 Issue 告警（含 >8 条截断）、_BarWidget 展示。
- src/views/widgets/result_matrix.py (29%):
    构造、refresh 空/无任务/无结果分支、任务×样品矩阵内容
    （行列统计、UserRole 存 (task_id, sample_id)、表头 SN 回退）、
    显示模式切换（符号/实测值/日期）、双击循环切换结果
    （含缓存乐观更新、非法列/统计行 no-op、未知结果回退到 pass）、
    set_on_result_changed、refresh_theme 重渲染。
"""

from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import apsw

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QTableWidget

from src.db.schema import init_schema
from src.models.test_plan import TestTask, TestResult
from src.models.issue import Issue
from src.views.widgets.analysis_widget import _AnalysisWidget, _BarWidget
from src.views.widgets.result_matrix import _ResultMatrixWidget


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def db_conn():
    conn = apsw.Connection(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    yield conn
    conn.close()


# ── 数据构造辅助 ──────────────────────────────────────────────

def _task(tid, name="任务", category="环境试验"):
    return TestTask(id=tid, plan_id=1, name=name, category=category)


def _result(task_id, sample_id, result, **kwargs):
    return TestResult(task_id=task_id, sample_id=sample_id, result=result, **kwargs)


def _issue(task_id, severity="major"):
    return Issue(task_id=task_id, severity=severity, title="失效")


# ═══════════════════════════════════════════════════════════════════
#  analysis_widget
# ═══════════════════════════════════════════════════════════════════

def _labels(widget) -> list[str]:
    """收集 widget 树中所有 QLabel 的文本。"""
    return [w.text() for w in widget.findChildren(QLabel)]


class TestAnalysisWidgetBasics:
    def test_construct_shows_placeholder(self, qapp):
        w = _AnalysisWidget()
        assert "选择测试计划后显示失效模式分析" in _labels(w)

    def test_refresh_empty_tasks_shows_placeholder(self, qapp):
        w = _AnalysisWidget()
        w.refresh([])
        assert "选择测试计划后显示失效模式分析" in _labels(w)

    def test_refresh_tasks_without_results_shows_zero_stats(self, qapp):
        """任务存在但无结果: 类别统计区渲染，通过率 0/0。"""
        w = _AnalysisWidget()
        w.refresh([_task(1)])
        labels = _labels(w)
        assert "按类别通过率" in labels
        assert "0/0" in labels

    def test_refresh_twice_rebuilds_without_duplication(self, qapp):
        """纯重建模式：连续 refresh 不残留旧内容（如失效详情表）。"""
        w = _AnalysisWidget()
        w.refresh([_task(1)], results=[_result(1, 10, "fail")])
        assert len(w.findChildren(QTableWidget)) == 1
        w.refresh([_task(1)])
        texts = _labels(w)
        assert len(w.findChildren(QTableWidget)) == 0
        assert texts.count("按类别通过率") == 1


class TestAnalysisCategoryStats:
    def test_category_pass_rate_detail(self, qapp):
        """类别统计: pass/fail/conditional 计入 total，pending 不计入。"""
        tasks = [_task(1, category="高温")]
        results = [
            _result(1, 1, "pass"),
            _result(1, 2, "fail"),
            _result(1, 3, "conditional"),
            _result(1, 4, "pending"),  # 不计入 total
        ]
        w = _AnalysisWidget()
        w.refresh(tasks, results=results)

        labels = _labels(w)
        assert "按类别通过率" in labels
        # pass=1, total=3 → "1/3"
        assert "1/3" in labels

    def test_uncategorized_task_uses_fallback_label(self, qapp):
        tasks = [TestTask(id=1, plan_id=1, name="T", category="")]
        w = _AnalysisWidget()
        w.refresh(tasks, results=[_result(1, 1, "pass")])
        assert "未分类" in _labels(w)

    def test_bar_widget_holds_rate_value(self, qapp):
        """进度条 widget 用 rate 构造。"""
        bar = _BarWidget(75.0, "#00ff00")
        assert bar._value == 75.0
        assert bar._color == "#00ff00"

    def test_bar_widget_paints_without_crash(self, qapp):
        """离屏渲染 paintEvent 不崩溃（不断言像素，仅冒烟）。"""
        for value in (0.0, 50.0, 100.0):
            bar = _BarWidget(value, "#00ff00")
            bar.resize(120, 18)
            assert not bar.grab().isNull()


class TestAnalysisFailTable:
    def _widget_with_fails(self, qapp, sample_map=None, issues=None):
        tasks = [_task(1, name="高温测试", category="环境"),
                 _task(2, name="低温测试", category="机械")]
        results = [
            _result(1, 10, "pass"),
            _result(1, 11, "fail"),
            _result(2, 11, "fail"),
        ]
        w = _AnalysisWidget()
        w.refresh(tasks, results=results,
                  issues=issues or [], sample_map=sample_map or {})
        return w

    def test_fail_table_rows_and_headers(self, qapp):
        w = self._widget_with_fails(qapp)
        tables = w.findChildren(QTableWidget)
        assert len(tables) == 1
        tbl = tables[0]
        assert tbl.rowCount() == 2
        assert tbl.columnCount() == 5
        headers = [tbl.horizontalHeaderItem(c).text() for c in range(5)]
        assert headers == ["任务", "类别", "样品", "Issue", "严重度"]

    def test_fail_table_cell_contents(self, qapp):
        w = self._widget_with_fails(qapp)
        tbl = w.findChildren(QTableWidget)[0]
        # 第一行: 任务名 / 类别 / 样品 SN 回退 #11 / 未创建 Issue / 严重度 -
        assert tbl.item(0, 0).text() == "高温测试"
        assert tbl.item(0, 1).text() == "环境"
        assert tbl.item(0, 2).text() == "#11"
        assert tbl.item(0, 3).text() == "未创建"
        assert tbl.item(0, 4).text() == "-"

    def test_fail_table_sample_map_and_issue_count(self, qapp):
        """sample_map 提供真实 SN；有 Issue 时显示 N个 + 严重度。"""
        tasks = [_task(1, name="振动测试", category="机械")]
        results = [_result(1, 7, "fail")]
        issues = [_issue(1, severity="critical"), _issue(1, severity="major")]
        w = _AnalysisWidget()
        w.refresh(tasks, results=results, issues=issues,
                  sample_map={7: "SN-007"})
        tbl = w.findChildren(QTableWidget)[0]
        assert tbl.item(0, 2).text() == "SN-007"
        assert tbl.item(0, 3).text() == "2个"
        assert tbl.item(0, 4).text() == "critical"

    def test_unlinked_warning_label(self, qapp):
        w = self._widget_with_fails(qapp)
        labels = _labels(w)
        warns = [t for t in labels if "未创建 Issue" in t]
        assert len(warns) == 1
        assert "2 条失败结果未创建 Issue" in warns[0]
        assert "高温测试/#11" in warns[0]

    def test_unlinked_warning_truncates_after_8(self, qapp):
        """超过 8 条未关联失败时截断并显示总数。"""
        tasks = [_task(i, name=f"T{i}") for i in range(1, 11)]
        results = [_result(i, i, "fail") for i in range(1, 11)]
        w = _AnalysisWidget()
        w.refresh(tasks, results=results)
        warns = [t for t in _labels(w) if "未创建 Issue" in t]
        assert len(warns) == 1
        assert "10 条失败结果未创建 Issue" in warns[0]
        assert "... 共 10 条" in warns[0]

    def test_fail_section_title_counts_entries(self, qapp):
        w = self._widget_with_fails(qapp)
        assert "失效详情 (2 条)" in _labels(w)


# ═══════════════════════════════════════════════════════════════════
#  result_matrix
# ═══════════════════════════════════════════════════════════════════

def _matrix(qapp, callback=None):
    return _ResultMatrixWidget(on_result_changed=callback)


class TestResultMatrixBasics:
    def test_construct_default_state(self, qapp):
        w = _matrix(qapp)
        assert w._summary_label.text() == "选择测试计划后显示结果矩阵"
        assert w._mode_group.checkedId() == 0  # 默认符号模式
        assert len(w._mode_group.buttons()) == 3

    def test_refresh_empty_tasks_clears_table(self, qapp):
        w = _matrix(qapp)
        w.refresh([], [], {})
        assert w._table.rowCount() == 0
        assert w._table.columnCount() == 0
        assert w._summary_label.text() == "当前计划无测试任务"

    def test_refresh_tasks_without_results(self, qapp):
        """任务存在但结果为空: 矩阵只有任务名列 + 通过率列，末行合计。"""
        w = _matrix(qapp)
        w.refresh([_task(1, name="T1")], [], {})
        assert w._table.rowCount() == 2   # 1 任务 + 合计行
        assert w._table.columnCount() == 2  # 任务名 + 通过率
        assert w._table.item(0, 0).text() == "T1"
        assert w._table.item(0, 1).text() == "—"  # 无结果 → 行统计为 —
        assert w._summary_label.text() == "暂无测试结果数据"

    def test_refresh_results_without_pass(self, qapp):
        """有样品列但全部未录入（result 为空串）→ 暂无录入结果。"""
        w = _matrix(qapp)
        w.refresh([_task(1)], [_result(1, 5, "")], {5: "SN-5"})
        assert "暂无录入结果" in w._summary_label.text()


class TestResultMatrixContent:
    def _refresh(self, qapp):
        tasks = [
            _task(1, name="高温"),
            _task(2, name="低温"),
        ]
        results = [
            _result(1, 10, "pass", measured_value="85.2",
                    test_date="2026-08-01 10:00:00", notes="OK"),
            _result(1, 11, "fail"),
            _result(2, 10, "conditional"),
            # task 2 / sample 11 无结果 → pending 空
        ]
        sample_map = {10: "SN-A", 11: "SN-B"}
        w = _matrix(qapp)
        w.refresh(tasks, results, sample_map)
        return w, tasks, results

    def test_dimensions_and_headers(self, qapp):
        w, _, _ = self._refresh(qapp)
        assert w._table.rowCount() == 3   # 2 任务 + 合计
        assert w._table.columnCount() == 4  # 任务名 + 2 样品 + 通过率
        headers = [w._table.horizontalHeaderItem(c).text()
                   for c in range(w._table.columnCount())]
        assert headers == ["任务", "SN-A", "SN-B", "通过率"]

    def test_header_sn_fallback_for_unknown_sample(self, qapp):
        """sample_map 缺失的 sample_id 回退为 #id。"""
        w = _matrix(qapp)
        w.refresh([_task(1)], [_result(1, 99, "pass")], {})
        assert w._table.horizontalHeaderItem(1).text() == "#99"

    def test_cell_labels_and_user_role(self, qapp):
        """符号模式下 P/F/C 标签；UserRole 存 (task_id, sample_id)。"""
        w, _, _ = self._refresh(qapp)
        tbl = w._table
        assert tbl.item(0, 1).text() == "P"   # task1 × SN-A pass
        assert tbl.item(0, 2).text() == "F"   # task1 × SN-B fail
        assert tbl.item(1, 1).text() == "C"   # task2 × SN-A conditional
        assert tbl.item(1, 2).text() == ""    # 无结果 → 空标签
        # 任务名列 UserRole 存 task.id（仓库规范: 通过 ID 查找行）
        assert tbl.item(0, 0).data(Qt.ItemDataRole.UserRole) == 1
        assert tbl.item(1, 0).data(Qt.ItemDataRole.UserRole) == 2
        # 结果单元格 UserRole 存 (task_id, sample_id) 元组
        assert tbl.item(0, 1).data(Qt.ItemDataRole.UserRole) == (1, 10)
        assert tbl.item(1, 2).data(Qt.ItemDataRole.UserRole) == (2, 11)

    def test_result_lookup_cache(self, qapp):
        w, _, _ = self._refresh(qapp)
        assert w._result_lookup[(1, 10)] == "pass"
        assert w._result_lookup[(2, 11)] == ""  # 无结果 → 空串

    def test_row_and_column_stats(self, qapp):
        """行统计: task1 1/2=50%；列统计: SN-A 1/2=50%、SN-B 0/1=0%。"""
        w, _, _ = self._refresh(qapp)
        tbl = w._table
        assert tbl.item(0, 3).text() == "50%"   # task1 行通过率
        assert tbl.item(1, 3).text() == "0%"    # task2: conditional 不算 pass
        assert tbl.item(2, 0).text() == "合计"
        assert tbl.item(2, 1).text() == "50%"   # SN-A 列
        assert tbl.item(2, 2).text() == "0%"    # SN-B 列
        # 右下角总计: pass=1, total=3
        assert tbl.item(2, 3).text() == "1/3 (33%)"

    def test_summary_label_text(self, qapp):
        w, _, _ = self._refresh(qapp)
        text = w._summary_label.text()
        assert "共 2 项任务 × 2 个样品" in text
        assert "通过 1/3 (33%)" in text
        assert "失败 1" in text

    def test_tooltip_contains_result_info(self, qapp):
        w, _, _ = self._refresh(qapp)
        tip = w._table.item(0, 1).toolTip()
        assert "结果: pass" in tip
        assert "实测值: 85.2" in tip
        assert "日期: 2026-08-01" in tip
        assert "备注: OK" in tip


class TestResultMatrixModes:
    def _refresh_with_extra(self, qapp):
        tasks = [_task(1, name="T")]
        results = [_result(1, 10, "pass", measured_value="12.5mm",
                           test_date="2026-08-15 09:30:00")]
        w = _matrix(qapp)
        w.refresh(tasks, results, {10: "SN-X"})
        return w

    def test_measured_mode_shows_measured_value(self, qapp):
        w = self._refresh_with_extra(qapp)
        w._mode_group.button(1).click()  # 实测值模式（idClicked → _on_mode_changed）
        assert w._mode_group.checkedId() == 1
        assert w._table.item(0, 1).text() == "12.5mm"

    def test_date_mode_shows_date_only(self, qapp):
        w = self._refresh_with_extra(qapp)
        w._mode_group.button(2).click()  # 日期模式
        assert w._table.item(0, 1).text() == "2026-08-15"

    def test_switching_back_to_symbol_mode(self, qapp):
        w = self._refresh_with_extra(qapp)
        w._mode_group.button(1).click()
        w._mode_group.button(0).click()
        assert w._table.item(0, 1).text() == "P"

    def test_mode_change_updates_button_styles(self, qapp):
        """选中的模式按钮套用选中态 QSS。"""
        w = self._refresh_with_extra(qapp)
        w._mode_group.button(1).click()
        checked_qss = w._mode_qss(True)
        assert w._mode_group.button(1).styleSheet() == checked_qss
        assert w._mode_group.button(0).styleSheet() == w._mode_qss(False)


class TestResultMatrixDoubleClick:
    def test_double_click_cycles_result_and_fires_callback(self, qapp):
        """双击 pass 单元格 → fail → conditional 循环推进，回调收到新值。"""
        calls: list[tuple[int, int, str]] = []
        w = _matrix(qapp, callback=lambda t, s, r: calls.append((t, s, r)))
        w.refresh([_task(1)], [_result(1, 10, "pass")], {10: "SN"})

        w._on_cell_double_clicked(0, 1)
        assert calls == [(1, 10, "fail")]
        assert w._result_lookup[(1, 10)] == "fail"  # 乐观缓存更新

        w._on_cell_double_clicked(0, 1)
        assert calls[-1] == (1, 10, "conditional")  # 连续双击继续推进

        w._on_cell_double_clicked(0, 1)
        w._on_cell_double_clicked(0, 1)
        w._on_cell_double_clicked(0, 1)
        assert calls[-1] == (1, 10, "pass")  # 环回: conditional→pending→skip→pass

    def test_double_click_unknown_result_falls_back_to_pass(self, qapp):
        """结果真值不在 cycle 中（如未录入的空串）→ 从 cycle 头部 pass 开始。"""
        calls: list[tuple[int, int, str]] = []
        w = _matrix(qapp, callback=lambda t, s, r: calls.append((t, s, r)))
        w.refresh([_task(1)], [_result(1, 10, "")], {10: "SN"})
        w._on_cell_double_clicked(0, 1)
        assert calls == [(1, 10, "pass")]
        assert w._result_lookup[(1, 10)] == "pass"

    def test_double_click_ignores_name_and_stat_columns(self, qapp):
        """第 0 列（任务名）与末列（行统计）双击是 no-op。"""
        calls: list[tuple[int, int, str]] = []
        w = _matrix(qapp, callback=lambda t, s, r: calls.append((t, s, r)))
        w.refresh([_task(1)], [_result(1, 10, "pass")], {10: "SN"})
        w._on_cell_double_clicked(0, 0)  # 任务名列
        w._on_cell_double_clicked(0, 2)  # 末列统计
        assert calls == []

    def test_double_click_ignores_stat_row(self, qapp):
        """末行（合计行）双击是 no-op。"""
        calls: list[tuple[int, int, str]] = []
        w = _matrix(qapp, callback=lambda t, s, r: calls.append((t, s, r)))
        w.refresh([_task(1)], [_result(1, 10, "pass")], {10: "SN"})
        w._on_cell_double_clicked(1, 1)  # row 1 = 合计行
        assert calls == []

    def test_set_on_result_changed_rebinds_callback(self, qapp):
        calls: list[tuple[int, int, str]] = []
        w = _matrix(qapp)
        w.refresh([_task(1)], [_result(1, 10, "pass")], {10: "SN"})
        w.set_on_result_changed(lambda t, s, r: calls.append((t, s, r)))
        w._on_cell_double_clicked(0, 1)
        assert calls == [(1, 10, "fail")]

    def test_double_click_ignores_malformed_cells(self, qapp):
        """单元格缺失或 UserRole 数据不是 (task_id, sample_id) 元组时 no-op。"""
        from PySide6.QtWidgets import QTableWidgetItem
        calls: list[tuple[int, int, str]] = []
        w = _matrix(qapp, callback=lambda t, s, r: calls.append((t, s, r)))
        w.refresh([_task(1)], [_result(1, 10, "pass")], {10: "SN"})
        # 无 UserRole 数据的裸单元格
        w._table.setItem(0, 1, QTableWidgetItem("bare"))
        w._on_cell_double_clicked(0, 1)
        # 单元格被移除（item 为 None）
        w._table.takeItem(0, 1)
        w._on_cell_double_clicked(0, 1)
        assert calls == []


class TestResultMatrixTheme:
    def test_refresh_theme_rerenders_cached_data(self, qapp):
        w = _matrix(qapp)
        w.refresh([_task(1, name="T")], [_result(1, 10, "pass")], {10: "SN"})
        # 清掉表格后 refresh_theme 应基于缓存重建
        w._table.setRowCount(0)
        w.refresh_theme()
        assert w._table.item(0, 1).text() == "P"
        assert w._table.rowCount() == 2

    def test_refresh_theme_without_tasks_no_crash(self, qapp):
        w = _matrix(qapp)
        w.refresh_theme()  # 无缓存数据也不崩
        assert w._summary_label.text() == "选择测试计划后显示结果矩阵"


# ═══════════════════════════════════════════════════════════════════
#  端到端: 真实 Service 依赖（:memory: apsw + init_schema）
# ═══════════════════════════════════════════════════════════════════

class TestWidgetsEndToEndWithServices:
    """用 Service 层创建真实任务/结果数据后驱动两个 widget。"""

    @pytest.fixture()
    def plan_data(self, db_conn, sample_project):
        from src.db.repositories import (
            SampleRepository,
            TestPlanRepository, TestTaskRepository, TestResultRepository,
        )
        from src.services.sample_service import SampleService
        from src.services.test_plan_service import TestPlanService

        # 真实样品行（test_results.sample_id 有外键约束）
        sample_svc = SampleService(SampleRepository(db_conn))
        pid = sample_project["id"]
        sid_a = sample_svc.create("SN-010", project_id=pid, status="in_stock")
        sid_b = sample_svc.create("SN-011", project_id=pid, status="in_stock")

        svc = TestPlanService(
            TestPlanRepository(db_conn), TestTaskRepository(db_conn),
            TestResultRepository(db_conn),
        )
        plan_id = svc.create_plan(pid, "回归计划", start_date="2026-08-01")
        tid1 = svc.create_task(plan_id, "高温老化", duration=5, category="环境试验")
        tid2 = svc.create_task(plan_id, "跌落测试", duration=2, category="机械试验")
        svc.save_result(tid1, sample_id=sid_a, result="pass")
        svc.save_result(tid1, sample_id=sid_b, result="fail")
        svc.save_result(tid2, sample_id=sid_a, result="conditional")
        tasks = svc.get_tasks(plan_id)
        results = svc.get_all_results_by_tasks([tid1, tid2])
        sample_map = {sid_a: "SN-010", sid_b: "SN-011"}
        return tasks, results, sample_map

    def test_matrix_with_service_data(self, qapp, plan_data):
        tasks, results, sample_map = plan_data
        w = _matrix(qapp)
        w.refresh(tasks, results, sample_map)

        assert w._table.rowCount() == 3
        assert w._table.columnCount() == 4
        headers = [w._table.horizontalHeaderItem(c).text()
                   for c in range(4)]
        assert headers == ["任务", "SN-010", "SN-011", "通过率"]
        # 高温老化: pass + fail → 50%
        assert w._table.item(0, 3).text() == "50%"
        assert "共 2 项任务 × 2 个样品" in w._summary_label.text()

    def test_analysis_with_service_data(self, qapp, plan_data):
        tasks, results, _ = plan_data
        w = _AnalysisWidget()
        w.refresh(tasks, results=results)

        labels = _labels(w)
        assert "按类别通过率" in labels
        # 高温老化 1/2、跌落 conditional 0/1
        assert "1/2" in labels
        assert "0/1" in labels
        # 一条 fail（高温老化 × sample 11），未创建 Issue
        assert "失效详情 (1 条)" in _labels(w)
        tbl = w.findChildren(QTableWidget)[0]
        assert tbl.item(0, 0).text() == "高温老化"
        assert tbl.item(0, 3).text() == "未创建"
