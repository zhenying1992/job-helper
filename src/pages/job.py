import datetime
import logging

import flet as ft
from flet_charts import *

from src.common.util import utc_2_naive_datetime, datetime_2_date_str
from src.constant import DATE_FMT
from src.data.model import Job, Task
from src.data.service import JobService, LogService, TaskService

logger = logging.getLogger(__name__)


@ft.component
def job_view():
    return build_work_detail_page()


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


# -------------------------- 左侧：工作详情卡片（普通函数，不是component） --------------------------
def build_left_info_panel(job: Job):
    return ft.Container(
        width=280,
        bgcolor=BG_PANEL,
        border_radius=BORDER_RADIUS,
        padding=20,
        # border=ft.border.all(1, "#254b80"),
        content=ft.Column(
            controls=[
                ft.Text("工作详情介绍", color=COLOR_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                ft.Divider(color="#254b80", height=1),
                ft.Container(height=12),
                ft.Text(f"工作名称: {job.name}", color=COLOR_TEXT, size=13),
                ft.Text(f"描述: {job.description}", color=COLOR_TEXT, size=13),
                ft.Container(height=6),
                ft.Text(f"优先级: {job.priority}", color=COLOR_TEXT, size=13),

                ft.Text(f"开始时间: {datetime_2_date_str(job.start_time)}", color=COLOR_TEXT, size=13),
                ft.Text(f"结束时间: {datetime_2_date_str(job.end_time)}", color=COLOR_TEXT, size=13),
                ft.Container(height=10),
                ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Text("进度: ", color=COLOR_TEXT, size=13),
                        ft.Stack(
                            [
                                ft.ProgressRing(value=job.progress/100, width=60, height=60, stroke_width=8, color=COLOR_PRIMARY,
                                                bgcolor="#1e293b"),
                                ft.Container(
                                    content=ft.Text(f"{job.progress}%", color=COLOR_PRIMARY, size=18),
                                    # alignment=ft.MainAxisAlignment.CENTER,
                                    width=60, height=60
                                )
                            ]
                        )
                    ]
                ),
                ft.Text(f"状态: {job.status}", color=COLOR_SUCCESS, size=14, text_align=ft.TextAlign.CENTER),
                ft.Container(height=8),
                # ft.ProgressBar(value=0.62, color=COLOR_PRIMARY, bgcolor="#1e293b", height=6),
            ],
            spacing=4
        )
    )


# -------------------------- 右侧：审计日志面板（普通函数） --------------------------
BG_PANEL = "#0f172a"
COLOR_PRIMARY = "#60a5fa"
COLOR_TEXT = "#cbd5e1"
BORDER_RADIUS = 10


def build_right_log_panel(job: Job):
    refresh_flag, set_refresh_flag = ft.use_state(True)

    def submit_audit_log():
        LogService.create(
            job_id=job.id,
            name=text_field.value,
            content=content_field.value,
        )
        ft.context.page.pop_dialog()
        set_refresh_flag(not refresh_flag)

    text_field = ft.TextField(label="事件", color=COLOR_TEXT)
    content_field = ft.TextField(label="内容", color=COLOR_TEXT)

    add_audit_log_dialog = ft.AlertDialog(
        title=ft.Text("添加审计", color=COLOR_PRIMARY),
        content=ft.Column([
            text_field ,
            content_field
        ], tight=True),
        actions=[
            ft.TextButton("取消", on_click=lambda e: ft.context.page.pop_dialog()),
            ft.Button("保存", bgcolor=COLOR_PRIMARY, color="white", on_click=submit_audit_log),
        ]
    )

    # 日志数据
    logs = ft.use_memo(lambda: LogService.query(job_id=job.id), [refresh_flag])

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
                            ft.Text(log.created_time, color="#60a5fa", size=13),
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
        width=340,
        bgcolor=BG_PANEL,
        border_radius=BORDER_RADIUS,
        padding=20,
        # border=ft.border.all(1, "#254b80"),
        content=ft.Column(
            controls=[
                ft.Text("审计日志", color=COLOR_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
                ft.Divider(color="#254b80", height=1),
                ft.Container(height=16),
                # Stack：左边竖线 + 日志列表
                ft.Stack(
                    controls=[
                        # 时间线竖线
                        ft.Container(
                            left=4,
                            top=0,
                            width=2,
                            height=320,
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
                ft.Container(height=20),
                ft.Row(
                    controls=[
                        ft.Button(
                            "新增审计日志",
                            bgcolor="#3b82f6",
                            color="white",
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                            on_click=lambda e: ft.context.page.show_dialog(add_audit_log_dialog),
                        )
                    ],
                    spacing=12
                )
            ],
            spacing=0
        )
    )


# -------------------------- 中间：任务表格+甘特图（普通函数） --------------------------


def build_center_task_panel(job: Job):
    # 任务表格数据
    refresh_flag, set_refresh_flag = ft.use_state(True)

    tasks = ft.use_memo(lambda: TaskService.query(), [refresh_flag])
    rows = []
    for task in tasks:
        rows.append(
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(task.id, color=COLOR_TEXT)),
                    ft.DataCell(ft.Text(task.name, color=COLOR_TEXT)),
                    ft.DataCell(ft.Text(task.priority, color=COLOR_TEXT)),
                    ft.DataCell(ft.Text(task.status, color=COLOR_TEXT)),
                    ft.DataCell(ft.Text(datetime_2_date_str(task.start_time), color=COLOR_TEXT)),
                    ft.DataCell(ft.Text(datetime_2_date_str(task.end_time), color=COLOR_TEXT)),
                    ft.DataCell(ft.Row([
                        ft.TextButton("编辑", on_click=lambda e, task=task: ft.context.page.show_dialog(update_task_dialog(task))),
                        ft.TextButton("删除", on_click=lambda e, task=task: ft.context.page.show_dialog(drop_task_dialog(task))),
                    ]))
                ]
            )
        )

    table = ft.DataTable(
        border_radius=BORDER_RADIUS,
        bgcolor="#12182e",
        heading_row_color=BG_HEADER,
        columns=[
            ft.DataColumn(label=ft.Text("ID", color=COLOR_TEXT)),
            ft.DataColumn(label=ft.Text("任务", color=COLOR_TEXT)),
            ft.DataColumn(label=ft.Text("优先级", color=COLOR_TEXT)),
            ft.DataColumn(label=ft.Text("状态", color=COLOR_TEXT)),
            ft.DataColumn(label=ft.Text("开始时间", color=COLOR_TEXT)),
            ft.DataColumn(label=ft.Text("结束时间", color=COLOR_TEXT)),
            ft.DataColumn(label=ft.Text("操作", color="#cbd5e1")),
        ],
        rows=rows
    )

    # 模拟甘特图 LineChart
    def get_labels():
        labels = []
        for i in range(7):
            day = datetime.date.today() + datetime.timedelta(days=i)
            l = ChartAxisLabel(value=i, label=ft.Text(day.strftime(DATE_FMT), color=COLOR_TEXT, size=11))
            labels.append(l)

        return labels

    def get_data():
        data= []

        for idx, task in enumerate(tasks):
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

    gantt_chart = LineChart(
        data_series=get_data(),
        left_axis=ChartAxis(labels=[], show_labels=False),
        bottom_axis=ChartAxis(
            labels=get_labels(),
        ),
        min_x=0,
        max_x=7,
        bgcolor="#0b1224",
        # border=ft.border.all(1, "#254b80"),
        height=220
    )

    # 新建任务弹窗
    today = datetime.date.today()
    today_7 = today + datetime.timedelta(days=7)
    name_field = ft.TextField(label="任务名称", color=COLOR_TEXT)
    desc_field = ft.TextField(label="描述", color=COLOR_TEXT)
    priority_field = ft.Dropdown(label="优先级", color=COLOR_TEXT,
                        options=[ft.dropdown.Option("高"), ft.dropdown.Option("高"),
                                 ft.dropdown.Option("低")])
    status_field = ft.Dropdown(label="状态", color=COLOR_TEXT,
                        options=[ft.dropdown.Option("待开始"), ft.dropdown.Option("进行中"),
                                 ft.dropdown.Option("已完成")])
    picker = ft.DateRangePicker(
        locale=ft.Locale("zh", "Hans"),
        start_value=datetime.datetime(year=today.year, month=today.month, day=today.day),
        end_value=datetime.datetime(year=today_7.year, month=today_7.month, day=today_7.day),
        # first_date=datetime.datetime(year=today.year, month=today.month, day=1),
        # last_date=datetime.datetime(year=2026, month=12, day=31),
        current_date=today,
        # on_change=handle_change,
        # on_dismiss=handle_dismissal,
    )
    picker_button = ft.Button(
        icon=ft.Icons.CALENDAR_MONTH,
        content="选择时间",
        on_click=lambda _: ft.context.page.show_dialog(picker)
    )
    create_task_dialog = ft.AlertDialog(
        title=ft.Text("新建任务", color=COLOR_PRIMARY),
        content=ft.Column([
            name_field,
            desc_field,
            priority_field,
            status_field,
            picker_button
        ], tight=True),
        actions=[
            ft.TextButton("取消", on_click=lambda e: ft.context.page.pop_dialog()),
            ft.Button("确定", bgcolor=COLOR_PRIMARY, color="white", on_click=lambda e:submit_create_task()),
        ],
    )

    def update_task_dialog(task: Task):
        return ft.AlertDialog(
            title=ft.Text("编辑任务", color=COLOR_PRIMARY),
            content=ft.Column([
                name_field,
                desc_field,
                priority_field,
                status_field,
                picker_button
            ], tight=True),
            actions=[
                ft.TextButton("取消", on_click=lambda e: ft.context.page.pop_dialog()),
                ft.Button("确定", bgcolor=COLOR_PRIMARY, color="white", on_click=lambda e:submit_update_task(task)),
            ],
    )

    def drop_task_dialog(task: Task):
        return ft.AlertDialog(
            title=ft.Text("删除任务", color=COLOR_PRIMARY),
            content=ft.Column([
                ft.Text(f"确定要删除任务{task.name}么？", color=COLOR_TEXT, size=11),
            ], tight=True),
            actions=[
                ft.TextButton("取消", on_click=lambda e: ft.context.page.pop_dialog()),
                ft.Button("确定", bgcolor=COLOR_PRIMARY, color="white", on_click=lambda e:submit_drop_task(task)),
            ],
    )

    def submit_create_task():
        TaskService.create(
            job_id=job.id,
            name=name_field.value,
            description=desc_field.value,
            priority=priority_field.value,
            status=status_field.value,
            start_time=utc_2_naive_datetime(picker.start_value),
            end_time=utc_2_naive_datetime(picker.end_value),
        )
        JobService().update(id=job.id, updated_content='新增任务')
        ft.context.page.pop_dialog()
        set_refresh_flag(not refresh_flag)

    def submit_update_task(task: Task):
        TaskService().update(
            id=task.id, name=name_field.value, description=desc_field.value,
            priority=priority_field.value, status=status_field.value,
            start_time=picker.start_value, end_time=picker.end_value,
        )
        JobService().update(id=job.id, updated_content='更新任务')

        ft.context.page.pop_dialog()
        set_refresh_flag(not refresh_flag)

    def submit_drop_task(task: Task):
        TaskService.delete(id=task.id)
        JobService().update(id=job.id, updated_content='删除任务')

        ft.context.page.pop_dialog()
        set_refresh_flag(not refresh_flag)

    header_row = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.Text("任务与计划", color=COLOR_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
            ft.Button("新建任务", bgcolor=COLOR_PRIMARY, color="white", on_click=lambda :ft.context.page.show_dialog(create_task_dialog)),
        ]
    )

    return ft.Container(
        expand=True,
        bgcolor=BG_PANEL,
        border_radius=BORDER_RADIUS,
        padding=20,
        # border=ft.border.all(1, "#254b80"),
        content=ft.Column(
            controls=[
                header_row,
                ft.Divider(color="#254b80", height=1),
                ft.Container(height=12),
                table,
                ft.Container(height=16),
                ft.Text("时间计划", color=COLOR_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                gantt_chart
            ],
            expand=True
        )
    )


# -------------------------- 页面整体组装函数 --------------------------
from src.common.decorate import catch_error


@catch_error
def build_work_detail_page():
    params = ft.use_route_params()
    job = JobService.get(int(params['job_id']))

    main_body = ft.Row(
        controls=[
            build_left_info_panel(job),
            ft.Container(width=16),
            build_center_task_panel(job),
            ft.Container(width=16),
            build_right_log_panel(job),
        ],
        expand=True
    )
    return main_body
