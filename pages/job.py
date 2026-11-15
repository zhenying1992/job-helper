import logging
from typing import Callable

import flet as ft
import flet_dropzone as ftd

from common.decorate import catch_error
from common.util import datetime_2_date_str
from constant import COLOR_WARN, BG_PANEL, BORDER_RADIUS, COLOR_PRIMARY, COLOR_TEXT, COLOR_SUCCESS
from data.model import Job
from data.service import JobService
from pages.task.gantt import TaskGantt
from pages.task.list import TaskList, task_list_view
from pages.task.topo import TaskTopo

logger = logging.getLogger(__name__)


@ft.component
@catch_error
def job_view():
    params = ft.use_route_params()
    job_id = int(params['job_id'])
    logger.info(f"查看工作: {job_id}")
    if not job_id:
        return ft.Text("请在工作列表中选择", color=COLOR_WARN)

    job = JobService.get(job_id)
    refresh_flag, set_refresh_flag = ft.use_state(True)
    # current_view, set_current_view = ft.use_state("list")  # list / gantt / topology

    return ft.Column([
        HeaderBar(job).build(),
        ft.Row([
            Left(job).build(),
            ft.Container(width=1),
            Right(job=job, refresh_flag=refresh_flag, set_refresh_flag=set_refresh_flag).build(),
        ], expand=True)
    ], expand=True)


class HeaderBar:
    def __init__(self, job: Job):
        self.job = job

    def build(self):
        return ft.Container(
            bgcolor="#0f172a",
            # padding=ft.padding.symmetric(horizontal=16, vertical=10),
            content=ft.Row([
                ft.TextButton("← 返回", on_click=lambda e: print("返回工作列表"),
                              style=ft.ButtonStyle(color="#94a3b8")),
                ft.Text(self.job.name, color="#22d3ee", weight=ft.FontWeight.W_600),
                ft.Container(width=12),
                ft.Container(
                    ft.Text(self.job.status, color="#0f172a"),
                    bgcolor="#22d3ee",
                    # padding=ft.padding.symmetric(horizontal=8, vertical=3),
                    border_radius=4
                ),
                ft.Container(width=12),
                ft.Text(f"进度：{self.job.progress / 100}%", color="#cbd5e1"),
                ft.Container(expand=True),
                ft.PopupMenuButton(
                    icon=ft.Icons.MORE_VERT,
                    items=[
                        ft.PopupMenuItem("归档工作"),
                        ft.PopupMenuItem("复制链接"),
                        ft.PopupMenuItem("导出审计台账"),
                    ]
                )
            ])
        )


class Left:
    def __init__(self, job: Job):
        self.job = job

    def build(self):
        return ft.Column(
            controls=[
                self.build_top(),
                ft.Container(height=10),
                self.build_bottom(),
            ],
        )

    def build_top(self):
        return ft.Container(
            width=300,
            height=300,
            bgcolor=BG_PANEL,
            border_radius=BORDER_RADIUS,
            padding=20,
            # border=ft.border.all(1, "#254b80"),
            content=ft.Column(
                controls=[
                    ft.Text("工作详情", color=COLOR_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                    ft.Divider(color="#254b80", height=1),
                    ft.Container(height=12),
                    ft.Text(f"名称: {self.job.name}", color=COLOR_TEXT, size=13),
                    ft.Text(f"描述: {self.job.description}", color=COLOR_TEXT, size=13),
                    ft.Container(height=6),
                    ft.Text(f"优先级: {self.job.priority}", color=COLOR_TEXT, size=13),

                    ft.Text(f"开始时间: {datetime_2_date_str(self.job.start_time)}", color=COLOR_TEXT, size=13),
                    ft.Text(f"结束时间: {datetime_2_date_str(self.job.end_time)}", color=COLOR_TEXT, size=13),
                    ft.Container(height=10),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.START,
                        controls=[
                            ft.Text("进度: ", color=COLOR_TEXT, size=13),
                            ft.Stack([
                                ft.ProgressBar(
                                    bar_height=12, width=180,
                                    value=self.job.progress / 100,
                                    bgcolor=COLOR_TEXT,
                                    color=COLOR_SUCCESS if self.job.progress == 100 else COLOR_PRIMARY,
                                ),
                                ft.Text(f"{self.job.progress}%")
                            ],
                                width=180,
                                alignment=ft.Alignment.CENTER
                            ),
                        ]
                    ),
                    ft.Text(f"状态: {self.job.status}", color=COLOR_SUCCESS, size=14, text_align=ft.TextAlign.CENTER),
                    ft.Container(height=8),
                ],
                spacing=4
            )
        )

    def build_bottom(self):
        return ft.Container(
            ftd.Dropzone(
                content=ft.Container(
                    ft.Text("Drop here!"),
                    height=300,
                    alignment=ft.Alignment.CENTER,
                    bgcolor="red",
                    # expand=True,
                ),
                on_dropped=lambda e: print(f"Dropped: {e.files}"),
                on_entered=lambda e: print("Entered"),
                on_exited=lambda e: print("Exited"),
            )
        )


class Right:
    def __init__(self, job: Job, refresh_flag: bool, set_refresh_flag: Callable):
        self.job = job
        self.refresh_flag = refresh_flag
        self.set_refresh_flag = set_refresh_flag

        self.current_view, self.set_current_view = ft.use_state("list")  # list / gantt / topology

    def build(self):
        return ft.Container(
            # width=280,
            height=610,
            bgcolor=BG_PANEL,
            border_radius=BORDER_RADIUS,
            padding=20,
            # border=ft.border.all(1, "#254b80"),
            content=ft.Column(
                controls=[
                    self.switch_bar(),
                    ft.Container(
                        self.build_main_view(),
                        expand=True,
                        alignment=ft.Alignment(-1.0, -1.0)
                    )
                ],
                spacing=4,
                # cross_axis_alignment=ft.CrossAxisAlignment.START,
                horizontal_alignment=ft.CrossAxisAlignment.START,
                alignment=ft.MainAxisAlignment.START,
            ),
            expand=True,
        )

    def switch_bar(self):
        return ft.Column([
            ft.Row([
                ft.Container(
                    ft.TextButton("任务列表", on_click=lambda e: (self.set_current_view("list")),
                                  style=ft.ButtonStyle(
                                      color="#22d3ee" if self.current_view == "list" else "#94a3b8")),
                    # padding=ft.padding.symmetric(horizontal=6)
                ),
                ft.Container(
                    ft.TextButton("甘特图", on_click=lambda e: (self.set_current_view("gantt")),
                                  style=ft.ButtonStyle(
                                      color="#22d3ee" if self.current_view == "gantt" else "#94a3b8")),
                    # padding=ft.padding.symmetric(horizontal=6)
                ),
                ft.Container(
                    ft.TextButton("依赖拓扑图", on_click=lambda e: (self.set_current_view("topology")),
                                  style=ft.ButtonStyle(
                                      color="#22d3ee" if self.current_view == "topology" else "#94a3b8")),
                    # padding=ft.padding.symmetric(horizontal=6)
                ),
                ft.Container(expand=True),
            ]),
            ft.Divider(color="#254b80", height=1),
        ])

    def build_main_view(self):
        if self.current_view == "list":
            return task_list_view(job=self.job)
        elif self.current_view == "gantt":
            return TaskGantt(job=self.job, refresh_flag=self.refresh_flag,
                            set_refresh_flag=self.set_refresh_flag).build()
        else:
            return TaskTopo(job=self.job).build()


# class Right:
#     def __init__(self, job):
#         self.job = job
#         self.refresh_flag, self.set_refresh_flag = ft.use_state(True)
#
#     def build_add_audit_log_dialog(self):
#         text_field = ft.TextField(label="事件", color=COLOR_TEXT)
#         content_field = ft.TextField(label="内容", color=COLOR_TEXT)
#
#         def submit_audit_log():
#             LogService.create(
#                 job_id=self.job.id,
#                 name=text_field.value,
#                 content=content_field.value,
#             )
#             ft.context.page.pop_dialog()
#             self.set_refresh_flag(not self.refresh_flag)
#
#         return ft.AlertDialog(
#             title=ft.Text("添加记录", color=COLOR_PRIMARY),
#             content=ft.Column(
#                 [
#                     text_field,
#                     content_field
#                 ],
#                 tight=True
#             ),
#             actions=[
#                 ft.TextButton("取消", on_click=lambda e: ft.context.page.pop_dialog()),
#                 ft.Button("保存", bgcolor=COLOR_PRIMARY, color="white", on_click=submit_audit_log),
#             ]
#         )
#
#     def build(self):
#         logs = ft.use_memo(lambda: LogService.query(job_id=self.job.id), [self.refresh_flag])
#
#         log_items = []
#         for log in logs:
#             log_items.append(
#                 ft.Row(
#                     controls=[
#                         ft.Container(
#                             width=10,
#                             height=10,
#                             bgcolor="#60a5fa",
#                             border_radius=5,
#                         ),
#                         ft.Container(width=16),
#                         ft.Column(
#                             controls=[
#                                 ft.Text(datetime_2_date_str(log.created_time, fmt=DATE_TIME_FMT), color="#60a5fa",
#                                         size=13),
#                                 ft.Text(f"动作：{log.name}", color=COLOR_TEXT, size=13),
#                                 ft.Text(f"内容：{log.content}", color=COLOR_TEXT, size=13),
#                                 ft.Container(height=12),
#                             ],
#                             spacing=4
#                         )
#                     ],
#                     vertical_alignment=ft.CrossAxisAlignment.START
#                 )
#             )
#
#         return ft.Container(
#             width=250,
#             height=800,
#             bgcolor=BG_PANEL,
#             border_radius=BORDER_RADIUS,
#             padding=20,
#             # border=ft.border.all(1, "#254b80"),
#             content=ft.Column(
#                 controls=[
#                     ft.Row(
#                         controls=[
#                             ft.Text("操作日志", color=COLOR_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
#                             ft.Button(
#                                 "新增",
#                                 bgcolor="#3b82f6",
#                                 color="white",
#                                 style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
#                                 on_click=lambda e: ft.context.page.show_dialog(self.build_add_audit_log_dialog()),
#                             ),
#                         ],
#                         alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
#                     ),
#                     ft.Divider(color="#254b80", height=1),
#                     ft.Container(height=16),
#
#                     ft.Container(
#                         expand=True,
#                         content=ft.Column(
#                             controls=[
#                                 # Stack：左边竖线 + 日志列表
#                                 ft.Stack(
#                                     controls=[
#                                         # 时间线竖线
#                                         ft.Container(
#                                             left=4,
#                                             top=0,
#                                             width=2,
#                                             height=1320,
#                                             bgcolor="#254b80",
#                                         ),
#                                         ft.Container(
#                                             # padding=ft.padding.only(left=8),
#                                             content=ft.Column(
#                                                 controls=log_items,
#                                                 spacing=0
#                                             )
#                                         )
#                                     ]
#                                 ),
#                             ],
#                             scroll=ft.ScrollMode.AUTO,  # 超出高度自动出现滚动条
#                         )
#                     ),
#                 ],
#                 spacing=0,
#                 horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
#             )
#         )
