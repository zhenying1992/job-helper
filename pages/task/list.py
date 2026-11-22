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

    # 每列定宽，表头与内容用同一宽度并居中，保证逐列对齐
    COLS = [
        ("ID", 45), ("任务", 100), ("状态", 80), ("负责人", 70),
        ("标签", 90), ("工时", 55), ("开始时间", 100), ("结束时间", 100),
        ("操作", 110),
    ]

    def cell(text, width, color=COLOR_TEXT, **kwargs) -> ft.Text:
        return ft.Text(str(text), color=color, width=width,
                       text_align=ft.TextAlign.CENTER, **kwargs)

    def col(label: str, width: int) -> ft.DataColumn:
        return ft.DataColumn(label=cell(label, width, weight=ft.FontWeight.BOLD))

    def table() -> ft.Control:
        widths = [w for _, w in COLS]  # ID/任务/状态/负责人/标签/工时/开始/结束/操作
        rows = []
        for task in tasks:
            w_id, w_name, w_status, w_owner, w_tags, w_hours, w_start, w_end, w_ops = widths
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(cell(task.id, w_id)),
                        ft.DataCell(cell(task.name, w_name)),
                        ft.DataCell(cell(
                            Status.normalize(task.status), w_status,
                            color=Status.color(task.status), size=FS_MD,
                            weight=ft.FontWeight.BOLD,
                        )),
                        ft.DataCell(cell(task.assignee or '-', w_owner)),
                        ft.DataCell(cell(', '.join(task.tags) or '-', w_tags)),
                        ft.DataCell(cell(
                            f'{task.estimate_hours}h' if task.estimate_hours else '-', w_hours)),
                        ft.DataCell(cell(datetime_2_date_str(task.start_time), w_start)),
                        ft.DataCell(cell(datetime_2_date_str(task.end_time), w_end)),
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
                        ], alignment=ft.MainAxisAlignment.CENTER, width=w_ops)),
                    ]
                )
            )

        return ft.Container(
            content=ft.Column(
                [ft.DataTable(
                    border_radius=BORDER_RADIUS,
                    bgcolor=BG_TABLE,
                    heading_row_color=BG_HEADER,
                    # 默认列间距约 32px，9 列累计会超出面板宽度把最后一列（操作）
                    # 挤出可视区，导致编辑/删除按钮看不到。收紧间距与左右边距。
                    column_spacing=10,
                    horizontal_margin=8,
                    columns=[col(label, width) for label, width in COLS],
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
