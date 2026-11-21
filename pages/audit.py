"""工作审计台账。

按时间线展示某工作下的审计日志，支持新增、删除与导出。
工作/任务的创建、更新、删除会在 Service 层自动埋点（见 LogService.record）。
以弹窗形式从工作详情页右上角 ⋮ 菜单打开。
"""

from collections.abc import Callable
from datetime import datetime

import flet as ft
from flet.controls.base_control import skip_field

from common.decorate import catch_error
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


def _confirm_delete(log: Log, on_saved: Callable):
    def confirm(_):
        LogService.delete(log.id)
        ft.context.page.pop_dialog()
        if on_saved:
            on_saved()

    ft.context.page.show_dialog(ft.AlertDialog(
        title=ft.Text("删除记录", color=COLOR_PRIMARY),
        content=ft.Text(f"确定删除「{log.name}」这条记录？", color=COLOR_TEXT),
        bgcolor=BG_PANEL,
        actions=[
            ft.TextButton("取消", on_click=lambda e: ft.context.page.pop_dialog()),
            ft.Button("删除", bgcolor=COLOR_WARN, color=BTN_TEXT, on_click=confirm),
        ],
    ))


def _log_item(log: Log, on_changed: Callable) -> ft.Control:
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
            ft.Container(width=10, height=10, bgcolor=INFO, border_radius=5),
            ft.Container(width=14),
            ft.Column(children, spacing=2, expand=True),
            ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=SLATE, icon_size=16,
                          tooltip="删除记录", on_click=lambda e: _confirm_delete(log, on_changed)),
        ],
        vertical_alignment=ft.CrossAxisAlignment.START,
    )


def export_text(job: Job, logs: list[Log]) -> str:
    """导出为纯文本台账。"""
    lines = [
        f"审计台账 - {job.name}",
        f"导出时间：{datetime_2_date_str(datetime.now(), DATE_TIME_FMT)}",
        "=" * 40,
    ]
    if not logs:
        lines.append("（暂无记录）")
    for log in logs:
        lines.append(f"[{datetime_2_date_str(log.created_time, DATE_TIME_FMT)}] {log.name}")
        if log.content:
            lines.append(f"    内容：{log.content}")
        if log.related_files:
            lines.append(f"    附件：{'、'.join(log.related_files)}")
    return '\n'.join(lines)


@ft.control("AlertDialog")
class AuditDialog(ft.AlertDialog):
    """审计台账弹窗：时间线 + 新增/删除/导出。"""

    job: Job = skip_field()
    count_text: ft.Text = skip_field()
    log_column: ft.Column = skip_field()

    def init(self):
        self.title = ft.Text("审计台账", color=COLOR_PRIMARY, size=FS_XL,
                             weight=ft.FontWeight.BOLD)
        self.bgcolor = BG_PANEL

        self.count_text = ft.Text(color=SLATE, size=FS_MD)
        self.log_column = ft.Column([], spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)

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
                ft.Container(self.log_column, expand=True),
            ], spacing=8),
        )
        self.actions = [
            ft.Button("新增记录", bgcolor=COLOR_PRIMARY, color=BTN_TEXT,
                      on_click=self._add),
            ft.TextButton("导出", on_click=self._export),
            ft.TextButton("关闭", on_click=lambda e: ft.context.page.pop_dialog()),
        ]
        self._load()

    def _load(self):
        """查询并重建时间线（不主动 update，供 init 首次构建）。"""
        logs = LogService.query(self.job.id)
        self.count_text.value = f"{len(logs)} 条记录"
        if logs:
            self.log_column.controls = [_log_item(log, self._reload) for log in logs]
        else:
            self.log_column.controls = [
                ft.Column([
                    ft.Icon(ft.Icons.HISTORY, size=FS_METRIC, color=TEXT_SUBTLE),
                    ft.Text("暂无审计记录", color=SLATE, size=FS_LG),
                ], alignment=ft.MainAxisAlignment.CENTER,
                   horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True)
            ]

    def _reload(self):
        """新增/删除后的回调：重建并刷新弹窗内容。"""
        self._load()
        self.update()

    def _add(self, _):
        ft.context.page.show_dialog(
            AddLogDialog(job_id=self.job.id, on_saved=self._reload)
        )

    def _export(self, _):
        logs = LogService.query(self.job.id)
        ft.context.page.show_dialog(ft.AlertDialog(
            title=ft.Text("审计台账导出", color=COLOR_PRIMARY),
            content=ft.Text(export_text(self.job, logs), size=FS_SM),
            bgcolor=BG_PANEL,
            actions=[ft.TextButton("关闭", on_click=lambda e: ft.context.page.pop_dialog())],
        ))


def open_audit(job: Job):
    """从工作详情页 ⋮ 菜单打开审计弹窗。"""
    ft.context.page.show_dialog(AuditDialog(job=job))


def open_export(job: Job):
    """从 ⋮ 菜单直接导出纯文本审计台账。"""
    logs = LogService.query(job.id)
    ft.context.page.show_dialog(ft.AlertDialog(
        title=ft.Text("审计台账", color=COLOR_PRIMARY),
        content=ft.Text(export_text(job, logs), size=FS_SM),
        bgcolor=BG_PANEL,
        actions=[ft.TextButton("关闭", on_click=lambda e: ft.context.page.pop_dialog())],
    ))
