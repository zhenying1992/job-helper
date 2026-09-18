import datetime

import flet as ft

from src.common.pagination import Pagination
from src.data.model import Job
from src.data.service import JobService


@ft.component
def jobs_view():
    current, set_current = ft.use_state(1)
    page_size, set_page_size = ft.use_state(1)
    keyword, set_keyword = ft.use_state("")

    pagination = ft.use_memo(lambda: JobService.query(Pagination(current, page_size), keyword), [current, page_size, keyword])

    def get_pagination_bar():
        # 分页控件
        return ft.Container(
            padding=ft.Padding(left=24, right=24, top=16, bottom=16),
            content=ft.Row([
                ft.Text(f"共 {pagination.total} 条记录", color="#94a3b8"),
                ft.Container(expand=True),
                ft.Dropdown(
                    label="每页条数",
                    width=100,
                    options=[ft.dropdown.Option("10"), ft.dropdown.Option("20"), ft.dropdown.Option("50")],
                    value="10"
                ),
                ft.Container(width=10),
                ft.Button("上一页", disabled=current <= 1, on_click=lambda e: set_current(current-1)),
                ft.Text(f"第 {pagination.current} / {pagination.total_page} 页"),
                ft.Button("下一页", disabled=current >= pagination.total_page, on_click=lambda e: set_current(current+1)),
            ])
        )

    def get_action_bar():
        # 顶部筛选操作栏
        return ft.Container(
            padding=ft.Padding(left=24, right=24, top=16, bottom=16),
            content=ft.Row(
                controls=[
                    # ft.Container(width=3),
                    ft.TextField(
                        value=keyword,
                        hint_text="输入工作名称搜索",
                        width=320,
                        height=40,
                        border_radius=8,
                        bgcolor="#161d34",
                        text_size=14,
                        on_change=lambda e: set_keyword(e.control.value),
                    ),
                    ft.Dropdown(
                        label="工作类型",
                        width=240,
                        options=[
                            ft.dropdown.Option("全部"),
                            ft.dropdown.Option("稽查"),
                            ft.dropdown.Option("纳税评估"),
                            ft.dropdown.Option("风险核查")
                        ],
                        value="全部"
                    ),
                    ft.Dropdown(
                        label="任务状态",
                        width=140,
                        options=[
                            ft.dropdown.Option("全部"),
                            ft.dropdown.Option("待处理"),
                            ft.dropdown.Option("进行中"),
                            ft.dropdown.Option("已办结"),
                            ft.dropdown.Option("暂停")
                        ],
                        value="全部"
                    ),
                    ft.Container(expand=True),
                    ft.Button(
                        "+ 新增任务",
                        bgcolor="#2563eb",
                        color=ft.Colors.WHITE,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=open_new_job_dialog,
                    )
                ],
            )
        )

    return ft.Container(
        padding=ft.Padding(left=24, right=24),
        content=ft.Column(
            controls=[
                get_action_bar(),
                get_table(pagination),
                get_pagination_bar(),
            ],
            spacing=20
        )
    )




def list_row(pagination):
    _rows = []
    for _job in pagination.data:
        _row = ft.DataRow(cells=[
            ft.DataCell(ft.Text(_job.id, color="#cbd5e1")),
            ft.DataCell(ft.Text(_job.name, color="#cbd5e1")),
            ft.DataCell(ft.Text(_job.type, color="#cbd5e1")),
            ft.DataCell(ft.Text(_job.progress, color="#cbd5e1")),
            ft.DataCell(ft.Container(ft.Text("待处理", size=12), bgcolor="#f97316", padding=3, border_radius=4)),
            ft.DataCell(ft.Text(_job.progress, color="#cbd5e1")),
            ft.DataCell(ft.Text(_job.start_time, color="#cbd5e1")),
            ft.DataCell(ft.Text(_job.end_time, color="#cbd5e1")),
            ft.DataCell(ft.Row([
                ft.TextButton("查看"),
                ft.TextButton("编辑"),
            ]))
        ])
        _rows.append(_row)

    return _rows

def open_new_job_dialog(e: ft.Event[ft.Button]):
    ft.context.page.show_dialog(dialog=dialog)


def get_table(pagination):
    # 表格定义
    return ft.DataTable(
        border_radius=10,
        bgcolor="#12182e",
        heading_row_color="#1b2442",
        columns=[
            ft.DataColumn(label=ft.Text("ID", color="#cbd5e1")),
            ft.DataColumn(label=ft.Text("名称", color="#cbd5e1")),
            ft.DataColumn(label=ft.Text("类型", color="#cbd5e1")),
            ft.DataColumn(label=ft.Text("优先级", color="#cbd5e1")),
            ft.DataColumn(label=ft.Text("状态", color="#cbd5e1")),
            ft.DataColumn(label=ft.Text("进度", color="#cbd5e1")),
            ft.DataColumn(label=ft.Text("开始时间", color="#cbd5e1")),
            ft.DataColumn(label=ft.Text("结束时间", color="#cbd5e1")),
            ft.DataColumn(label=ft.Text("操作", color="#cbd5e1")),
        ],
        rows=list_row(pagination),
    )


# 表单控件
job_name = ft.TextField(
        label="工作名",
        hint_text="请输入工作名称",
        border_color="#40C9FF",
        focused_border_color="#40C9FF",
        bgcolor="#171e38",
        color="#e2e8f0",
        label_style=ft.TextStyle(color="#94a3b8"),
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
        options=[
            ft.DropdownOption(key="风险核查", content=ft.Text("风险核查", color="#94a3b8")),
            ft.DropdownOption("资料整理"),
            ft.DropdownOption("案件复核"),
            ft.DropdownOption("其他"),
        ],
        border_color="#40C9FF",
        focused_border_color="#40C9FF",
        bgcolor="#171e38",
        color="#e2e8f0",
        label_style=ft.TextStyle(color="#94a3b8"),
    )
job_priority = ft.Dropdown(
        label="优先级",
        value="中",
        options=[
            ft.dropdown.Option("高"),
            ft.dropdown.Option("中"),
            ft.dropdown.Option("低"),
        ],
        border_color="#40C9FF",
        focused_border_color="#40C9FF",
        bgcolor="#171e38",
        color="#e2e8f0",
        label_style=ft.TextStyle(color="#94a3b8"),
    )
today = datetime.datetime(year=2025, month=4, day=15)

picker = ft.DateRangePicker(
    start_value=datetime.datetime(year=today.year, month=today.month, day=1),
    end_value=datetime.datetime(year=today.year, month=today.month, day=15),
    first_date=datetime.datetime(year=2024, month=1, day=1),
    last_date=datetime.datetime(year=2026, month=12, day=31),
    current_date=today,
    # on_change=handle_change,
    # on_dismiss=handle_dismissal,
)

def submit_job():
    JobService.create(
        name=job_name.value,
        description=job_desc.value,
        type=job_type.value,
        priority=job_priority.value,
        start_time=picker.start_value,
        end_time=picker.end_value,
    )
    set
    ft.context.page.pop_dialog()

    ft.context.page.show_dialog(ft.SnackBar(ft.Text("Opened snack bar")))



picker_button =ft.Button(
                icon=ft.Icons.CALENDAR_MONTH,
    content="选择时间",

    on_click=lambda _: ft.context.page.show_dialog(picker)
)

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
            ft.ElevatedButton("确认创建", on_click=submit_job, bgcolor="#40C9FF", color="#0f1529"),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

