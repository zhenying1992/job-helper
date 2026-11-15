from dataclasses import dataclass

import flet as ft

from common.decorate import catch_error
from common.util import datetime_2_date_str
from constant import COLOR_TEXT, BG_PANEL, BORDER_RADIUS, COLOR_PRIMARY, BG_HEADER
from data.model import Job, Task
from data.service import TaskService
from pages.task import CreateTaskDialog, DropTaskDialog, UpdateTaskDialog


@ft.component
@catch_error
def task_list_view(job: Job):
    refresh, set_refresh = ft.use_state(False)

    def bump():
        # 函数式更新：永远基于 hook 里的最新值，不受闭包快照影响
        set_refresh(lambda v: v + 1)

    return TaskList(job=job, bump=bump).build()

class TaskList:
    def __init__(self, job: Job, bump):
        self.job = job
        self.tasks = TaskService.query(job.id)
        self.bump = bump

    def build(self):
        return ft.Container(
            expand=True,
            bgcolor=BG_PANEL,
            border_radius=BORDER_RADIUS,
            padding=20,
            # border=ft.border.all(1, "#254b80"),
            content=ft.Column(
                controls=[
                    self.build_header(),
                    ft.Divider(color="#254b80", height=1),

                    self.build_table(),

                ],
                expand=True
            )
        )

    def build_header(self):
        return ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                # ft.Text("任务信息", color=COLOR_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                ft.Button(
                    "新建任务",
                    bgcolor=COLOR_PRIMARY,
                    color="white",
                    on_click=lambda: ft.context.page.show_dialog(
                        CreateTaskDialog(
                            job_id=self.job.id,
                            on_saved=self.bump,
                        )
                    )
                ),
            ]
        )

    def build_table(self):
        rows = []
        for task in self.tasks:
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(task.id, color=COLOR_TEXT)),
                        ft.DataCell(ft.Text(task.name, color=COLOR_TEXT)),
                        ft.DataCell(ft.Text(task.status, color=COLOR_TEXT)),
                        ft.DataCell(ft.Text(datetime_2_date_str(task.start_time), color=COLOR_TEXT)),
                        ft.DataCell(ft.Text(datetime_2_date_str(task.end_time), color=COLOR_TEXT)),
                        ft.DataCell(ft.Row([
                            ft.TextButton(
                                "编辑",
                                on_click=lambda e, task=task: ft.context.page.show_dialog(
                                    UpdateTaskDialog(task=task, on_saved=self.bump)
                                )
                            ),
                            ft.TextButton(
                                "删除",
                                on_click=lambda e, task=task: ft.context.page.show_dialog(
                                    DropTaskDialog(task=task, on_saved=self.bump)
                                )
                            ),
                        ]))
                    ]
                )
            )

        return ft.Container(
            height=350,
            expand=True,
            content=ft.Column(
                [ft.DataTable(
                    border_radius=BORDER_RADIUS,
                    bgcolor="#12182e",
                    heading_row_color=BG_HEADER,
                    columns=[
                        ft.DataColumn(label=ft.Text("ID", color=COLOR_TEXT)),
                        ft.DataColumn(label=ft.Text("任务", color=COLOR_TEXT)),
                        ft.DataColumn(label=ft.Text("状态", color=COLOR_TEXT)),
                        ft.DataColumn(label=ft.Text("开始时间", color=COLOR_TEXT)),
                        ft.DataColumn(label=ft.Text("结束时间", color=COLOR_TEXT)),
                        ft.DataColumn(label=ft.Text("操作", color="#cbd5e1")),
                    ],
                    rows=rows,
                    # expand=True,
                )],
                scroll=ft.ScrollMode.AUTO,  # 超出高度自动出现滚动条
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,  # ✅关键！子控件横向拉伸填满Column宽度
            )
        )
