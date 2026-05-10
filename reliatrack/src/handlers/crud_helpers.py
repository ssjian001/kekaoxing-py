"""Handler 公共工具 — CRUD 操作的标准化异常处理与 UI 反馈。

使用方式:
    from src.handlers.crud_helpers import exec_crud

    exec_crud(
        win=self._win,
        action=ctrl.project_service.create,
        action_args=(...),
        action_kwargs={...},
        toast_msg="项目「xxx」已创建",
        entity="project",
        error_title="创建失败",
    )
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from PySide6.QtWidgets import QMessageBox

if TYPE_CHECKING:
    from main import MainWindow
    from src.services.undo_manager import Command

logger = logging.getLogger(__name__)


def exec_crud(
    *,
    win: MainWindow,
    action: Callable[..., Any],
    action_args: tuple | None = None,
    action_kwargs: dict | None = None,
    toast_msg: str,
    entity: str,
    error_title: str = "操作失败",
    catch_value_error: bool = False,
    undo_command: Command | None = None,
) -> bool:
    """执行 CRUD 操作并统一处理 toast / notify / 异常弹窗。

    Args:
        win: 主窗口实例。
        action: 要执行的业务方法（如 ctrl.project_service.create）。
        action_args: 位置参数元组。
        action_kwargs: 关键字参数字典。
        toast_msg: 成功时的 toast 消息。
        entity: 数据变更通知的实体名（如 "project", "issue"）。
        error_title: 异常弹窗标题。
        catch_value_error: 是否单独捕获 ValueError（用于 delete 操作）。
        undo_command: 可选的撤销命令。如果提供，将通过 UndoManager 执行，
            替代直接调用 action。

    Returns:
        True 表示操作成功，False 表示失败或被异常中断。
    """
    if action_args is None:
        action_args = ()
    if action_kwargs is None:
        action_kwargs = {}

    try:
        ctrl = win._ctrl
        if undo_command is not None and ctrl is not None:
            ctrl.undo_manager.execute(undo_command)
        else:
            action(*action_args, **action_kwargs)
    except ValueError as e:
        if catch_value_error:
            QMessageBox.warning(win, error_title, str(e))
            return False
        # 非 delete 操作的 ValueError 视为普通异常
        logger.exception("%s failed", error_title)
        QMessageBox.critical(win, error_title, f"操作失败: {e}")
        return False
    except Exception as e:
        logger.exception("%s failed", error_title)
        QMessageBox.critical(win, error_title, f"操作失败: {e}")
        return False

    win.toast(toast_msg, "success")
    if ctrl is None:
        ctrl = win._ctrl
    if ctrl:
        ctrl.notify_data_changed(entity)
    return True
