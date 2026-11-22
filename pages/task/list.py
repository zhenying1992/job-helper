import flet as ft

from common.decorate import catch_error
from common.util import datetime_2_date_str
from constant import (
    COLOR_TEXT, BG_PANEL, BORDER_RADIUS, COLOR_PRIMARY, BG_HEADER, Status,
)
from data.model import Job
from data.service import TaskService
from pages.task import CreateTaskDialog, DropTaskDialog, UpdateTaskDialog
from theme import BORDER, BG_TABLE, BTN_TEXT, FS_MD


@ft.component
@catch_error
def task_list_view(job: Job, on_changed=None):
    """任务列表容器：自增计数触发重渲染，on_changed 冒泡到工作详情页。"""
    _, set_refresh = ft.use_state(0)

    def bump():
        set_refresh(lambda v: v + 1)
        if on_changed:
            on_changed()

    return TaskList(job=job, bump=bump)


@ft.component
def TaskList(job: Job, bump):
    """任务列表主体：每次渲染实时查库，保证与看板/甘特同步。"""
    tasks = TaskService.query(job.id)

    def header() -> ft.Control:
        return ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Button(
                    "新建任务",
                    bgcolor=COLOR_PRIMARY,
                    color=BTN_TEXT,
                    on_click=lambda: ft.context.page.show_dialog(
                        CreateTaskDialog(
                            job_id=job.id,
                            on_saved=bump,
                        )
                    )
                ),
            ]
        )

    def table() -> ft.Control:
        rows = []
        for task in tasks:
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(str(task.id), color=COLOR_TEXT)),
                        ft.DataCell(ft.Text(task.name, color=COLOR_TEXT)),
                        ft.DataCell(
                            ft.Text(
                                Status.normalize(task.status), color=Status.color(task.status),
                                size=FS_MD, weight=ft.FontWeight.BOLD, width=80,
                                text_align=ft.TextAlign.CENTER,
                            )
                        ),
                        ft.DataCell(ft.Text(task.assignee or '-', color=COLOR_TEXT)),
                        ft.DataCell(ft.Text(', '.join(task.tags) or '-', color=COLOR_TEXT)),
                        ft.DataCell(ft.Text(f'{task.estimate_hours}h' if task.estimate_hours else '-', color=COLOR_TEXT)),
                        ft.DataCell(ft.Text(datetime_2_date_str(task.start_time), color=COLOR_TEXT)),
                        ft.DataCell(ft.Text(datetime_2_date_str(task.end_time), color=COLOR_TEXT)),
                        ft.DataCell(ft.Row([
                            ft.TextButton(
                                "编辑",
                                on_click=lambda e, task=task: ft.context.page.show_dialog(
                                    UpdateTaskDialog(task=task, on_saved=bump)
                                )
                            ),
                            ft.TextButton(
                                "删除",
                                on_click=lambda e, task=task: ft.context.page.show_dialog(
                                    DropTaskDialog(task=task, on_saved=bump)
                                )
                            ),
                        ]))
                    ]
                )
            )

        return ft.Container(
            content=ft.Column(
                [ft.DataTable(
                    border_radius=BORDER_RADIUS,
                    bgcolor=BG_TABLE,
                    heading_row_color=BG_HEADER,
                    columns=[
                        ft.DataColumn(label=ft.Text("ID", color=COLOR_TEXT)),
                        ft.DataColumn(label=ft.Text("任务", color=COLOR_TEXT)),
                        ft.DataColumn(label=ft.Text("状态", color=COLOR_TEXT)),
                        ft.DataColumn(label=ft.Text("负责人", color=COLOR_TEXT)),
                        ft.DataColumn(label=ft.Text("标签", color=COLOR_TEXT)),
                        ft.DataColumn(label=ft.Text("工时", color=COLOR_TEXT)),
                        ft.DataColumn(label=ft.Text("开始时间", color=COLOR_TEXT)),
                        ft.DataColumn(label=ft.Text("结束时间", color=COLOR_TEXT)),
                        ft.DataColumn(label=ft.Text("操作", color=COLOR_TEXT)),
                    ],
                    rows=rows,
                )],
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,  # 子控件横向拉伸填满Column宽度
            )
        )

    return ft.Container(
        expand=True,
        bgcolor=BG_PANEL,
        border_radius=BORDER_RADIUS,
        padding=20,
        content=ft.Column(
            controls=[
                header(),
                ft.Divider(color=BORDER, height=1),
                table(),
            ],
            expand=True
        )
    )
