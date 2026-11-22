"""工作审计台账。

按时间线展示某工作下的审计日志，支持手工新增记录。
工作/任务的创建、更新、删除会在 Service 层自动埋点（见 LogService.record）。
以弹窗形式从工作详情页右上角 ⋮ 菜单打开。
"""

from collections.abc import Callable

import flet as ft
from flet.controls.base_control import skip_field

from common.util import datetime_2_date_str
from constant import (
    BG_PANEL, BORDER_RADIUS, COLOR_PRIMARY, COLOR_TEXT, COLOR_WARN, DATE_TIME_FMT,
)
from data.model import Job, Log
from data.service import LogService
from theme import (
    BORDER as LINE_COLOR, INFO, ACCENT_SOFT, SLATE, TEXT_SUBTLE, BTN_TEXT,
    FS_XL, FS_LG, FS_MD, FS_SM, FS_METRIC,
)


@ft.control("AlertDialog")
class AddLogDialog(ft.AlertDialog):
    """手工补录一条审计记录。"""
    job_id: int = skip_field()
    on_saved: Callable = skip_field()

    name_field: ft.TextField = skip_field()
    content_field: ft.TextField = skip_field()

    def init(self):
        self.name_field = ft.TextField(label="事件", color=COLOR_TEXT,
                                       border_color=COLOR_PRIMARY, max_length=40)
        self.content_field = ft.TextField(label="内容", color=COLOR_TEXT, multiline=True,
                                          min_lines=3, border_color=COLOR_PRIMARY)

        self.title = ft.Text("添加审计记录", color=COLOR_PRIMARY, size=FS_XL,
                             weight=ft.FontWeight.BOLD)
        self.bgcolor = BG_PANEL
        self.content = ft.Column([self.name_field, self.content_field], tight=True, spacing=12)
        self.actions = [
            ft.TextButton("取消", on_click=lambda e: ft.context.page.pop_dialog()),
            ft.Button("保存", bgcolor=COLOR_PRIMARY, color=BTN_TEXT, on_click=self.submit),
        ]

    def submit(self, e):
        name = (self.name_field.value or '').strip()
        if not name:
            ft.context.page.show_dialog(
                ft.SnackBar(ft.Text("事件名不能为空"), bgcolor=COLOR_WARN)
            )
            return
        try:
            LogService.create(self.job_id, name, (self.content_field.value or '').strip())
        except Exception as ex:
            ft.context.page.show_dialog(ft.SnackBar(ft.Text(f"保存失败：{ex}")))
            return
        ft.context.page.pop_dialog()
        if self.on_saved:
            self.on_saved()


# 时间线圆点直径；纵线放在圆点中心（x = 半径 - 线宽/2），由圆点覆盖。
TIMELINE_DOT = 10
TIMELINE_LINE_X = 4


def _log_item(log: Log) -> ft.Control:
    """一条审计记录：左侧圆点 + 右侧时间/动作/内容/附件。

    纵线由弹窗里贯穿整列的 Stack 图层提供，这里只负责圆点本身。
    """
    children = [
        ft.Text(datetime_2_date_str(log.created_time, DATE_TIME_FMT), color=INFO, size=FS_MD),
        ft.Text(f"动作：{log.name}", color=COLOR_TEXT, size=FS_LG, weight=ft.FontWeight.W_500),
    ]
    if log.content:
        children.append(ft.Text(f"内容：{log.content}", color=COLOR_TEXT, size=FS_MD))
    if log.related_files:
        children.append(ft.Text(f"附件：{'、'.join(log.related_files)}", color=ACCENT_SOFT, size=FS_SM))

    return ft.Row(
        controls=[
            ft.Container(width=TIMELINE_DOT, height=TIMELINE_DOT,
                         bgcolor=INFO, border_radius=TIMELINE_DOT / 2),
            ft.Container(width=14),
            ft.Column(children, spacing=2, expand=True),
        ],
        vertical_alignment=ft.CrossAxisAlignment.START,
    )


@ft.control("AlertDialog")
class AuditDialog(ft.AlertDialog):
    """审计台账弹窗：带纵向连线的时间线 + 新增记录。"""

    job: Job = skip_field()
    count_text: ft.Text = skip_field()
    log_column: ft.Column = skip_field()
    timeline_line: ft.Container = skip_field()

    def init(self):
        self.title = ft.Text("审计台账", color=COLOR_PRIMARY, size=FS_XL,
                             weight=ft.FontWeight.BOLD)
        self.bgcolor = BG_PANEL

        self.count_text = ft.Text(color=SLATE, size=FS_MD)
        self.log_column = ft.Column([], spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)
        # 贯穿整条时间线的纵线：top/bottom 定位撑满列高，圆点绘制在其上层覆盖。
        self.timeline_line = ft.Container(
            left=TIMELINE_LINE_X, top=TIMELINE_DOT / 2, bottom=0, width=1,
            bgcolor=LINE_COLOR,
        )

        header = ft.Row([
            ft.Text("操作时间线", color=COLOR_TEXT, size=FS_LG, weight=ft.FontWeight.W_500),
            ft.Container(expand=True),
            self.count_text,
        ])
        # bgcolor/border_radius 由 Container 承载；Column 在 Flet 1.0 无这两个参数
        self.content = ft.Container(
            width=560, height=440, bgcolor=BG_PANEL,
            border_radius=BORDER_RADIUS, padding=16,
            content=ft.Column([
                header,
                ft.Divider(color=LINE_COLOR, height=1),
                ft.Stack(
                    controls=[self.timeline_line, self.log_column],
                    fit=ft.StackFit.EXPAND, expand=True,
                ),
            ], spacing=8),
        )
        self.actions = [
            ft.Button("新增记录", bgcolor=COLOR_PRIMARY, color=BTN_TEXT,
                      on_click=self._add),
            ft.TextButton("关闭", on_click=lambda e: ft.context.page.pop_dialog()),
        ]
        self._load()

    def _load(self):
        """查询并重建时间线（不主动 update，供 init 首次构建）。"""
        logs = LogService.query(self.job.id)
        self.count_text.value = f"{len(logs)} 条记录"
        self.timeline_line.visible = bool(logs)
        if logs:
            self.log_column.controls = [_log_item(log) for log in logs]
        else:
            self.log_column.controls = [
                ft.Column([
                    ft.Icon(ft.Icons.HISTORY, size=FS_METRIC, color=TEXT_SUBTLE),
                    ft.Text("暂无审计记录", color=SLATE, size=FS_LG),
                ], alignment=ft.MainAxisAlignment.CENTER,
                   horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True)
            ]

    def _reload(self):
        """新增记录后的回调：重建并刷新弹窗内容。"""
        self._load()
        self.update()

    def _add(self, _):
        ft.context.page.show_dialog(
            AddLogDialog(job_id=self.job.id, on_saved=self._reload)
        )


def open_audit(job: Job):
    """从工作详情页 ⋮ 菜单打开审计弹窗。"""
    ft.context.page.show_dialog(AuditDialog(job=job))
