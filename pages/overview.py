import datetime

import flet as ft
from flet import TextAlign
from flet_charts import (
    ChartAxis, ChartAxisLabel, ChartGridLines, LineChart, LineChartData,
    LineChartDataPoint, PieChart, PieChartSection,
)

from common.util import datetime_2_date_str
from constant import (
    BORDER_RADIUS, COLOR_DANGER, COLOR_JOB_FINISH, COLOR_PRIMARY, COLOR_SAFE,
    COLOR_TASK_FINISH, COLOR_TEXT, COLOR_WARN, DATE_TIME_FMT,
    DEFAULT_TREND_DAYS, TREND_RANGES,
    BG_PANEL, Status,
)
from data.model import Job, Log
from data.service import JobService, LogService, TaskService
from theme import (
    BG_CARD, BG_CARD_ALT, BORDER, BORDER_ACCENT, MUTED, ACCENT, SLATE,
    TEXT_BRIGHT, TEXT, TRANSPARENT,
    DANGER, SAFE, FS_BASE, FS_METRIC, FS_XL, FS_MD, FS_SM, glow, GLOW_SOFT,
    RADIUS_MD, RADIUS_SM, FONT_MONO,
)


@ft.component
def overview():
    return ft.Column(
        [
            ft.Container(height=5),
            Top(),
            ft.Container(height=5),
            Center(),
            ft.Container(height=5),
            Bottom(),
        ],
        expand=True
    )


# ---------------------------------------------------------------- 第 1 行：统计卡片
def _change_badge(change: int) -> ft.Control:
    """相比上周的变动徽标：↑增加(绿) / ↓减少(红) / —持平(灰)。"""
    if change > 0:
        text, color, icon = f"+{change} 较上周", SAFE, ft.Icons.TRENDING_UP
    elif change < 0:
        text, color, icon = f"{change} 较上周", DANGER, ft.Icons.TRENDING_DOWN
    else:
        text, color, icon = "与上周持平", SLATE, ft.Icons.REMOVE
    return ft.Row([
        ft.Icon(icon, size=FS_MD, color=color),
        ft.Text(text, size=FS_SM, color=color),
    ], spacing=0)


def _stat_card(title, value, change: int = 0) -> ft.Control:
    return ft.Container(
        expand=True, height=124, padding=ft.Padding(18, 12, 18, 10),
        border=ft.Border(
            left=ft.BorderSide(1, BORDER_ACCENT),
            right=ft.BorderSide(1, BORDER_ACCENT),
            top=ft.BorderSide(1, BORDER_ACCENT),
            bottom=ft.BorderSide(1, BORDER_ACCENT),
        ),
        border_radius=RADIUS_MD,
        bgcolor=BG_CARD,
        shadow=glow(GLOW_SOFT, blur=20),
        content=ft.Column(
            [
                ft.Text(title, size=FS_BASE, color=MUTED),
                ft.Row(
                    controls=[
                        ft.Text(
                            str(value),
                            size=FS_METRIC,
                            weight=ft.FontWeight.BOLD,
                            color=ACCENT,
                            font_family=FONT_MONO,
                        ),
                        ft.Container(
                            content=_change_badge(change),
                            padding=ft.Padding(left=0, top=0, right=0, bottom=10),  # 下沉量，按观感调
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.END,  # 关键：贴行底部
                )
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
    )


@ft.component
def Top():
    """第一行：工作/任务总数与完成数，附周环比徽标。"""
    total_job_c = JobService.total()
    finish_job = JobService.total(status=Status.FINISHED)
    total_task_c = TaskService.total()
    finish_task = TaskService.total(status=Status.FINISHED)

    # 相比上周：总数按创建/开始时间，已完成按完成时间
    job_change = JobService.week_change()
    finish_job_change = JobService.week_change(Status.FINISHED, 'end_time')
    task_change = TaskService.week_change()
    finish_task_change = TaskService.week_change(Status.FINISHED, 'end_time')

    return ft.Row([
        _stat_card("工作总数", total_job_c, job_change),
        _stat_card("已完成工作", finish_job, finish_job_change),
        _stat_card("任务总数", total_task_c, task_change),
        _stat_card("已完成任务", finish_task, finish_task_change),
    ], spacing=16)


# ---------------------------------------------------------------- 第 2 行：饼图 + 工作进展
PIE_NORMAL_RADIUS = 84
PIE_HOVER_RADIUS = 94
PIE_NORMAL_TITLE = ft.TextStyle(size=FS_BASE, color=TEXT_BRIGHT, weight=ft.FontWeight.BOLD)
PIE_HOVER_TITLE = ft.TextStyle(size=FS_MD, color=TEXT_BRIGHT, weight=ft.FontWeight.BOLD)


def _pct(value: int, total: int) -> int:
    return round(value / total * 100) if total else 0


def _pie_state(items, total, hovered):
    """按 hover 索引算出扇区标题 / 半径 / tooltip（纯函数，便于测试）。

    默认标题是状态名；悬浮某块时该块显示「数量 (占比)」，其余保持原样。
    """
    titles, radii = [], []
    for i, (status, value) in enumerate(items):
        active = i == hovered
        titles.append(f"{value} ({_pct(value, total)}%)" if active else status)
        radii.append(PIE_HOVER_RADIUS if active else PIE_NORMAL_RADIUS)
    if hovered is not None and 0 <= hovered < len(items):
        status, value = items[hovered]
        tooltip = f"{status}：{value} 个（{_pct(value, total)}%）"
    else:
        tooltip = "悬浮查看各状态数量与占比"
    return titles, radii, tooltip


@ft.component
def PieChartPanel():
    """任务分布饼图：声明式组件，hover 只改 state，不触碰冻结控件。"""
    hovered, set_hovered = ft.use_state(None)
    data = JobService.ratio()
    total = sum(data.values())
    items = list(data.items())
    titles, radii, tooltip = _pie_state(items, total, hovered)

    sections = [
        PieChartSection(
            value=value, title=titles[i], color=Status.color(status),
            radius=radii[i],
            title_style=PIE_HOVER_TITLE if i == hovered else PIE_NORMAL_TITLE,
        )
        for i, (status, value) in enumerate(items)
    ]

    def on_hover(e):
        idx = e.section_index
        set_hovered(idx if idx is not None and 0 <= idx < len(items) else None)

    chart = PieChart(
        sections=sections,
        sections_space=2,
        center_space_radius=40,
        expand=True,
        tooltip=tooltip,
        on_event=on_hover,
    )
    return ft.Column([
        ft.Text("任务分布饼图", color=COLOR_PRIMARY, size=FS_XL, weight=ft.FontWeight.BOLD),
        chart,
    ])


def _cumulative_peak(trend: dict) -> int:
    """累计曲线的最高峰值。"""
    running = peak = 0
    for v in trend.values():
        running += v
        peak = max(peak, running)
    return peak


# 纵轴刻度步长候选：全部为整数，避免 fl_chart 自动推算出 0.5 这类小数刻度。
Y_STEPS = (1, 2, 5, 10, 20, 50, 100)

# 横轴标签区高度：字号 11 的文字行高约 14，11 会把数字上沿切掉，这里留够空间。
X_LABEL_SIZE = 18


def _y_axis(peak: int) -> tuple[int, int]:
    """纵轴上限与刻度步长。

    fl_chart 的自动刻度会按 0.5 之类的步长生成 3.5 / 2.5 这类小数，且窄轴
    会把「3.5」折成两行。这里统一取整数步长，交由调用方显式提供刻度。
    """
    step = Y_STEPS[-1]
    for candidate in Y_STEPS:
        if peak <= candidate * 5:
            step = candidate
            break
    top = step * max(1, -(-peak // step))
    return max(top, 4), step


def _y_label_size(max_y: int) -> int:
    """纵轴刻度占位宽度：按最长刻度文字估算，保证不被裁切也不换行。"""
    return max(24, 8 + 7 * len(str(max_y)))


def _y_labels(max_y: int, step: int) -> list[ChartAxisLabel]:
    """纵轴刻度：只有整数，且不换行。"""
    return [
        ChartAxisLabel(value=v, label=ft.Text(str(v), color=MUTED, size=FS_SM, no_wrap=True))
        for v in range(0, max_y + 1, step)
    ]


def _legend_dot(color: str, label: str) -> ft.Control:
    return ft.Row([
        ft.Container(width=18, height=4, border_radius=2, bgcolor=color),
        ft.Text(label, size=FS_SM, color=TEXT),
    ], spacing=6)


def _series(data: dict, color: str, label: str) -> LineChartData:
    # 累加为累计完成数，曲线更有趋势感；每个点带 tooltip
    points = []
    running = 0
    for idx, value in enumerate(data.values()):
        running += value
        points.append(LineChartDataPoint(
            idx, running,
            tooltip=f"{label} · {value} 个（累计 {running}）",
            show_tooltip=True,
        ))
    return LineChartData(
        points=points, color=color, stroke_width=3,
        point=True, selected_point=True, curved=True,
    )


def _x_step(days: int) -> int:
    """横轴刻度间隔：天数越多抽得越稀，避免日期挤成一团。"""
    return 1 if days <= 10 else (2 if days <= 20 else 3)


def _x_labels(data: dict, step: int) -> list[ChartAxisLabel]:
    """横轴刻度：只显示「日」，且位置必须与 fl_chart 的采样点完全一致。

    fl_chart 用 ``label_spacing`` 决定采样步长：起点 0，每次加 step，
    并且总是额外带上轴的最大值。自定义标签只有在取值精确命中采样点时才
    会被渲染，否则是空白，所以这里的下标集合必须与采样集合一致。
    """
    total = len(data)
    indexes = sorted(set(range(0, total, step)) | {total - 1})
    return [
        ChartAxisLabel(
            value=idx,
            label=ft.Text(list(data)[idx].split("-")[-1], color=MUTED,
                          size=FS_SM, no_wrap=True),
        )
        for idx in indexes
    ]


def _range_button(label: str, active: bool, on_click) -> ft.Control:
    """天数切换按钮：选中态用青色描边 + 高亮文字。"""
    return ft.Container(
        content=ft.Text(
            label, size=FS_SM,
            color=ACCENT if active else MUTED,
            weight=ft.FontWeight.BOLD if active else ft.FontWeight.W_400,
        ),
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border_radius=RADIUS_SM,
        bgcolor=BG_CARD_ALT if active else TRANSPARENT,
        border=ft.Border.all(1, BORDER_ACCENT if active else BORDER),
        ink=True,
        on_click=on_click,
    )


@ft.component
def ProgressChart():
    """工作进展折线图：右上角切换统计范围（近 7 / 15 / 30 天）。"""
    days, set_days = ft.use_state(DEFAULT_TREND_DAYS)

    job_trend = JobService.finish_trend(days)
    task_trend = TaskService.finish_trend(days)
    peak = max(_cumulative_peak(job_trend), _cumulative_peak(task_trend))
    max_y, y_step = _y_axis(peak)
    x_step = _x_step(days)

    chart = LineChart(
        data_series=[
            _series(job_trend, COLOR_JOB_FINISH, "完成工作"),
            _series(task_trend, COLOR_TASK_FINISH, "完成任务"),
        ],
        left_axis=ChartAxis(
            labels=_y_labels(max_y, y_step),
            show_labels=True,
            label_spacing=y_step,
            label_size=_y_label_size(max_y),
            title=ft.Text("数量", size=FS_SM, color=MUTED), title_size=FS_SM,
        ),
        bottom_axis=ChartAxis(
            labels=_x_labels(job_trend, x_step),
            show_labels=True,
            label_spacing=x_step,
            label_size=X_LABEL_SIZE,
        ),
        min_x=0, max_x=days - 1, min_y=0, max_y=max_y,
        horizontal_grid_lines=ChartGridLines(interval=y_step, color=BORDER, width=1),
        # 注意：LineChart.tooltip 只接受 LineChartTooltip 类型，传字符串会导致
        # 序列化失败、整图渲染不出（露出灰底）。数据点的 tooltip 在各点上单独设置。
        bgcolor="#FF070D1B",
        expand=True,
    )
    legend = ft.Row([
        _legend_dot(COLOR_JOB_FINISH, "完成工作"),
        _legend_dot(COLOR_TASK_FINISH, "完成任务"),
    ], spacing=18)
    ranges = ft.Row([
        _range_button(label, value == days, lambda e, v=value: set_days(v))
        for label, value in TREND_RANGES
    ], spacing=8)

    return ft.Column([
        ft.Row([
            ft.Text("工作进展", size=FS_XL, color=ACCENT),
            ft.Row([legend, ranges], spacing=18),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER),
        chart,
    ], spacing=10, expand=True)


@ft.component
def Center():
    """第二行：左饼图 + 右工作进展折线图。"""
    return ft.Row([
        ft.Container(
            width=360, height=330, bgcolor=BG_CARD,
            border_radius=RADIUS_MD, padding=ft.Padding(18, 12, 18, 12),
            content=PieChartPanel(),
        ),
        ft.Container(
            expand=True, bgcolor=BG_PANEL, height=330,
            border_radius=BORDER_RADIUS, padding=ft.Padding(18, 12, 18, 12),
            content=ProgressChart(),
        )
    ], spacing=16)



# ---------------------------------------------------------------- 第 3 行：最新更新 + 即将逾期
def _panel(content, expand=False, width=None) -> ft.Control:
    """两张卡片共用的描边容器，避免重复内联。"""
    return ft.Container(
        width=width, expand=expand, height=270, padding=ft.Padding(16, 12, 16, 12),
        border=ft.Border(
            left=ft.BorderSide(1, BORDER_ACCENT),
            right=ft.BorderSide(1, BORDER_ACCENT),
            top=ft.BorderSide(1, BORDER_ACCENT),
            bottom=ft.BorderSide(1, BORDER_ACCENT),
        ),
        border_radius=RADIUS_MD,
        bgcolor=BG_CARD,
        content=content,
    )


def _latest_job_row(log: Log) -> ft.Control:
    """最新更新工作的一行：时间/动作取自审计日志，其余信息取自所属工作。"""
    job = log.job
    return ft.Container(
        data=job,
        on_click=lambda e: ft.context.page.navigate(f"/job/{job.id}"),
        padding=10,
        border_radius=4,
        content=ft.Row([
            ft.Container(width=10, height=10, border_radius=99), ft.Container(width=10),
            ft.Column(
                [
                    ft.Text(
                        job.name,
                        color=ACCENT,
                        size=FS_BASE,
                        weight=ft.FontWeight.W_500,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS
                    ),
                    ft.Text(
                        f"{job.type} | {datetime_2_date_str(log.created_time, DATE_TIME_FMT)} | {log.name}",
                        size=FS_SM,
                        color=MUTED),
                ],
                expand=True),
            ft.Text(job.status, size=FS_MD),
            ft.Icon(ft.Icons.ARROW_FORWARD_IOS, size=FS_BASE, color=SLATE),
        ]),
    )


def _latest_panel() -> ft.Control:
    return ft.Column([
        ft.Text("最新更新工作", size=FS_XL, color=ACCENT),
        ft.ListView(
            controls=[_latest_job_row(log) for log in LogService.latest_updates()],
            spacing=4,
        )
    ])


# 即将逾期表格的列定义：(标题, flex)。名称占 3，其余按内容分配，末列图标固定。
EXPIRE_COLS = (
    ("名称", 3), ("类型", 2), ("优先级", 1),
    ("结束时间", 2), ("剩余时长", 2), ("状态", 2),
)
EXPIRE_ICON_W = 28


def _expire_job(job: Job) -> ft.Control:
    day = (job.end_time.date() - datetime.date.today()).days
    if day < 0:
        text, color = f"已逾期{-day}天", COLOR_DANGER
    elif day <= 3:
        text, color = str(day), COLOR_WARN
    else:
        text, color = str(day), COLOR_SAFE

    name = ft.Text(job.name, size=FS_MD, color=ACCENT,
                   max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
    return ft.Row([
        ft.Container(
            expand=3, tooltip=job.name,
            on_click=lambda e: ft.context.page.navigate(f"/job/{job.id}"),
            content=name,
        ),
        ft.Text(job.type, size=FS_MD, color=COLOR_TEXT, text_align=TextAlign.CENTER, expand=2),
        ft.Text(job.priority, size=FS_MD, color=COLOR_TEXT, text_align=TextAlign.CENTER, expand=1),
        ft.Text(job.end_time.strftime("%Y-%m-%d"), size=FS_MD, color=COLOR_TEXT,
                text_align=TextAlign.CENTER, expand=2),
        ft.Text(text, size=FS_MD, color=color, text_align=TextAlign.CENTER, expand=2),
        ft.Text(job.status, size=FS_MD, color=COLOR_TEXT, text_align=TextAlign.CENTER, expand=2),
        ft.Icon(ft.Icons.WARNING_AMBER, size=FS_BASE, color=COLOR_WARN,
                width=EXPIRE_ICON_W) if day < 3 else ft.Container(width=EXPIRE_ICON_W),
    ], spacing=8)


def _expire_panel() -> ft.Control:
    header = ft.Row([
                        ft.Text(h, size=FS_MD, color=MUTED, text_align=TextAlign.CENTER, expand=f)
                        for h, f in EXPIRE_COLS
                    ] + [ft.Container(width=EXPIRE_ICON_W)], spacing=8)
    return ft.Column([
        ft.Text("即将逾期工作", size=FS_XL, color=ACCENT),
        header,
        ft.Divider(color=BORDER, height=1),
        ft.ListView(
            controls=[_expire_job(job) for job in JobService.expire()],
            spacing=6, expand=True,
        )
    ], spacing=10, expand=True)


@ft.component
def Bottom():
    """第三行：最新更新工作 + 即将逾期工作。"""
    return ft.Row([
        _panel(_latest_panel(), width=440),
        _panel(_expire_panel(), expand=True),
    ], spacing=16)
