"""任务甘特图：左侧任务名 + 右侧按天定位的时间条，逾期/完成按状态着色。

用纯 Flet 控件自绘，避免 LineChart 画甘特时刻度与任务名缺失、观感空旷的问题。
"""

import datetime

import flet as ft

from constant import DATE_FMT, OVERDUE, Status
from data.model import Job
from data.service import TaskService
from theme import (
    ACCENT, BORDER_SOFT, MUTED, SLATE, TEXT, TEXT_BRIGHT, WHITE,
    RADIUS_MD, FS_SM, FS_MD, glow,
)

NAME_W = 130       # 左侧任务名列宽（冻结，不随轨道横向滚动）
TRACK_W = 900      # 时间条轨道基准宽度（跨度小时按此均分）
MIN_DAY_W = 48     # 每日最小宽度：小于此值 MM-DD 标签会挤成碎片
HEADER_H = 28      # 日期刻度表头高度
ROW_H = 32         # 每行高度
BAR_H = 18         # 时间条高度


def _as_date(value):
    return value.date() if hasattr(value, 'date') else value


def _bar_color(task) -> str:
    """逾期优先标红，其余按状态色。"""
    if task.status != Status.FINISHED and _as_date(task.end_time) < datetime.date.today():
        return Status.color(OVERDUE)
    return Status.color(task.status)


def _range(tasks: list):
    """计算时间轴范围：覆盖全部任务，且至少含今天起 7 天。"""
    today = datetime.date.today()
    dates = [today, today + datetime.timedelta(days=6)]
    for t in tasks:
        dates += [_as_date(t.start_time), _as_date(t.end_time)]
    lo, hi = min(dates), max(dates)
    return lo, (hi - lo).days + 1


@ft.component
def TaskGantt(job: Job):
    """任务甘特图：按天定位的时间条，逾期/完成按状态着色。"""

    tasks = TaskService.query(job.id)
    lo, span = _range(tasks)
    # 每日至少 MIN_DAY_W，保证 MM-DD 标签完整；跨度小时仍按 TRACK_W 均分铺满
    day_w = max(TRACK_W / span, MIN_DAY_W)
    track_w = day_w * span
    today_idx = (datetime.date.today() - lo).days
    chart_h = ROW_H * max(len(tasks), 1)

    # 日期刻度 + 竖向网格线（只画一次，铺在每行轨道底层）
    grid = []
    header_cells = []
    for i in range(span):
        x = i * day_w
        grid.append(ft.Container(left=x, top=0, width=1, height=chart_h,
                                 bgcolor=BORDER_SOFT))
        day = lo + datetime.timedelta(days=i)
        header_cells.append(ft.Container(
            width=day_w,
            content=ft.Text(day.strftime('%m-%d'), color=ACCENT if i == today_idx else MUTED,
                            size=FS_SM, text_align=ft.TextAlign.CENTER, no_wrap=True),
        ))
    if 0 <= today_idx < span:  # 今日高亮竖线
        grid.append(ft.Container(left=today_idx * day_w + day_w / 2, top=0, width=2,
                                 height=chart_h, bgcolor=ACCENT, shadow=glow(ACCENT, blur=8)))

    rows = []
    names = []  # 冻结的任务名列，与时间轨道分行平行
    for t in tasks:
        start, end = _as_date(t.start_time), _as_date(t.end_time)
        left = (start - lo).days * day_w + 2
        width = max(((end - start).days + 1) * day_w - 4, 8)
        color = _bar_color(t)
        bar = ft.Container(
            left=left, top=(ROW_H - BAR_H) / 2, width=width, height=BAR_H,
            bgcolor=color, border_radius=RADIUS_MD, shadow=glow(color, blur=10),
            tooltip=f"{t.name} · {start.strftime(DATE_FMT)} ~ {end.strftime(DATE_FMT)} · {t.status}",
            content=ft.Text(t.name, color=WHITE, size=FS_SM, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS),
            alignment=ft.Alignment.CENTER,
        )
        names.append(ft.Container(
            width=NAME_W, height=ROW_H,
            content=ft.Text(t.name, color=TEXT, size=FS_MD, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS, tooltip=t.name),
            alignment=ft.Alignment(-1.0, 0.0),
        ))
        rows.append(ft.Container(width=track_w, height=ROW_H,
                                 content=ft.Stack([*grid, bar])))

    if not rows:
        names.append(ft.Container(width=NAME_W, height=120))
        rows.append(ft.Container(width=track_w, content=ft.Text(
            "暂无任务", color=SLATE, size=FS_MD), alignment=ft.Alignment.CENTER, height=120))

    # 时间轴轨道：横向可滚动；任务名列冻结在左侧，只随纵向滚动
    timeline = ft.Column([
        ft.Row(header_cells, spacing=0),
        ft.Container(height=1, bgcolor=BORDER_SOFT),
        ft.Column(rows, spacing=0),
    ], spacing=0, width=track_w)
    frozen_names = ft.Column([
        ft.Container(width=NAME_W, height=HEADER_H,
                     content=ft.Text("任务", color=TEXT_BRIGHT, size=FS_MD),
                     alignment=ft.Alignment(-1.0, 0.0)),
        ft.Container(height=1, bgcolor=BORDER_SOFT),
        ft.Column(names, spacing=0),
    ], spacing=0)

    return ft.Row([
        frozen_names,
        # Row 的 scroll 为横向：时间轨道可左右滚动，名列保持冻结
        ft.Row([timeline], scroll=ft.ScrollMode.AUTO, expand=True, spacing=0),
    ], spacing=0, expand=True, vertical_alignment=ft.CrossAxisAlignment.START)

