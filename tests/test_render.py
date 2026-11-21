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
from flet.components.component import Component, Renderer  # noqa: E402
from flet.controls import context as ctx  # noqa: E402

from data.service import JobService  # noqa: E402
from pages.urls import get_urls  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
