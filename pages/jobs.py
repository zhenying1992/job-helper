from typing import Callable

import flet as ft
from flet import MainAxisAlignment

from common.decorate import catch_error
from common.pagination import Pagination
from common.util import datetime_2_date_str
from constant import Status, Priority, JobType
from data.model import Job
from data.service import JobService, PluginService
from theme import (
    BG_SEARCH, BG_DIALOG, BG_TABLE, BG_TABLE_HEAD, BTN_ADD,
    ACCENT_BRIGHT, TEXT_ON_DARK, TEXT_TITLE, TEXT, BTN_TEXT, MUTED, SLATE,
    RADIUS_LG, TABLE_RADIUS, FS_BASE, FS_MD, FS_XXL,
    # 与任务弹窗共用的暗色科技感表单样式
    form_field, form_option, required_label as _required_label,
    primary_button, FORM_COL_W, FORM_GAP, FORM_FULL_W,
    dark_dropdown, dark_option,
)


def all_job_types() -> list[str]:
    """全部工作类型：内置通用工作 + 插件注入的类型（如稽查案件）。

    筛选栏与新建弹窗共用，避免两处来源不一致导致筛选下拉漏掉插件类型。
    """
    return [JobType.COMMON] + [p.name for p in PluginService.list()]


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

        def on_type(e):
            set_type(e.control.value)
            set_current(1)  # 换筛选条件回到第一页，避免停在新条件下不存在的页码

        def on_status(e):
            set_status(e.control.value)
            set_current(1)

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
                    dark_dropdown(
                        label="工作类型",
                        width=240,
                        options=[dark_option('', '全部')] +
                                [dark_option(i) for i in all_job_types()],
                        value=type,
                        on_select=on_type,
                    ),
                    dark_dropdown(
                        label="工作状态",
                        width=140,
                        options=[dark_option('', '全部')] + [
                            dark_option(i) for i in Status.list()
                        ],
                        value=status,
                        on_select=on_status,
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
        job_types = all_job_types()

        # 与任务弹窗共用同一套暗色科技感表单控件
        job_name = form_field(
            ft.TextField, label=_required_label("工作名"), hint_text="请输入工作名称",
            max_length=20, width=FORM_FULL_W,
        )
        job_desc = form_field(
            ft.TextField, label="描述", hint_text="非必填，填写任务说明",
            multiline=True, min_lines=2, width=FORM_FULL_W,
        )
        job_type = form_field(
            ft.Dropdown, label=_required_label("类型"), value=JobType.COMMON,
            width=FORM_COL_W, options=[form_option(i) for i in job_types],
        )
        job_priority = form_field(
            ft.Dropdown, label=_required_label("优先级"), value=Priority.LOW,
            width=FORM_COL_W, options=[form_option(i) for i in Priority.list()],
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
            # 起止时间由任务自动汇总，新建时无需录入
            JobService.create(
                name=name,
                description=job_desc.value,
                type=job_type.value,
                priority=job_priority.value,
            )
            ft.context.page.pop_dialog()
            set_refresh_flag(lambda v: not v)

        dialog = ft.AlertDialog(
            title=ft.Text("新建工作", size=FS_XXL, color=TEXT_TITLE, weight=ft.FontWeight.BOLD),
            bgcolor=BG_DIALOG,
            # 表单宽度与字段宽度一致（不再固定 520 导致右侧空一片），
            # 按钮经 actions 放在表单下方右侧，与任务编辑弹窗同一紧凑布局。
            content=ft.Container(
                width=FORM_FULL_W,
                content=ft.Column([
                    job_name,
                    job_desc,
                    ft.Row([job_type, job_priority], spacing=FORM_GAP),
                ], tight=True, spacing=16),
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda e: ft.context.page.pop_dialog()),
                primary_button("确认创建", submit_job),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            actions_padding=ft.Padding(0, 0, FORM_GAP, 12),
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
        # 一次批量聚合所有行的时间范围，避免逐行查询
        time_ranges = JobService.time_ranges([j.id for j in pagination.data])

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
                ft.DataCell(ft.Text(
                    datetime_2_date_str(time_ranges[_job.id][0]) if time_ranges[_job.id][0] else "-",
                    color=TEXT, width=110, text_align=ft.TextAlign.CENTER)),
                ft.DataCell(ft.Text(
                    datetime_2_date_str(time_ranges[_job.id][1]) if time_ranges[_job.id][1] else "-",
                    color=TEXT, width=110, text_align=ft.TextAlign.CENTER)),
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
