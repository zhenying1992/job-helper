"""组件渲染冒烟测试：用 Flet 真实渲染管线展开路由组件树。

详情页曾因 ft.Dropdown 误用 on_change（1.0.3 应为 on_select）在渲染时抛
TypeError，导致 Router 渲染循环崩溃、整个页面（含顶部 Tab）失去响应。
此测试确保各路由组件树能完整构建，不再出现同类白屏/卡死回归。
"""

import tempfile
import unittest
from pathlib import Path

import config

_TMP = tempfile.TemporaryDirectory()
config.APP_CONF_PATH = Path(_TMP.name) / "config.json"
config.save_app_config({"WORK_DIR": _TMP.name})

import data.db as db_module  # noqa: E402
db_module.init_db()

import flet as ft  # noqa: E402
from flet_charts import PieChart  # noqa: E402
from flet.components.component import Component, Renderer  # noqa: E402
from flet.controls import context as ctx  # noqa: E402

from data.service import JobService  # noqa: E402
from pages.urls import get_urls  # noqa: E402
from pages.overview import Center  # noqa: E402


class _FakePage:
    width = 1200
    on_route_change = None
    on_view_pop = None

    def __init__(self, route):
        self.route = route

    def show_dialog(self, *a, **k):
        pass

    def navigate(self, *a, **k):
        pass


def _expand(node, errors, depth=0, seen=None):
    """递归执行组件树里每个 @component 的函数体，收集渲染异常。

    同时扫描渲染结果中是否被 @catch_error 替换成了「页面加载失败」错误页——
    这类异常会被装饰器吞掉、函数体本身不抛，必须靠错误页文本才能检出。
    """
    if seen is None:
        seen = set()
    if depth > 20:
        return
    if isinstance(node, Component):
        if id(node) in seen:
            return
        seen.add(id(node))
        name = getattr(getattr(node, "fn", None), "__name__", "?")
        try:
            body = Renderer(node).render(node.fn, *node.args, **node.kwargs)
        except Exception as ex:  # noqa: BLE001
            errors.append((name, repr(ex)))
            return
        _expand(body, errors, depth + 1, seen)
        return
    if isinstance(node, ft.Text) and node.value == "页面加载失败":
        errors.append(("catch_error", "渲染结果为错误页"))
        return
    if isinstance(node, (list, tuple)):
        for item in node:
            _expand(item, errors, depth + 1, seen)
        return
    for attr in ("controls", "content", "body", "leading", "title", "outlet"):
        value = getattr(node, attr, None)
        if value is not None:
            _expand(value, errors, depth + 1, seen)


def render_route_errors(route):
    ctx._context_page.set(_FakePage(route))
    with Renderer().with_context():
        router = get_urls()
    body = Renderer(router).render(router.fn, *router.args, **router.kwargs)
    errors = []
    _expand(body, errors)
    return errors


class TestRenderSmoke(unittest.TestCase):
    def test_main_routes_render(self):
        for route in ("/overview", "/jobs", "/calendar", "/setting"):
            with self.subTest(route=route):
                self.assertEqual(render_route_errors(route), [])

    def test_job_detail_render_all_statuses(self):
        for status in ("未开始", "执行中", "阻塞中", "已完成"):
            job = JobService.create(f"渲染测试-{status}", "通用工作")
            JobService.update(job.id, status=status)
            with self.subTest(status=status):
                self.assertEqual(render_route_errors(f"/job/{job.id}"), [])

    def test_pie_hover_state(self):
        """饼图 hover 纯状态：默认状态名，悬浮显示数量/占比，越界还原。"""
        items = [("未开始", 15), ("执行中", 3)]
        titles, radii, tip = Center._pie_state(items, 18, None)
        self.assertEqual(titles, ["未开始", "执行中"])
        self.assertEqual(radii, [Center.normal_radius, Center.normal_radius])
        titles, radii, tip = Center._pie_state(items, 18, 0)
        self.assertEqual(titles, ["15 (83%)", "执行中"])
        self.assertEqual(radii, [Center.hover_radius, Center.normal_radius])
        self.assertIn("83%", tip)
        titles, _, _ = Center._pie_state(items, 18, -1)
        self.assertEqual(titles, ["未开始", "执行中"])

    def test_pie_hover_event_does_not_freeze(self):
        """回归：声明式组件里 hover 回调不得对冻结控件 update()。

        曾在 on_hover 里直接改 section 属性 + chart.update()，触发
        RuntimeError: Frozen control cannot be updated。用真实 Renderer 展开
        组件树、派发 hover 事件，确保状态驱动重渲染不再抛该异常。
        """
        ctx._context_page.set(_FakePage("/overview"))
        from pages import overview as ov
        charts = []

        def walk(node, depth=0):
            if depth > 25:
                return
            if isinstance(node, Component):
                body = Renderer(node).render(node.fn, *node.args, **node.kwargs)
                walk(body, depth + 1)
                return
            if isinstance(node, PieChart):
                charts.append(node)
            for attr in ("controls", "content", "outlet"):
                value = getattr(node, attr, None)
                if value is None:
                    continue
                for item in (value if isinstance(value, (list, tuple)) else [value]):
                    walk(item, depth + 1)

        with Renderer().with_context():
            root = Renderer().render(ov.overview)
        walk(root)
        self.assertEqual(len(charts), 1)
        chart = charts[0]
        self.assertIsNotNone(chart.on_event)
        # 真正派发 hover / leave，任何一步抛 Frozen control 都会让测试失败
        chart.on_event(type("E", (), {"section_index": 0})())
        chart.on_event(type("E", (), {"section_index": None})())


if __name__ == "__main__":
    unittest.main()
