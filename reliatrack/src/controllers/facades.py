"""按域拆分的依赖装配 facade。

AppController 原先直接集 12 repo + 12 service 的公共字段（god object）。
本模块把同一领域的 repo + service 绑成一个 facade 对象，由 AppController
持有 facade，对外通过委托属性暴露（向后兼容既有调用方）。
"""

from __future__ import annotations

from typing import Any


class DomainFacade:
    """一个业务域的 repo + service 容器。"""

    def __init__(self, repo: Any = None, service: Any = None) -> None:
        self.repo = repo
        self.service = service


class SampleFacade(DomainFacade):
    """样品域。"""


class IssueFacade(DomainFacade):
    """Issue / FA / CAPA 域。"""


class PlanFacade(DomainFacade):
    """测试计划/任务域。"""


class ProjectFacade(DomainFacade):
    """项目域。"""


class EquipmentFacade(DomainFacade):
    """设备域。"""


class TechnicianFacade(DomainFacade):
    """技术员域。"""


class KnowledgeFacade(DomainFacade):
    """知识库域。"""


class TodoFacade(DomainFacade):
    """待办域。"""


class SettingsFacade(DomainFacade):
    """设置域。"""


class ExportFacade(DomainFacade):
    """导出域。"""


class SchedulerFacade(DomainFacade):
    """排程域。"""
