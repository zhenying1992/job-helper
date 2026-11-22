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

from data.service import JobService, LogService, TaskService  # noqa: E402
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


class TestStyleAlignmentUi(unittest.TestCase):
    """本轮样式调整：状态语义色、轴标题间距、必填红星、下拉亮字。"""

    def test_expire_status_uses_semantic_color(self):
        """即将逾期表格的状态列与工作列表一致，用 Status.color。"""
        job = JobService.create(f"逾期色-{datetime.now().timestamp()}", "通用工作")
        JobService.update(job.id, status="执行中")
        row = ov._expire_job(JobService.get(job.id))
        cells = []
        walk_controls(row, lambda n: isinstance(n, ft.Text), cells)
        status_texts = [c for c in cells if c.value == "执行中"]
        self.assertEqual(len(status_texts), 1)
        from constant import Status
        self.assertEqual(status_texts[0].color, Status.color("执行中"))

    def test_chart_title_size_leaves_gap(self):
        ctx._context_page.set(_FakePage("/overview"))
        with Renderer().with_context():
            root = Renderer().render(ov.overview)
        charts = []
        walk_controls(root, lambda n: isinstance(n, LineChart), charts)
        self.assertGreater(charts[0].left_axis.title_size, 11)

    def test_job_detail_status_is_plain_text(self):
        """工作详情状态：纯文字语义色，不再是带底色的徽章。"""
        from pages.job import JobDetails
        job = JobService.create(f"详情状态-{datetime.now().timestamp()}", "通用工作",
                                status="执行中")
        ctx._context_page.set(_FakePage(f"/job/{job.id}"))
        with Renderer().with_context():
            body = Renderer().render(JobDetails, job)
        texts = []
        walk_controls(body, lambda n: isinstance(n, ft.Text) and n.value == "执行中", texts)
        self.assertTrue(texts)
        from constant import Status
        self.assertEqual(texts[0].color, Status.color("执行中"))

    def test_new_job_form_helpers(self):
        """必选项红星与下拉亮字由公共辅助生成（两个弹窗共用）。"""
        from theme import DANGER, TEXT_BRIGHT, form_option, required_label
        label = required_label("工作名")
        self.assertEqual([s.text for s in label.spans], ["工作名", " *"])
        self.assertEqual(label.spans[1].style.color, DANGER)
        option = form_option("高")
        self.assertEqual(option.key, "高")
        self.assertEqual(option.content.color, TEXT_BRIGHT)

    def test_filter_dropdowns_use_dark_theme(self):
        """工作列表筛选栏两个下拉：暗底青描边 + 弹出菜单深底 + 选项冷白字。"""
        from theme import (BG_INPUT, BG_PANEL, BORDER_STRONG, ACCENT_BRIGHT,
                           TEXT_BRIGHT, dark_dropdown, dark_option)
        from pages.jobs import jobs_view

        # helper 层：收起态 + 弹出菜单 + 选项样式
        dd = dark_dropdown([dark_option("", "全部")])
        self.assertEqual(dd.bgcolor, BG_INPUT)
        self.assertEqual(dd.color, TEXT_BRIGHT)
        self.assertEqual(dd.border_color, BORDER_STRONG)
        self.assertEqual(dd.focused_border_color, ACCENT_BRIGHT)
        self.assertIsNotNone(dd.menu_style)
        self.assertEqual(dd.menu_style.bgcolor, BG_PANEL)
        opt = dd.options[0]
        self.assertEqual(opt.content.color, TEXT_BRIGHT)
        self.assertIsNotNone(opt.style)

        # 渲染层：筛选栏两个下拉都来自 dark_dropdown（menu_style 非空）
        from data.service import PluginService
        plugin = PluginService().create("稽查案件", 1, "", "jicha.py")
        ctx._context_page.set(_FakePage("/jobs"))
        try:
            with Renderer().with_context():
                body = Renderer().render(jobs_view)
            dds = []
            walk_controls(body, lambda n: isinstance(n, ft.Dropdown), dds)
            filters = [d for d in dds if d.label in ("工作类型", "工作状态")]
            self.assertEqual(len(filters), 2)
            self.assertTrue(all(d.menu_style is not None for d in filters),
                            "筛选下拉必须带暗色 menu_style，否则弹出层是系统浅色")

            # 类型筛选必须含插件注入的类型，且全部选项都是暗色样式
            type_filter = next(d for d in filters if d.label == "工作类型")
            texts = [o.text for o in type_filter.options]
            self.assertIn("全部", texts)
            self.assertIn("通用工作", texts)
            self.assertIn("稽查案件", texts, "筛选栏漏掉了插件注入的工作类型")
            self.assertTrue(all(o.style is not None and o.content.color == TEXT_BRIGHT
                                for o in type_filter.options),
                            "每个选项都需显式暗色样式，否则首项/选中项是浅色看不清")
        finally:
            # walk_controls 会重新渲染 Component，删除必须放到所有断言之后
            PluginService().delete(plugin.id)

    def test_filter_dropdowns_reflect_selected_state(self):
        """下拉必须回显当前筛选 state：选了'阻塞中'就不能还显示'全部'。"""
        from common.pagination import Pagination
        from pages.jobs import JobsView

        ctx._context_page.set(_FakePage("/jobs"))
        with Renderer().with_context():
            body = Renderer().render(
                JobsView,
                current=1, set_current=lambda v: None,
                page_size=10, set_page_size=lambda v: None,
                keyword="", set_keyword=lambda v: None,
                type="稽查案件", set_type=lambda v: None,
                status="阻塞中", set_status=lambda v: None,
                refresh_flag=True, set_refresh_flag=lambda v: None,
                pagination=Pagination(1, 10),
            )
        dds = []
        walk_controls(body, lambda n: isinstance(n, ft.Dropdown), dds)
        filters = {d.label: d for d in dds if d.label in ("工作类型", "工作状态")}
        self.assertEqual(filters["工作类型"].value, "稽查案件",
                         "类型下拉写死 value='' 会导致选了插件类型仍显示'全部'")
        self.assertEqual(filters["工作状态"].value, "阻塞中",
                         "状态下拉写死 value='' 会导致选了'阻塞中'仍显示'全部'")


class TestTaskUi(unittest.TestCase):
    """任务列表/弹窗：操作列可见、日期暗色末行、混合时区不闪退。"""

    @staticmethod
    def _walk(node, depth=0, seen=None, out=None):
        if seen is None:
            seen = set()
        if out is None:
            out = []
        if depth > 14:
            return out
        if isinstance(node, Component):
            if id(node) in seen:
                return out
            seen.add(id(node))
            TestTaskUi._walk(Renderer(node).render(node.fn, *node.args, **node.kwargs),
                             depth + 1, seen, out)
            return out
        out.append(node)
        for attr in ("controls", "content", "actions", "cells"):
            v = getattr(node, attr, None)
            if v is None:
                continue
            for it in (v if isinstance(v, (list, tuple)) else [v]):
                if isinstance(it, (ft.Control, Component)):
                    TestTaskUi._walk(it, depth + 1, seen, out)
        return out

    def _job(self):
        job = JobService.create(f"任务UI-{datetime.now().timestamp()}", "通用工作")
        TaskService.create(job.id, "任务A", status="未开始")
        ctx._context_page.set(_FakePage(f"/job/{job.id}"))
        return job

    def test_task_table_keeps_operation_column(self):
        """固定列宽+默认列间距曾把末列挤出面板，编辑/删除按钮消失。"""
        job = self._job()
        from pages.task.list import task_list_view
        with Renderer().with_context():
            comp = task_list_view(job=job)
            body = Renderer(comp).render(comp.fn, *comp.args, **comp.kwargs)
            nodes = self._walk(body)
        table = next(n for n in nodes if isinstance(n, ft.DataTable) and n.columns)
        self.assertEqual([c.label.value for c in table.columns][-1], "操作")
        self.assertEqual(len(table.columns), 9)
        self.assertEqual(table.column_spacing, 10)
        ops = table.rows[0].cells[-1].content
        self.assertEqual(len([n for n in self._walk(ops)
                              if isinstance(n, ft.TextButton)]), 2)

    def test_date_picker_dark_and_last_row(self):
        """日期选择器改暗色科技感、默认日历模式，并置于表单末行。"""
        job = self._job()
        from pages.task import CreateTaskDialog
        from theme import BG_INPUT, ACCENT_SOFT
        dlg = CreateTaskDialog(job_id=job.id, on_saved=None)
        dlg.init()
        self.assertEqual(dlg.start_picker.entry_mode, ft.DatePickerEntryMode.CALENDAR)
        dark = [n for n in self._walk(dlg.content)
                if isinstance(n, ft.Button) and n.bgcolor == BG_INPUT]
        self.assertEqual(len(dark), 2)
        self.assertEqual(dark[0].color, ACCENT_SOFT)
        cols = dlg.content.content.controls
        self.assertIsInstance(cols[-1], ft.Row)
        self.assertEqual(len(cols[-1].controls), 2)

    def test_forms_share_dark_theme_and_aligned_widths(self):
        """新建工作/任务两弹窗共用暗色科技感样式，标签描述与两列等宽。"""
        from theme import (BG_INPUT, ACCENT_BRIGHT, TEXT_BRIGHT,
                           FORM_FULL_W, FORM_COL_W, FORM_GAP)
        job = self._job()
        from pages.task import CreateTaskDialog

        dlg = CreateTaskDialog(job_id=job.id, on_saved=None)
        dlg.init()
        fields = [dlg.name_field, dlg.status_field, dlg.assignee_field,
                  dlg.hours_field, dlg.tags_field, dlg.desc_field]
        # 所有字段统一暗色底/青描边/亮字
        for fld in fields:
            self.assertEqual(fld.bgcolor, BG_INPUT)
            self.assertEqual(fld.border_color, ACCENT_BRIGHT)
            self.assertEqual(fld.color, TEXT_BRIGHT)
        # 标签/描述全宽 == 两列合计，右侧不再多出一截
        self.assertEqual(FORM_FULL_W, FORM_COL_W * 2 + FORM_GAP)
        self.assertEqual(dlg.desc_field.width, FORM_FULL_W)
        self.assertEqual(dlg.tags_field.width, dlg.desc_field.width)
        self.assertEqual(dlg.name_field.width * 2 + FORM_GAP, FORM_FULL_W)
        # 下拉选项亮字
        self.assertTrue(all(o.content.color == TEXT_BRIGHT
                            for o in dlg.status_field.options))

    def test_valid_range_mixed_timezone(self):
        """日历选出的 aware 与表单初始 naive 混合比较不得抛异常闪退。"""
        from datetime import timezone
        from pages.task import _valid_range

        class P:
            def __init__(self, v):
                self.value = v

        aware = datetime(2026, 11, 22, tzinfo=timezone.utc)
        naive = datetime(2026, 11, 23)
        late = datetime(2026, 11, 25, tzinfo=timezone.utc)
        self.assertTrue(_valid_range(P(aware), P(naive)))
        self.assertTrue(_valid_range(P(naive), P(late)))
        self.assertFalse(_valid_range(P(late), P(naive)))


class TestSettingUi(unittest.TestCase):
    """配置中心：两侧顶部对齐、插件空态、按文件恢复。"""

    def _setting_root(self):
        from pages import setting
        ctx._context_page.set(_FakePage("/setting"))
        with Renderer().with_context():
            comp = setting.setting_view()
            return Renderer(comp).render(comp.fn, *comp.args, **comp.kwargs)

    def test_menu_and_body_top_aligned(self):
        root = self._setting_root()
        self.assertEqual(root.vertical_alignment, ft.CrossAxisAlignment.START)
        for child in root.controls:
            with Renderer().with_context():
                body = Renderer(child).render(child.fn, *child.args, **child.kwargs)
            self.assertEqual(body.padding, 10)

    def test_plugin_empty_state(self):
        from pages import setting
        from data.service import PluginService
        for p in PluginService().list():
            PluginService().delete(p.id)
        ctx._context_page.set(_FakePage("/setting"))
        with Renderer().with_context():
            comp = setting.PluginContent()
            body = Renderer(comp).render(comp.fn, *comp.args, **comp.kwargs)
        texts = []
        walk_controls(body, lambda n: isinstance(n, ft.Text) and bool(n.value), texts)
        self.assertIn("拖入 .py 插件安装", [t.value for t in texts])
        tables = []
        walk_controls(body, lambda n: isinstance(n, ft.DataTable), tables)
        self.assertEqual(tables, [], "无插件时不应渲染空表头")

    def test_plugin_table_fills_width_and_description_ellipsis(self):
        """插件表横向撑满右侧、描述列 expand、超长单行折叠 + tooltip 看全文。"""
        from pages import setting
        from data.service import PluginService

        desc = "一段非常非常长的插件描述内容" * 12
        PluginService().create("测试插件", 1, desc, "test_plugin.py")
        ctx._context_page.set(_FakePage("/setting"))
        try:
            with Renderer().with_context():
                comp = setting.PluginContent()
                body = Renderer(comp).render(comp.fn, *comp.args, **comp.kwargs)
        finally:
            for p in PluginService().list():
                PluginService().delete(p.id)

        # 横向 STRETCH 约束链：外层 Column → Dropzone → Container → 表格包裹 Column
        self.assertEqual(body.horizontal_alignment, ft.CrossAxisAlignment.STRETCH)
        dropzone = body.controls[-1]
        table_area = dropzone.content.content
        self.assertEqual(table_area.horizontal_alignment, ft.CrossAxisAlignment.STRETCH)
        self.assertTrue(table_area.tight)

        table = table_area.controls[0]
        self.assertIsInstance(table, ft.Column)
        # 弃用 DataTable：表头行 + 数据行都是 Container(content=Row)，由同一
        # render_row() 生成，逐列结构完全一致，从根源保证对齐。
        head_row, data_row = table.controls[0], table.controls[1]
        head_cells, data_cells = head_row.content.controls, data_row.content.controls
        self.assertIsInstance(head_row.content, ft.Row)
        self.assertIsInstance(data_row.content, ft.Row)
        self.assertEqual([c.content.value for c in head_cells],
                         ["名称", "版本", "描述", "安装时间", "操作"])

        # 每列 Container(expand=flex) + alignment=CENTER，描述列 flex 最大
        self.assertEqual([c.expand for c in head_cells], [2, 1, 8, 3, 1])
        self.assertEqual([c.expand for c in data_cells], [2, 1, 8, 3, 1])
        self.assertTrue(all(c.alignment == ft.Alignment.CENTER
                            for c in head_cells + data_cells),
                        "每列内容必须居中，否则表头与数据错位")

        # 描述列超长折叠 + tooltip
        desc_text = data_cells[2].content
        self.assertEqual(desc_text.max_lines, 1)
        self.assertEqual(desc_text.overflow, ft.TextOverflow.ELLIPSIS)
        self.assertEqual(desc_text.tooltip, desc)

        # 表头与数据行逐列对齐：同样的 expand（列宽比例）+ 同样的居中 alignment
        for hc, dc in zip(head_cells[:4], data_cells[:4]):
            self.assertEqual(dc.expand, hc.expand)
            self.assertEqual(dc.alignment, hc.alignment)
        # 末列为操作：表头文本 vs 删除按钮，二者同列同 expand 同居中
        self.assertEqual(data_cells[4].expand, head_cells[4].expand)
        self.assertEqual(data_cells[4].alignment, head_cells[4].alignment)

    def test_restore_uses_file_picker(self):
        import inspect
        from pages import setting
        # do_restore 是 DataContent 内的闭包，源码层面确认其走 FilePicker 选择
        source = inspect.getsource(setting)
        self.assertIn("pick_files(", source)
        self.assertIn("allowed_extensions=[\"db\"]", source)


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


class TestTopoAndCalendarUi(unittest.TestCase):
    """拓扑节点状态色/副信息 + 日历关注任务优先泳道。"""

    def test_topo_node_color_follows_status(self):
        """回归：node.kind 曾是状态串，node_colors 判断 start/end 永远落空，
        所有节点同一灰蓝色。现在按 status 取 Status.color。"""
        from pages.task import topo
        from constant import Status
        from theme import TEXT_SUBTLE

        job = JobService.create(f"拓扑色-{datetime.now().timestamp()}", "通用工作")
        states = ["未开始", "执行中", "阻塞中", "已完成"]
        tks = []
        for i, st in enumerate(states):
            tk = TaskService.create(job.id, f"N{i}", status=st, assignee=f"人{i}",
                                    estimate_hours=i + 1)
            tks.append(tk)
        editor = topo.TaskTopo(job)
        by_text = {n.text: n for n in editor.state.nodes}
        seen = set()
        for i, st in enumerate(states):
            node = by_text[f"N{i}"]
            _, border = topo.node_colors(node)
            self.assertEqual(border, Status.color(st))
            self.assertNotEqual(border, TEXT_SUBTLE)
            seen.add(border)
        self.assertEqual(len(seen), len(states))  # 四种状态四种颜色

        # 副信息随节点数据带入
        n0 = by_text["N0"]
        self.assertEqual(n0.assignee, "人0")
        self.assertEqual(n0.hours, 1)

    def test_calendar_focus_task_takes_front_lane(self):
        """hover/点击的任务即便原本被折叠，也要优先占可见泳道。"""
        import pages.calendar as cal
        from datetime import datetime as dt

        job = JobService.create(f"日历泳道-{datetime.now().timestamp()}", "通用工作")
        tks = [TaskService.create(job.id, f"T{i}", status="执行中",
                                  start_time=dt(2026, 11, 2), end_time=dt(2026, 11, 20))
               for i in range(5)]
        cells = cal._month_window(2026, 11)
        segs = cal._build_segments(tks, cells)
        cal._assign_lanes(segs, focus_id=tks[4].id)
        lane = {getattr(s.task, "id", id(s.task)): s.lane for s in segs}
        self.assertEqual(lane[tks[4].id], 0)
        self.assertTrue(all(lane[tks[i].id] > 0 for i in range(4)))

        # 换关注对象后重新分配，旧的被挤走
        cal._assign_lanes(segs, focus_id=tks[0].id)
        lane = {getattr(s.task, "id", id(s.task)): s.lane for s in segs}
        self.assertEqual(lane[tks[0].id], 0)
        self.assertGreater(lane[tks[4].id], 0)

    def test_calendar_task_lane_stable_across_weeks(self):
        """同一任务跨周所有段必须共享泳道，否则 hover 时无法拼成一条横条。"""
        import pages.calendar as cal
        from datetime import datetime as dt

        job = JobService.create(f"日历跨周-{datetime.now().timestamp()}", "通用工作")
        a = TaskService.create(job.id, "A", start_time=dt(2026, 11, 12),
                               end_time=dt(2026, 11, 17))
        b = TaskService.create(job.id, "B", start_time=dt(2026, 11, 13),
                               end_time=dt(2026, 11, 13))
        cells = cal._month_window(2026, 11)
        segs = cal._build_segments([a, b], cells)
        cal._assign_lanes(segs)
        a_segs = [s for s in segs if s.task.id == a.id]
        self.assertGreater(len(a_segs), 1)
        self.assertEqual(len({s.lane for s in a_segs}), 1,
                         "跨周任务所有段必须在同一泳道")

    def test_calendar_focus_promotes_folded_task_and_demotes_others(self):
        """A(11.12-11.14) 被 X0/X1/X2 挤进更多时，focus A 应把 A 放到
        可见泳道 0，同时把原来的任务顺延——即「把 A 挪出来，把别的挪进去」。"""
        import pages.calendar as cal
        from datetime import datetime as dt

        job = JobService.create(f"日历折叠-{datetime.now().timestamp()}", "通用工作")
        xs = [TaskService.create(job.id, f"X{i}", start_time=dt(2026, 11, 10),
                                 end_time=dt(2026, 11, 15)) for i in range(3)]
        a = TaskService.create(job.id, "A", start_time=dt(2026, 11, 12),
                               end_time=dt(2026, 11, 14))
        bs = [TaskService.create(job.id, f"B{i}", start_time=dt(2026, 11, 13),
                                 end_time=dt(2026, 11, 13)) for i in range(3)]
        tasks = xs + [a] + bs
        cells = cal._month_window(2026, 11)

        segs = cal._build_segments(tasks, cells)
        cal._assign_lanes(segs)
        a_lane = [s.lane for s in segs if s.task.id == a.id][0]
        self.assertGreaterEqual(a_lane, cal.MAX_LANES, "A 原本应被折叠")

        focused = cal._build_segments(tasks, cells)
        cal._assign_lanes(focused, focus_id=a.id)
        a_lane2 = [s.lane for s in focused if s.task.id == a.id][0]
        self.assertEqual(a_lane2, 0, "focus 后 A 必须占可见泳道 0")
        self.assertTrue(all(
            [s.lane for s in focused if s.task.id == t.id][0] > 0 for t in xs
        ), "原占前排的任务应被顺延")

    def test_calendar_range_segs_for_cross_row_drag(self):
        """拖动端点跨行时按日期范围重切段：首尾标记、lane、preview 标记正确。"""
        import pages.calendar as cal
        from datetime import date

        cells = cal._month_window(2026, 11)
        task = type("T", (), {"id": 999, "name": "跨行"})()
        segs = cal._range_segs(task, date(2026, 11, 13), date(2026, 11, 17),
                               cells, lane=1)
        self.assertEqual([(s.row, s.c0, s.c1) for s in segs],
                         [(2, 4, 6), (3, 0, 1)])
        self.assertTrue(all(s.preview and s.lane == 1 and s.multi for s in segs))
        self.assertTrue(segs[0].first and not segs[0].last)
        self.assertTrue(not segs[1].first and segs[1].last)

    def test_calendar_cross_row_drag_uses_range_preview(self):
        """回归：旧实现跨行时只弹提示卡、条不动；新实现必须按日期范围重切段。"""
        import inspect
        import pages.calendar as cal

        src = inspect.getsource(cal.calendar_view)
        self.assertIn("_range_segs(", src, "拖动时必须按目标日期范围重建预览段")
        self.assertIn('"segs":', src, "预览段要进 use_state 驱动重渲染")
        self.assertNotIn("crossed_row", src, "旧的跨行特判像素预览已移除")
        self.assertNotIn('drag.get("k")', src, "旧的像素几何预览已移除")

    def test_calendar_drag_keeps_handle_key_stable(self):
        """回归：pan 期间若把手控件被摘出/换 key，客户端手势中断 → 报错且不实时。

        现在真实段与把手始终留在渲染树、key 固定；预览段是额外 pv- 控件，
        且跨行时自动增长为多段。用真实 Renderer + hook 状态驱动验证。
        """
        import pages.calendar as cal

        ctx._context_page.set(_FakePage("/calendar"))
        job = JobService.create(f"日历拖拽-{datetime.now().timestamp()}", "通用工作")
        TaskService.create(job.id, "DragTask", start_time=datetime(2026, 11, 12),
                           end_time=datetime(2026, 11, 14))

        class Ev:
            def __init__(self, gx, gy):
                self.global_position = ft.Offset(gx, gy)
                self.local_position = ft.Offset(6, 9)
                self.local_delta = ft.Offset(6, 9)

        def walk(node, pred, out):
            if isinstance(node, Component):
                return
            if pred(node):
                out.append(node)
            for attr in ("controls", "content"):
                v = getattr(node, attr, None)
                if v is None:
                    continue
                for x in (v if isinstance(v, (list, tuple)) else [v]):
                    walk(x, pred, out)

        with Renderer().with_context():
            comp = cal.calendar_view()

        def render():
            comp._state.hook_cursor = 0
            return Renderer(comp).render(comp.fn, *comp.args, **comp.kwargs)

        def handles(b):
            out = []
            walk(b, lambda n: isinstance(n, ft.GestureDetector)
                 and isinstance(n.key, str) and n.key.startswith("bar-")
                 and n.key.endswith(("-l", "-r")), out)
            return out

        body = render()
        hs = handles(body)
        self.assertTrue(hs)
        h = [x for x in hs if x.key.endswith("-r")][0]
        h.on_pan_start(Ev(h.left + 6, h.top + 9))

        seen_pv = []
        # 向右下拖 4 帧，跨过至少一行
        for i in range(1, 5):
            h.on_pan_update(Ev(h.left + 6 + i * 180, h.top + 9 + i * 52))
            b2 = render()
            self.assertEqual(
                sorted(x.key for x in handles(b2)), sorted(x.key for x in hs),
                "把手 key 在拖动全程必须稳定，否则手势会被中断",
            )
            pv = []
            walk(b2, lambda n: isinstance(n, ft.Container)
                 and isinstance(n.key, str) and n.key.startswith("pv-")
                 and n.key != "pv-tip", pv)
            seen_pv.append(len(pv))
        # 预览条数量随跨行增长（多段），松手后归零
        self.assertGreater(max(seen_pv), 1, "跨行拖动应出现多段预览条")
        h.on_pan_end(Ev(h.left + 900, h.top + 260))
        b3 = render()
        pv = []
        walk(b3, lambda n: isinstance(n, ft.Container)
             and isinstance(n.key, str) and n.key.startswith("pv-"), pv)
        self.assertEqual(pv, [], "松手后预览层必须清空")

    def test_calendar_hover_does_not_change_lanes(self):
        """回归：hover 若触发 focus→重排泳道，条移到光标下又触发 enter→无限抖动。

        on_enter 只允许 set_hover（高亮），不得 set_focus。
        """
        import inspect
        import pages.calendar as cal

        src = inspect.getsource(cal.calendar_view)
        on_enter = [ln for ln in src.splitlines() if "on_enter=" in ln]
        self.assertTrue(on_enter)
        self.assertTrue(all("set_focus" not in ln for ln in on_enter),
                        "横条 on_enter 不得修改 focus（会导致重排抖动）")

    def test_calendar_bar_meta_and_tooltip(self):
        """横条按宽度塞负责人/工时/标签，tooltip 带描述。"""
        import pages.calendar as cal

        job = JobService.create(f"日历元信息-{datetime.now().timestamp()}", "通用工作")
        task = TaskService.create(
            job.id, "MetaTask", assignee="张三", estimate_hours=6,
            tags=["前端", "紧急"], description="完成接口联调",
        )
        self.assertIn("@张三", cal._bar_meta(task, 200))
        self.assertIn("6h", cal._bar_meta(task, 200))
        self.assertNotIn("#前端", cal._bar_meta(task, 200), "窄条不应塞标签")
        self.assertIn("#前端", cal._bar_meta(task, 400))
        self.assertEqual(cal._bar_meta(task, 40), "", "过窄的条不塞元信息")
        tip = cal._bar_tooltip(task, "MetaTask")
        for bit in ("张三", "6h", "前端", "完成接口联调"):
            self.assertIn(bit, tip)

    def test_calendar_width_uses_resize_event(self):
        """回归：resize 回调读 page.width（1.0.3 无此属性）被吞，
        win_w 恒为 0 → 用默认 1280 → 宽窗口日历右侧留白。"""
        import inspect
        import pages.calendar as cal
        src = inspect.getsource(cal.calendar_view)
        self.assertIn("e.width", src)
        self.assertNotIn("set_win_w(page.width)", src)


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

    def test_job_detail_render_with_aware_task_time(self):
        """历史 aware 时间的任务不得让详情页渲染崩溃（点开即卡死回归）。

        job_view 在 use_state 前调用 sync_progress→time_range 聚合工作时间；
        若 min/max 混合 aware/naive 抛 TypeError，异常被 catch_error 吞掉会
        破坏 Flet hook 栈，表现为点开任务列表卡死且无可见报错。
        """
        from datetime import timezone
        from data.model import Task
        job = JobService.create(f"时区渲染-{datetime.now().timestamp()}", "通用工作")
        t = TaskService.create(job.id, "脏时间任务")
        Task.update(
            start_time=datetime(2026, 5, 1, 8, tzinfo=timezone.utc),
            end_time=datetime(2026, 5, 2, 8, tzinfo=timezone.utc),
        ).where(Task.id == t.id).execute()
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
