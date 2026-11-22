import datetime
from typing import Callable

import flet as ft
from flet import MainAxisAlignment

from common.decorate import catch_error
from common.pagination import Pagination
from common.util import utc_2_naive_datetime, datetime_2_date_str
from constant import Status, Priority, JobType
from data.model import Job
from data.service import JobService, PluginService
from theme import (
    BG_SEARCH, BG_INPUT, BG_DIALOG, BG_TABLE, BG_TABLE_HEAD, BTN_ADD,
    ACCENT_BRIGHT, TEXT_BRIGHT, TEXT_TITLE, TEXT, MUTED, TEXT_ON_DARK, BTN_TEXT, SLATE,
    RADIUS_LG, TABLE_RADIUS,
    FS_BASE, FS_MD, FS_XXL,
)


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
    )


@ft.component
def JobsView(current: int, set_current: Callable, page_size: int,
             set_page_size: Callable, keyword: str, set_keyword: Callable,
             type: str, set_type: Callable, status: str, set_status: Callable,
             refresh_flag: bool, set_refresh_flag: Callable,
             pagination: Pagination):
    """工作列表主体。所有状态由 jobs_view 持有并通过参数传入，本组件只负责呈现。"""
    def _body():
        return ft.Container(
            padding=ft.Padding(left=24, right=24),
            content=ft.Column(
                controls=[
                    build_action_bar(),
                    build_table(),
                    build_pagination_bar(),
                ],
                spacing=20
            ),
        )

    # 选择栏
    def build_action_bar():
        """顶部筛选栏：搜索、类型/状态下拉与新增入口。"""
        return ft.Container(
            padding=ft.Padding(left=24, right=24, top=16, bottom=16),
            content=ft.Row(
                controls=[
                    ft.TextField(
                        value=keyword,
                        hint_text="输入工作名称搜索",
                        width=320,
                        height=40,
                        border=ft.OutlineInputBorder(border_radius=RADIUS_LG),
                        bgcolor=BG_SEARCH,
                        text_size=FS_BASE,
                        on_change=lambda e: set_keyword(e.control.value),
                    ),
                    ft.Dropdown(
                        label="工作类型",
                        width=240,
                        options=[ft.DropdownOption(key='', text='全部')] +
                                [ft.DropdownOption(key=i, text=i) for i in JobType.list()],
                        value="",
                        on_select=lambda e: set_type(e.control.value),
                    ),
                    ft.Dropdown(
                        label="工作状态",
                        width=140,
                        options=[ft.DropdownOption(key="", text="全部")] + [
                            ft.DropdownOption(key=i, text=i) for i in Status.list()
                        ],
                        value="",
                        on_select=lambda e: set_status(e.control.value),
                    ),
                    ft.Container(expand=True),
                    ft.Button(
                        "+ 新增工作",
                        bgcolor=BTN_ADD,
                        color=BTN_TEXT,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=RADIUS_LG)),
                        on_click=open_new_job_dialog,
                    )
                ],
            )
        )

    # 表格
    def open_new_job_dialog(e: ft.Event[ft.Button]):
        plugins = PluginService.list()
        job_types = [JobType.COMMON] + [plugin.name for plugin in plugins]

        # 表单控件共享同一套暗色输入框样式
        def field(kind, **kwargs):
            common = dict(
                border_color=ACCENT_BRIGHT,
                focused_border_color=ACCENT_BRIGHT,
                bgcolor=BG_INPUT,
                color=TEXT_BRIGHT,
                label_style=ft.TextStyle(color=MUTED),
            )
            common.update(kwargs)
            return kind(**common)

        job_name = field(
            ft.TextField, label="工作名", hint_text="请输入工作名称",
            max_length=20,
        )
        job_desc = field(
            ft.TextField, label="描述", hint_text="非必填，填写任务说明",
            multiline=True, min_lines=2,
        )
        job_type = field(
            ft.Dropdown, label="类型", value=JobType.COMMON,
            options=[ft.DropdownOption(key=i, text=i) for i in job_types],
        )
        job_priority = field(
            ft.Dropdown, label="优先级", value=Priority.LOW,
            options=[ft.DropdownOption(key=i, text=i) for i in Priority.list()],
        )
        today = datetime.date.today()
        today_7 = datetime.date.today() + datetime.timedelta(days=7)
        picker = ft.DateRangePicker(
            locale=ft.Locale("zh", "Hans"),
            start_value=datetime.datetime(year=today.year, month=today.month, day=today.day),
            end_value=datetime.datetime(year=today_7.year, month=today_7.month, day=today_7.day),
            current_date=today,
        )

        picker_button = ft.Button(
            icon=ft.Icons.CALENDAR_MONTH,
            content="选择时间",
            on_click=lambda _: ft.context.page.show_dialog(picker)
        )

        def submit_job(e):
            name = (job_name.value or '').strip()
            if not name:
                ft.context.page.show_dialog(ft.SnackBar(ft.Text("工作名称不能为空")))
                return
            if JobService.exists_name(name):
                ft.context.page.show_dialog(
                    ft.SnackBar(ft.Text("名称已存在；若已删除，请先到回收站彻底删除"))
                )
                return
            JobService.create(
                name=name,
                description=job_desc.value,
                type=job_type.value,
                priority=job_priority.value,
                start_time=utc_2_naive_datetime(picker.start_value),
                end_time=utc_2_naive_datetime(picker.end_value),
            )
            ft.context.page.pop_dialog()
            set_refresh_flag(lambda v: not v)

        dialog = ft.AlertDialog(
            title=ft.Text("新建工作", size=FS_XXL, color=TEXT_TITLE, weight=ft.FontWeight.BOLD),
            bgcolor=BG_DIALOG,
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
                ft.Button("确认创建", on_click=submit_job, bgcolor=ACCENT_BRIGHT, color=TEXT_ON_DARK),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        ft.context.page.show_dialog(dialog=dialog)

    def open_drop_job_dialog(e, job: Job):
        def drop_job(_):
            JobService.delete(id=job.id)
            ft.context.page.pop_dialog()
            set_refresh_flag(lambda v: not v)

        dialog = ft.AlertDialog(
            title=ft.Text("删除工作", size=FS_XXL, color=TEXT_TITLE, weight=ft.FontWeight.BOLD),
            bgcolor=BG_DIALOG,
            content=ft.Container(
                content=ft.Text(f"确定要删除{job.name}？", color=TEXT)
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda e: setattr(dialog, "open", False) or ft.context.page.update()),
                ft.Button("确认", on_click=drop_job, bgcolor=ACCENT_BRIGHT, color=TEXT_ON_DARK),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        ft.context.page.show_dialog(dialog=dialog)

    def build_table():
        # 表格定义
        return ft.Container(
            ft.Row(
                controls=[ft.DataTable(
                    border_radius=TABLE_RADIUS,
                    bgcolor=BG_TABLE,
                    heading_row_color=BG_TABLE_HEAD,
                    columns=[
                        ft.DataColumn(label=ft.Text("ID", color=TEXT),
                                      heading_row_alignment=MainAxisAlignment.CENTER),
                        ft.DataColumn(label=ft.Text("名称", color=TEXT),
                                      heading_row_alignment=MainAxisAlignment.CENTER),

                        ft.DataColumn(label=ft.Text("类型", color=TEXT),
                                      heading_row_alignment=MainAxisAlignment.CENTER),
                        ft.DataColumn(label=ft.Text("优先级", color=TEXT),
                                      heading_row_alignment=MainAxisAlignment.CENTER),
                        ft.DataColumn(label=ft.Text("状态", color=TEXT),
                                      heading_row_alignment=MainAxisAlignment.CENTER),
                        ft.DataColumn(label=ft.Text("进度", color=TEXT),
                                      heading_row_alignment=MainAxisAlignment.CENTER),
                        ft.DataColumn(label=ft.Text("开始时间", color=TEXT),
                                      heading_row_alignment=MainAxisAlignment.CENTER),
                        ft.DataColumn(label=ft.Text("结束时间", color=TEXT),
                                      heading_row_alignment=MainAxisAlignment.CENTER),
                        ft.DataColumn(label=ft.Text("操作", color=TEXT),
                                      heading_row_alignment=MainAxisAlignment.CENTER),
                    ],
                    rows=list_row(),
                    expand=True
                )]
            )
        )

    def list_row():
        def view_handler(job_id):
            """单参数闭包：Flet 事件只回传一个事件对象，job_id 由闭包捕获。"""
            def _go(_e):
                ft.context.page.navigate(f"/job/{job_id}")
            return _go

        def drop_handler(job):
            def _drop(_e):
                open_drop_job_dialog(_e, job)
            return _drop

        _rows = []
        for _job in pagination.data:
            _row = ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(_job.id), color=TEXT, width=55, text_align=ft.TextAlign.CENTER)),
                ft.DataCell(
                    ft.Text(
                        _job.name, color=TEXT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, width=220,
                        tooltip=_job.description, text_align=ft.TextAlign.CENTER,
                    ),
                ),
                ft.DataCell(ft.Text(_job.type, color=TEXT, width=105, text_align=ft.TextAlign.CENTER)),
                ft.DataCell(ft.Text(_job.priority, color=TEXT, width=65, text_align=ft.TextAlign.CENTER)),
                ft.DataCell(
                    ft.Text(
                        Status.normalize(_job.status), color=Status.color(_job.status),
                        size=FS_MD, weight=ft.FontWeight.BOLD, width=80,
                        text_align=ft.TextAlign.CENTER,
                    )
                ),
                ft.DataCell(ft.Text(f'{_job.progress}%', color=TEXT, width=65, text_align=ft.TextAlign.CENTER)),
                ft.DataCell(
                    ft.Text(datetime_2_date_str(_job.start_time), color=TEXT, width=110, text_align=ft.TextAlign.CENTER)
                ),
                ft.DataCell(
                    ft.Text(datetime_2_date_str(_job.end_time), text_align=ft.TextAlign.CENTER, color=TEXT, width=110)
                ),
                ft.DataCell(ft.Row([
                    ft.TextButton("查看", on_click=view_handler(_job.id)),
                    ft.TextButton("删除", on_click=drop_handler(_job)),
                ], width=120, alignment=ft.MainAxisAlignment.CENTER))
            ])
            _rows.append(_row)

        return _rows

    # 分页
    def build_pagination_bar():
        # 分页控件
        return ft.Container(
            padding=ft.Padding(left=24, right=24, top=16, bottom=16),
            content=ft.Row([
                ft.Text(f"共 {pagination.total} 条记录", color=MUTED),
                ft.Container(expand=True),
                ft.Container(width=10),
                ft.Button(
                    "上一页",
                    disabled=current <= 1,
                    on_click=lambda e: set_current(current - 1), color=SLATE
                ),
                ft.Text(f"第 {pagination.current} / {pagination.total_page} 页", color=SLATE),
                ft.Button(
                    "下一页",
                    disabled=current >= pagination.total_page,
                    on_click=lambda e: set_current(current + 1), color=SLATE
                ),
            ])
        )

    return _body()
