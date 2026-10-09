import datetime
from typing import Callable

import flet as ft
from flet import MainAxisAlignment

from common.decorate import catch_error
from common.pagination import Pagination
from common.util import utc_2_naive_datetime, datetime_2_date_str
from constant import Status, Priority, JobType
from data.model import Job
from data.service import JobService


@ft.component
@catch_error
def jobs_view():
    current, set_current = ft.use_state(1)
    page_size, set_page_size = ft.use_state(10)
    keyword, set_keyword = ft.use_state("")
    type, set_type = ft.use_state("")
    status, set_status = ft.use_state("")
    refresh_flag, set_refresh_flag = ft.use_state(True)

    pagination = ft.use_memo(
        lambda: JobService.query(Pagination(current, page_size), keyword, type, status),
        [current, page_size, keyword, type, status, refresh_flag]
    )

    return JobsView(
        current=current,
        set_current=set_current,
        page_size=page_size,
        set_page_size=set_page_size,
        keyword=keyword,
        set_keyword=set_keyword,
        type=type,
        set_type=set_type,
        status=status,
        set_status=set_status,
        refresh_flag=refresh_flag,
        set_refresh_flag=set_refresh_flag,
        pagination=pagination,
    ).build()


class JobsView:
    def __init__(
            self,
            current: int,
            set_current: Callable,
            page_size: int,
            set_page_size: Callable,
            keyword: str,
            set_keyword: Callable,
            type: str,
            set_type: Callable,
            status: str,
            set_status: Callable,
            refresh_flag: bool,
            set_refresh_flag: Callable,
            pagination: Pagination,
    ):
        self.current = current
        self.set_current = set_current
        self.page_size = page_size
        self.set_page_size = set_page_size
        self.keyword = keyword
        self.set_keyword = set_keyword
        self.type = type
        self.set_type = set_type
        self.status = status
        self.set_status = set_status
        self.refresh_flag = refresh_flag
        self.set_refresh_flag = set_refresh_flag
        self.pagination = pagination

    def build(self):
        return ft.Container(
            padding=ft.Padding(left=24, right=24),
            content=ft.Column(
                controls=[
                    self.build_action_bar(),
                    self.build_table(),
                    self.build_pagination_bar(),
                ],
                spacing=20
            ),
        )

    # 选择栏
    def build_action_bar(self):
        """顶部筛选栏

        :return:
        """
        return ft.Container(
            padding=ft.Padding(left=24, right=24, top=16, bottom=16),
            content=ft.Row(
                controls=[
                    # ft.Container(width=3),
                    ft.TextField(
                        value=self.keyword,
                        hint_text="输入工作名称搜索",
                        width=320,
                        height=40,
                        border_radius=8,
                        bgcolor="#161d34",
                        text_size=14,
                        on_change=lambda e: self.set_keyword(e.control.value),
                    ),
                    ft.Dropdown(
                        label="工作类型",
                        width=240,
                        options=[ft.DropdownOption(key='', text='全部')] +
                                [ft.DropdownOption(i) for i in JobType.list()],
                        value="全部",
                        on_select=lambda e: self.set_type(e.control.value),
                    ),
                    ft.Dropdown(
                        label="任务状态",
                        width=140,
                        options=[ft.dropdown.Option(key="", text='全部')] + [
                            ft.dropdown.Option(i)
                            for i in Status.list()
                        ],
                        value="全部",
                        on_select=lambda e: self.set_status(e.control.value),
                    ),
                    ft.Container(expand=True),
                    ft.Button(
                        "+ 新增任务",
                        bgcolor="#2563eb",
                        color=ft.Colors.WHITE,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=self.open_new_job_dialog,
                    )
                ],
            )
        )

    # 表格
    def open_new_job_dialog(self, e: ft.Event[ft.Button]):
        # 表单控件
        job_name = ft.TextField(
            label="工作名",
            hint_text="请输入工作名称",
            border_color="#40C9FF",
            focused_border_color="#40C9FF",
            bgcolor="#171e38",
            color="#e2e8f0",
            label_style=ft.TextStyle(color="#94a3b8"),
            max_length=20,
            # on_change=''
        )
        job_desc = ft.TextField(
            label="描述",
            hint_text="非必填，填写任务说明",
            multiline=True,
            min_lines=2,
            border_color="#40C9FF",
            focused_border_color="#40C9FF",
            bgcolor="#171e38",
            color="#e2e8f0",
            label_style=ft.TextStyle(color="#94a3b8"),
        )
        job_type = ft.Dropdown(
            label="类型",
            value=JobType.COMMON,
            options=[ft.DropdownOption(i) for i in JobType.list()],
            border_color="#40C9FF",
            focused_border_color="#40C9FF",
            bgcolor="#f0182b",
            color="#e2e8f0",
            label_style=ft.TextStyle(color="#94a3b8"),
        )
        job_priority = ft.Dropdown(
            label="优先级",
            value=Priority.LOW,
            options=[ft.DropdownOption(i) for i in Priority.list()],
            border_color="#40C9FF",
            focused_border_color="#40C9FF",
            bgcolor="#f0182b",
            color="#e2e8f0",
            label_style=ft.TextStyle(color="#94a3b8"),
        )
        today = datetime.date.today()
        today_7 = datetime.date.today() + datetime.timedelta(days=7)
        picker = ft.DateRangePicker(
            locale=ft.Locale("zh", "Hans"),
            start_value=datetime.datetime(year=today.year, month=today.month, day=today.day),
            end_value=datetime.datetime(year=today_7.year, month=today_7.month, day=today_7.day),
            # first_date=datetime.datetime(year=2024, month=1, day=1),
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

        def submit_job(e):
            JobService.create(
                name=job_name.value,
                description=job_desc.value,
                type=job_type.value,
                priority=job_priority.value,
                start_time=utc_2_naive_datetime(picker.start_value),
                end_time=utc_2_naive_datetime(picker.end_value),
            )
            ft.context.page.pop_dialog()
            self.set_refresh_flag(not self.refresh_flag)

        dialog = ft.AlertDialog(
            title=ft.Text("新建工作", size=20, color="#CFD8FF", weight=ft.FontWeight.BOLD),
            bgcolor="#111834",
            content=ft.Container(
                width=520,
                content=ft.Column(
                    [
                        job_name,
                        job_desc,
                        job_type,
                        job_priority,
                        picker_button,
                    ],
                    tight=True,
                    spacing=16
                ),
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda e: setattr(dialog, "open", False) or ft.context.page.update()),
                ft.Button("确认创建", on_click=submit_job, bgcolor="#40C9FF", color="#0f1529"),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        ft.context.page.show_dialog(dialog=dialog)

    def open_drop_job_dialog(self, e, job: Job):
        def drop_job(_):
            JobService.delete(id=job.id)
            ft.context.page.pop_dialog()
            self.set_refresh_flag(not self.refresh_flag)

        dialog = ft.AlertDialog(
            title=ft.Text("删除工作", size=20, color="#CFD8FF", weight=ft.FontWeight.BOLD),
            bgcolor="#111834",
            content=ft.Container(
                content=ft.Text(f"确定要删除{job.name}？", color="#cbd5e1")
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda e: setattr(dialog, "open", False) or ft.context.page.update()),
                ft.Button("确认", on_click=drop_job, bgcolor="#40C9FF", color="#0f1529"),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        ft.context.page.show_dialog(dialog=dialog)

    def build_table(self):
        # 表格定义
        return ft.Container(
            ft.Row(
                controls=[ft.DataTable(
                    border_radius=10,
                    bgcolor="#12182e",
                    heading_row_color="#1b2442",
                    columns=[
                        ft.DataColumn(label=ft.Text("ID", color="#cbd5e1"),
                                      heading_row_alignment=MainAxisAlignment.CENTER),
                        ft.DataColumn(label=ft.Text("名称", color="#cbd5e1"),
                                      heading_row_alignment=MainAxisAlignment.CENTER),

                        ft.DataColumn(label=ft.Text("类型", color="#cbd5e1"),
                                      heading_row_alignment=MainAxisAlignment.CENTER),
                        ft.DataColumn(label=ft.Text("优先级", color="#cbd5e1"),
                                      heading_row_alignment=MainAxisAlignment.CENTER),
                        ft.DataColumn(label=ft.Text("状态", color="#cbd5e1"),
                                      heading_row_alignment=MainAxisAlignment.CENTER),
                        ft.DataColumn(label=ft.Text("进度", color="#cbd5e1"),
                                      heading_row_alignment=MainAxisAlignment.CENTER),
                        ft.DataColumn(label=ft.Text("开始时间", color="#cbd5e1"),
                                      heading_row_alignment=MainAxisAlignment.CENTER),
                        ft.DataColumn(label=ft.Text("结束时间", color="#cbd5e1"),
                                      heading_row_alignment=MainAxisAlignment.CENTER),
                        ft.DataColumn(label=ft.Text("操作", color="#cbd5e1"),
                                      heading_row_alignment=MainAxisAlignment.CENTER),
                    ],
                    rows=self.list_row(),
                    expand=True
                )]
            )
        )

    def list_row(self):
        _rows = []
        for _job in self.pagination.data:
            _row = ft.DataRow(cells=[
                ft.DataCell(ft.Text(_job.id, color="#cbd5e1", text_align=ft.TextAlign.CENTER)),
                ft.DataCell(
                    ft.Text(
                        _job.name, color="#cbd5e1", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, width=300,
                        tooltip=_job.description, text_align=ft.TextAlign.CENTER,
                    ),
                ),
                ft.DataCell(ft.Text(_job.type, color="#cbd5e1", text_align=ft.TextAlign.CENTER)),
                ft.DataCell(ft.Text(_job.priority, color="#cbd5e1", text_align=ft.TextAlign.CENTER)),
                ft.DataCell(
                    ft.Container(
                        ft.Text(_job.status, size=12, text_align=ft.TextAlign.CENTER),
                        bgcolor="#f97316",
                        padding=3, border_radius=4
                    )
                ),
                ft.DataCell(ft.Text(f'{_job.progress}%', color="#cbd5e1", text_align=ft.TextAlign.CENTER)),
                ft.DataCell(
                    ft.Text(datetime_2_date_str(_job.start_time), color="#cbd5e1", text_align=ft.TextAlign.CENTER)
                ),
                ft.DataCell(
                    ft.Text(datetime_2_date_str(_job.end_time), text_align=ft.TextAlign.CENTER, color="#cbd5e1")
                ),
                ft.DataCell(ft.Row([
                    ft.TextButton("查看", on_click=lambda e, _job=_job: ft.context.page.navigate(f"/job/{_job.id}")),
                    ft.TextButton("删除", on_click=lambda e, _job=_job: self.open_drop_job_dialog(e, _job)),
                ]))
            ])
            _rows.append(_row)

        return _rows

    # 分页
    def build_pagination_bar(self):
        # 分页控件
        return ft.Container(
            padding=ft.Padding(left=24, right=24, top=16, bottom=16),
            content=ft.Row([
                ft.Text(f"共 {self.pagination.total} 条记录", color="#94a3b8"),
                ft.Container(expand=True),

                # ft.Dropdown(
                #     label="每页条数",
                #     width=100,
                #     options=[ft.dropdown.Option("10"), ft.dropdown.Option("20"), ft.dropdown.Option("50")],
                #     value="10",
                #     on_select=lambda e: self.set_page_size(int(e.control.value)),
                #     color='#999999'
                # ),
                ft.Container(width=10),
                ft.Button(
                    "上一页",
                    disabled=self.current <= 1,
                    on_click=lambda e: self.set_current(self.current - 1), color='#999999'
                ),
                ft.Text(f"第 {self.pagination.current} / {self.pagination.total_page} 页", color='#999999'),
                ft.Button(
                    "下一页",
                    disabled=self.current >= self.pagination.total_page,
                    on_click=lambda e: self.set_current(self.current + 1), color='#999999'
                ),
            ])
        )
