import datetime
import logging
from typing import Callable

import flet as ft
from flet_charts import *
import flet_dropzone as ftd

from common.decorate import catch_error
from common.util import utc_2_naive_datetime, datetime_2_date_str
from constant import DATE_FMT, Status, DATE_TIME_FMT
from data.model import Task, Job
from data.service import JobService, LogService, TaskService

logger = logging.getLogger(__name__)

# -------------------------- 通用样式常量（抽出来，方便全局复用） --------------------------
BG_MAIN = "#081022"
BG_PANEL = "#101a33"
BG_HEADER = "#182848"
COLOR_TEXT = "#cbd5e1"
COLOR_PRIMARY = "#38bdf8"
COLOR_SUCCESS = "#22c55e"
COLOR_WARN = "#f59e0b"
COLOR_DANGER = "#ef4444"
BORDER_RADIUS = 10


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

    return ft.Row(
        controls=[
            Left(job).build(),
            ft.Container(width=5),

            Center(job=job, refresh_flag=refresh_flag, set_refresh_flag=set_refresh_flag).build(),
            ft.Container(width=5),

            Right(job).build(),
        ],
        vertical_alignment=ft.CrossAxisAlignment.START
    )


class Left:
    def __init__(self, job: Job):
        self.job = job

    def build(self):
        return ft.Column(
            controls=[
                self.build_top(),
                self.build_bottom(),
            ]
        )

    def build_top(self):
        return ft.Container(
            width=280,
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
                    height=500,
                    alignment=ft.Alignment.CENTER,
                    bgcolor="red",
                ),
                on_dropped=lambda e: print(f"Dropped: {e.files}"),
                on_entered=lambda e: print("Entered"),
                on_exited=lambda e: print("Exited"),
            )
        )


class Center:
    def __init__(self, job: Job, refresh_flag: bool, set_refresh_flag: Callable):
        self.job = job
        self.refresh_flag = refresh_flag
        self.set_refresh_flag = set_refresh_flag

        self.job = job
        self.tasks = TaskService.query(job.id)

        today = datetime.date.today()
        today_7 = today + datetime.timedelta(days=7)

        self.name_field = ft.TextField(label="任务名称", color=COLOR_TEXT)
        self.desc_field = ft.TextField(label="描述", color=COLOR_TEXT)
        self.status_field = ft.Dropdown(
            label="状态",
            color=COLOR_TEXT,
            options=[ft.DropdownOption(i) for i in Status.list()],
            value=Status.NOT_START,
        )
        self.picker = ft.DateRangePicker(
            locale=ft.Locale("zh", "Hans"),
            start_value=datetime.datetime(year=today.year, month=today.month, day=today.day),
            end_value=datetime.datetime(year=today_7.year, month=today_7.month, day=today_7.day),
            # first_date=datetime.datetime(year=today.year, month=today.month, day=1),
            # last_date=datetime.datetime(year=2026, month=12, day=31),
            current_date=today,
            # on_change=handle_change,
            # on_dismiss=handle_dismissal,
        )
        self.picker_button = ft.Button(
            icon=ft.Icons.CALENDAR_MONTH,
            content="选择时间",
            on_click=lambda _: ft.context.page.show_dialog(self.picker)
        )

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

                    ft.Container(height=16),
                    ft.Text("时间计划", color=COLOR_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                    ft.Divider(color="#254b80", height=1),
                    self.build_gantt(),
                ],
                expand=True
            )
        )

    def build_header(self):
        def submit_create_task():
            TaskService.create(
                job_id=self.job.id,
                name=self.name_field.value,
                description=self.desc_field.value,
                status=self.status_field.value,
                start_time=utc_2_naive_datetime(self.picker.start_value),
                end_time=utc_2_naive_datetime(self.picker.end_value),
            )
            JobService().update(id=self.job.id, updated_content='新增任务')
            ft.context.page.pop_dialog()
            self.set_refresh_flag(not self.refresh_flag)

        create_task_dialog = ft.AlertDialog(
            title=ft.Text("新建任务", color=COLOR_PRIMARY),
            content=ft.Column([
                self.name_field,
                self.desc_field,
                self.status_field,
                self.picker_button
            ], tight=True),
            actions=[
                ft.TextButton("取消", on_click=lambda e: ft.context.page.pop_dialog()),
                ft.Button("确定", bgcolor=COLOR_PRIMARY, color="white", on_click=lambda e: submit_create_task()),
            ],
        )
        return ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Text("任务信息", color=COLOR_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                ft.Button(
                    "新建任务",
                    bgcolor=COLOR_PRIMARY,
                    color="white",
                    on_click=lambda: ft.context.page.show_dialog(create_task_dialog)
                ),
            ]
        )

    # 表格
    def submit_update_task(self, task: Task):
        TaskService().update(
            id=task.id, name=self.name_field.value, description=self.desc_field.value,
            status=self.status_field.value,
            start_time=self.picker.start_value, end_time=self.picker.end_value,
        )
        JobService().update(id=self.job.id, updated_content='更新任务')

        ft.context.page.pop_dialog()
        self.set_refresh_flag(not self.refresh_flag)

    def update_task_dialog(self, task: Task):
        return ft.AlertDialog(
            title=ft.Text("编辑任务", color=COLOR_PRIMARY),
            content=ft.Column([
                self.name_field,
                self.desc_field,
                self.status_field,
                self.picker_button
            ], tight=True),
            actions=[
                ft.TextButton("取消", on_click=lambda e: ft.context.page.pop_dialog()),
                ft.Button("确定", bgcolor=COLOR_PRIMARY, color="white",
                          on_click=lambda e: self.submit_update_task(task)),
            ],
        )

    def submit_drop_task(self, task: Task):
        TaskService.delete(id=task.id)
        JobService().update(id=self.job.id, updated_content='删除任务')

        ft.context.page.pop_dialog()
        self.set_refresh_flag(not self.refresh_flag)

    def drop_task_dialog(self, task: Task):
        return ft.AlertDialog(
            title=ft.Text("删除任务", color=COLOR_PRIMARY),
            content=ft.Column([
                ft.Text(f"确定要删除任务{task.name}么？", color=COLOR_TEXT, size=11),
            ], tight=True),
            actions=[
                ft.TextButton("取消", on_click=lambda e: ft.context.page.pop_dialog()),
                ft.Button("确定", bgcolor=COLOR_PRIMARY, color="white", on_click=lambda e: self.submit_drop_task(task)),
            ],
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
                                    self.update_task_dialog(task)
                                )
                            ),
                            ft.TextButton(
                                "删除",
                                on_click=lambda e, task=task: ft.context.page.show_dialog(
                                    self.drop_task_dialog(task)
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

    # 甘特图
    def get_labels(self):
        labels = []
        for i in range(7):
            day = datetime.date.today() + datetime.timedelta(days=i)
            l = ChartAxisLabel(value=i, label=ft.Text(day.strftime(DATE_FMT), color=COLOR_TEXT, size=11))
            labels.append(l)

        return labels

    def get_data(self):
        data = []

        for idx, task in enumerate(self.tasks):
            s = (task.start_time.date() - datetime.datetime.today().date()).days
            e = (task.end_time.date() - datetime.datetime.today().date()).days
            data.append(
                LineChartData(
                    points=[
                        LineChartDataPoint(s, idx, tooltip=task.name),
                        LineChartDataPoint(e, idx, tooltip=task.name),
                    ],
                    color="#22c55e",
                    stroke_width=3,
                    point=True,
                )
            )
        return data

    def build_gantt(self):
        return LineChart(
            data_series=self.get_data(),
            left_axis=ChartAxis(labels=[], show_labels=False),
            bottom_axis=ChartAxis(
                labels=self.get_labels(),
            ),
            min_x=0,
            max_x=7,
            bgcolor="#0b1224",
            # border=ft.border.all(1, "#254b80"),
            height=300
        )


class Right:
    def __init__(self, job):
        self.job = job
        self.refresh_flag, self.set_refresh_flag = ft.use_state(True)

    def build_add_audit_log_dialog(self):
        text_field = ft.TextField(label="事件", color=COLOR_TEXT)
        content_field = ft.TextField(label="内容", color=COLOR_TEXT)

        def submit_audit_log():
            LogService.create(
                job_id=self.job.id,
                name=text_field.value,
                content=content_field.value,
            )
            ft.context.page.pop_dialog()
            self.set_refresh_flag(not self.refresh_flag)

        return ft.AlertDialog(
            title=ft.Text("添加记录", color=COLOR_PRIMARY),
            content=ft.Column(
                [
                    text_field,
                    content_field
                ],
                tight=True
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda e: ft.context.page.pop_dialog()),
                ft.Button("保存", bgcolor=COLOR_PRIMARY, color="white", on_click=submit_audit_log),
            ]
        )

    def build(self):
        logs = ft.use_memo(lambda: LogService.query(job_id=self.job.id), [self.refresh_flag])

        log_items = []
        for log in logs:
            log_items.append(
                ft.Row(
                    controls=[
                        ft.Container(
                            width=10,
                            height=10,
                            bgcolor="#60a5fa",
                            border_radius=5,
                        ),
                        ft.Container(width=16),
                        ft.Column(
                            controls=[
                                ft.Text(datetime_2_date_str(log.created_time, fmt=DATE_TIME_FMT), color="#60a5fa", size=13),
                                ft.Text(f"动作：{log.name}", color=COLOR_TEXT, size=13),
                                ft.Text(f"内容：{log.content}", color=COLOR_TEXT, size=13),
                                ft.Container(height=12),
                            ],
                            spacing=4
                        )
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.START
                )
            )

        return ft.Container(
            width=250,
            height=800,
            bgcolor=BG_PANEL,
            border_radius=BORDER_RADIUS,
            padding=20,
            # border=ft.border.all(1, "#254b80"),
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("操作日志", color=COLOR_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
                            ft.Button(
                                "新增",
                                bgcolor="#3b82f6",
                                color="white",
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                                on_click=lambda e: ft.context.page.show_dialog(self.build_add_audit_log_dialog()),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(color="#254b80", height=1),
                    ft.Container(height=16),

                    ft.Container(
                        expand=True,
                        content=ft.Column(
                            controls=[
                                # Stack：左边竖线 + 日志列表
                                ft.Stack(
                                    controls=[
                                        # 时间线竖线
                                        ft.Container(
                                            left=4,
                                            top=0,
                                            width=2,
                                            height=1320,
                                            bgcolor="#254b80",
                                        ),
                                        ft.Container(
                                            # padding=ft.padding.only(left=8),
                                            content=ft.Column(
                                                controls=log_items,
                                                spacing=0
                                            )
                                        )
                                    ]
                                ),
                            ],
                            scroll=ft.ScrollMode.AUTO,  # 超出高度自动出现滚动条
                        )
                    ),
                ],
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            )
        )
