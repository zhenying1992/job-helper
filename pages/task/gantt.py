"""任务甘特图：左侧任务名 + 右侧按天定位的时间条，逾期/完成按状态着色。

用纯 Flet 控件自绘，避免 LineChart 画甘特时刻度与任务名缺失、观感空旷的问题。
"""

import datetime
from typing import Callable

import flet as ft

from constant import DATE_FMT, OVERDUE, Status
from data.model import Job
from data.service import TaskService
from theme import (
    ACCENT, BORDER_SOFT, MUTED, SLATE, TEXT, TEXT_BRIGHT, WHITE,
    RADIUS_MD, FS_SM, FS_MD, glow,
)

NAME_W = 130       # 左侧任务名列宽
TRACK_W = 900      # 时间条轨道总宽（横向可滚动）
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


class TaskGantt:
    def __init__(self, job: Job, refresh_flag: bool, set_refresh_flag: Callable):
        self.job = job
        self.refresh_flag = refresh_flag
        self.set_refresh_flag = set_refresh_flag

    def build(self) -> ft.Control:
        tasks = TaskService.query(self.job.id)
        lo, span = _range(tasks)
        day_w = TRACK_W / span
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
                                size=FS_SM, text_align=ft.TextAlign.CENTER),
            ))
        if 0 <= today_idx < span:  # 今日高亮竖线
            grid.append(ft.Container(left=today_idx * day_w + day_w / 2, top=0, width=2,
                                     height=chart_h, bgcolor=ACCENT, shadow=glow(ACCENT, blur=8)))

        rows = []
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
            rows.append(ft.Row([
                ft.Container(width=NAME_W, content=ft.Text(
                    t.name, color=TEXT, size=FS_MD, max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS, tooltip=t.name)),
                ft.Container(width=TRACK_W, height=ROW_H, content=ft.Stack([*grid, bar])),
            ], spacing=0))

        if not rows:
            rows = [ft.Container(content=ft.Text("暂无任务", color=SLATE, size=FS_MD),
                                 alignment=ft.Alignment.CENTER, height=120)]

        return ft.Column([
            ft.Row([
                ft.Container(width=NAME_W, content=ft.Text("任务", color=TEXT_BRIGHT, size=FS_MD)),
                ft.Row(header_cells, spacing=0),
            ], spacing=0),
            ft.Container(height=1, bgcolor=BORDER_SOFT),
            ft.Column(rows, spacing=0, scroll=ft.ScrollMode.AUTO, expand=True),
        ], expand=True, scroll=ft.ScrollMode.AUTO)
