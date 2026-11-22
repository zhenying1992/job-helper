"""组件渲染冒烟测试：用 Flet 真实渲染管线展开路由组件树。

详情页曾因 ft.Dropdown 误用 on_change（1.0.3 应为 on_select）在渲染时抛
TypeError，导致 Router 渲染循环崩溃、整个页面（含顶部 Tab）失去响应。
此测试确保各路由组件树能完整构建，不再出现同类白屏/卡死回归。
"""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import config

_TMP = tempfile.TemporaryDirectory()
config.APP_CONF_PATH = Path(_TMP.name) / "config.json"
config.save_app_config({"WORK_DIR": _TMP.name})

import data.db as db_module  # noqa: E402
db_module.init_db()

import flet as ft  # noqa: E402
from flet_charts import LineChart, PieChart  # noqa: E402
from flet.components.component import Component, Renderer  # noqa: E402
from flet.controls import context as ctx  # noqa: E402

from constant import DEFAULT_TREND_DAYS, TREND_RANGES  # noqa: E402

from data.service import JobService, LogService  # noqa: E402
from pages.urls import get_urls  # noqa: E402
from pages import audit as audit_page  # noqa: E402
from pages import overview as ov  # noqa: E402


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


def fl_chart_samples(min_v, max_v, interval):
    """复刻 fl_chart 1.0.0 的 iterateThroughAxis：返回轴上实际会被采样的取值。

    fl_chart 用 label_spacing(=interval) 从 min 开始按步长取点，并且一定
    会带上轴的最大值。自定义刻度只有取值精确命中采样点时才会渲染，所以
    图表里给的标签集合必须与这个集合完全一致，否则标签会整片空白。
    """
    baseline, min_included, max_included = 0.0, True, True
    diff = baseline - min_v
    mod = diff % interval
    initial = min_v if (abs(max_v - min_v) <= mod or mod == 0) else min_v + mod

    count = int((max_v - min_v) // interval)
    last_position = initial + count * interval
    end = max_v
    epsilon = interval / 100000

    values = []
    seek = initial
    while seek <= end + epsilon:
        values.append(seek)
        seek += interval
    if min_included and initial != min_v:
        values.insert(0, min_v)
    if max_included and last_position != max_v:
        values.append(max_v)
    return values


class TestProgressChart(unittest.TestCase):
    """工作进展折线图的坐标轴约束。"""

    def test_y_axis_is_integer_step(self):
        """纵轴必须是整数刻度：fl_chart 自动推算会得到 3.5 这类小数。"""
        for peak in (0, 1, 3, 4, 5, 7, 12, 25, 26, 99, 100, 250, 1000):
            with self.subTest(peak=peak):
                max_y, step = ov._y_axis(peak)
                self.assertEqual(step, int(step))
                self.assertIn(step, ov.Y_STEPS)
                self.assertEqual(max_y, int(max_y))
                self.assertGreaterEqual(max_y, peak)
                self.assertEqual(max_y % step, 0)

    def test_y_labels_match_chart_samples(self):
        """自定义纵轴标签必须与 fl_chart 的采样点一一对应，否则不显示。"""
        for peak in (0, 3, 25, 120, 1000):
            with self.subTest(peak=peak):
                max_y, step = ov._y_axis(peak)
                labels = ov._y_labels(max_y, step)
                values = [lb.value for lb in labels]
                self.assertEqual(values, fl_chart_samples(0, max_y, step))
                self.assertTrue(all(float(v).is_integer() for v in values))

    def test_x_labels_match_chart_samples(self):
        """横轴标签下标必须与采样点一致，且末位（今天）必须有标签。"""
        for days in (7, 15, 30):
            with self.subTest(days=days):
                step = ov._x_step(days)
                data = {f"2026-01-{i:02d}": 0 for i in range(1, days + 1)}
                labels = ov._x_labels(data, step)
                values = [lb.value for lb in labels]
                self.assertEqual(values, fl_chart_samples(0, days - 1, step))
                self.assertIn(days - 1, values)

    def test_x_label_shows_only_day(self):
        """横轴只显示「日」，避免「2026-01-05」这种长文本挤爆图表。"""
        data = {"2026-01-05": 0, "2026-01-06": 0}
        labels = ov._x_labels(data, 1)
        self.assertEqual([lb.label.value for lb in labels], ["05", "06"])


def walk_controls(node, predicate, found, depth=0):
    """展开声明式组件树，收集所有满足 predicate 的控件。"""
    if depth > 30:
        return
    if predicate(node):
        found.append(node)
    if isinstance(node, Component):
        body = Renderer(node).render(node.fn, *node.args, **node.kwargs)
        walk_controls(body, predicate, found, depth + 1)
        return
    for attr in ("controls", "content", "body", "actions", "title", "items", "outlet"):
        value = getattr(node, attr, None)
        if value is None:
            continue
        for item in (value if isinstance(value, (list, tuple)) else [value]):
            if isinstance(item, (ft.Control, Component)):
                walk_controls(item, predicate, found, depth + 1)


class TestAuditUi(unittest.TestCase):
    """审计台账弹窗与 ⋮ 菜单的结构约束。"""

    def _walk(self, node, predicate, found, depth=0):
        walk_controls(node, predicate, found, depth)

    def test_dialog_has_no_delete_or_export(self):
        job = JobService.create(f"审计UI-{datetime.now().timestamp()}", "通用工作")
        LogService.record(job.id, "上传附件", "新增 1 个文件")
        dlg = audit_page.AuditDialog(job=job)

        buttons, labels = [], []
        self._walk(dlg, lambda n: isinstance(n, ft.IconButton), buttons)
        self._walk(dlg, lambda n: isinstance(n, ft.Text) and bool(n.value), labels)
        texts = [t.value for t in labels]
        # ft.Button("新增记录") 的 content 是字符串而非 Text 控件，需单独取
        action_texts = []
        for action in dlg.actions:
            content = getattr(action, "content", None)
            action_texts.append(content if isinstance(content, str) else getattr(content, "value", ""))
        self.assertEqual(buttons, [], "记录右侧不应再有删除按钮")
        self.assertNotIn("导出", texts + action_texts, "底部不应再有导出按钮")
        self.assertIn("新增记录", action_texts)
        self.assertIn("关闭", action_texts)
        self.assertIn("上传附件", " ".join(texts))

    def test_dialog_has_timeline_vertical_line(self):
        job = JobService.create(f"审计纵线-{datetime.now().timestamp()}", "通用工作")
        LogService.record(job.id, "新建任务", "任务A")
        dlg = audit_page.AuditDialog(job=job)

        line = dlg.timeline_line
        self.assertEqual(line.width, 1)
        self.assertEqual(line.left, audit_page.TIMELINE_LINE_X)
        self.assertTrue(line.visible, "有记录时纵线应可见")
        stacks = []
        self._walk(dlg, lambda n: isinstance(n, ft.Stack), stacks)
        self.assertEqual(len(stacks), 1)
        self.assertIn(line, stacks[0].controls)

    def test_timeline_line_hidden_when_empty(self):
        from data.model import Log
        job = JobService.create(f"审计空态-{datetime.now().timestamp()}", "通用工作")
        Log.delete().where(Log.job == job.id).execute()
        dlg = audit_page.AuditDialog(job=job)
        self.assertFalse(dlg.timeline_line.visible)

    def test_more_menu_only_has_view_audit(self):
        """⋮ 菜单里的「导出审计台账」已取消。"""
        job = JobService.create(f"菜单UI-{datetime.now().timestamp()}", "通用工作")
        ctx._context_page.set(_FakePage(f"/job/{job.id}"))
        with Renderer().with_context():
            router = get_urls()
        body = Renderer(router).render(router.fn, *router.args, **router.kwargs)
        menus = []
        self._walk(body, lambda n: isinstance(n, ft.PopupMenuButton), menus)
        self.assertEqual(len(menus), 1)
        items = menus[0].items
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].content, "查看审计台账")


class TestProgressChartRender(unittest.TestCase):
    """工作进展折线图最终渲染结果：纵轴整数刻度、三按钮、默认 7 天。"""

    def test_rendered_chart_structure(self):
        ctx._context_page.set(_FakePage("/overview"))
        with Renderer().with_context():
            root = Renderer().render(ov.overview)

        charts, texts = [], []
        walk_controls(root, lambda n: isinstance(n, LineChart), charts)
        walk_controls(root, lambda n: isinstance(n, ft.Text) and bool(n.value), texts)
        self.assertEqual(len(charts), 1)
        chart = charts[0]

        # 纵轴：自定义刻度全是整数，步长是整数且与网格线对齐
        values = [lb.value for lb in chart.left_axis.labels]
        self.assertTrue(values)
        self.assertTrue(all(float(v).is_integer() for v in values), values)
        self.assertEqual(chart.left_axis.label_spacing, int(chart.left_axis.label_spacing))
        self.assertEqual(chart.horizontal_grid_lines.interval,
                         chart.left_axis.label_spacing)
        self.assertTrue(all(lb.label.no_wrap for lb in chart.left_axis.labels))

        # 默认 7 天：横坐标 0..6，采样步长与天数匹配
        self.assertEqual(chart.min_x, 0)
        self.assertEqual(chart.max_x, DEFAULT_TREND_DAYS - 1)
        self.assertEqual(chart.bottom_axis.label_spacing, ov._x_step(DEFAULT_TREND_DAYS))

        # 右上角三个范围切换按钮
        labels = [t.value for t in texts]
        for text, _ in TREND_RANGES:
            self.assertIn(text, labels)


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
        titles, radii, tip = ov._pie_state(items, 18, None)
        self.assertEqual(titles, ["未开始", "执行中"])
        self.assertEqual(radii, [ov.PIE_NORMAL_RADIUS, ov.PIE_NORMAL_RADIUS])
        titles, radii, tip = ov._pie_state(items, 18, 0)
        self.assertEqual(titles, ["15 (83%)", "执行中"])
        self.assertEqual(radii, [ov.PIE_HOVER_RADIUS, ov.PIE_NORMAL_RADIUS])
        self.assertIn("83%", tip)
        titles, _, _ = ov._pie_state(items, 18, -1)
        self.assertEqual(titles, ["未开始", "执行中"])

    def test_pie_hover_event_does_not_freeze(self):
        """回归：声明式组件里 hover 回调不得对冻结控件 update()。

        曾在 on_hover 里直接改 section 属性 + chart.update()，触发
        RuntimeError: Frozen control cannot be updated。用真实 Renderer 展开
        组件树、派发 hover 事件，确保状态驱动重渲染不再抛该异常。
        """
        ctx._context_page.set(_FakePage("/overview"))
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
