import datetime
from collections.abc import Callable

import flet as ft
from flet.controls.base_control import skip_field

from constant import COLOR_TEXT, Status, COLOR_PRIMARY, COLOR_DANGER
from data.model import Task
from data.service import TaskService
from theme import FS_SM, BTN_TEXT, BG_PANEL, RADIUS_LG, FS_BASE, MUTED

# 弹窗内表单列宽：两列各占一半，避免默认宽度撑破弹窗导致错位/溢出
_FORM_W = 460
_COL_W = 215


def _required_label(text: str) -> ft.Row:
    """必填字段标签：文字 + 红色 *。"""
    return ft.Row([
        ft.Text(text, size=FS_BASE, color=MUTED),
        ft.Text("*", size=FS_BASE, color=COLOR_DANGER, weight=ft.FontWeight.BOLD),
    ], spacing=2)


def _valid_range(start_picker, end_picker) -> bool:
    """校验日期齐全且结束不早于开始；不合法时弹提示返回 False。"""
    s, e = start_picker.value, end_picker.value
    if not s or not e:
        ft.context.page.show_dialog(ft.SnackBar(ft.Text("请选择开始和结束日期")))
        return False
    if e < s:
        ft.context.page.show_dialog(ft.SnackBar(ft.Text("结束日期不能早于开始日期")))
        return False
    return True


def _date_picker(value, label: str) -> ft.DatePicker:
    """带文本框 + 日历图标的日期选择器，比隐藏日期的按钮直观。"""
    return ft.DatePicker(
        value=value,
        entry_mode=ft.DatePickerEntryMode.INPUT,
        field_label_text=label,
        locale=ft.Locale("zh", "Hans"),
        first_date=datetime.datetime(2000, 1, 1),
        last_date=datetime.datetime(2100, 12, 31),
    )


def _build_form(dlg, task=None):
    """为新建/更新弹窗创建表单字段，返回紧凑的两列布局内容。

    两个对话框字段完全相同，仅初始值不同，抽出来避免重复且便于统一样式。
    """
    today = datetime.date.today()
    is_update = task is not None
    start = task.start_time if is_update else datetime.datetime.combine(today, datetime.time())
    end = task.end_time if is_update else datetime.datetime.combine(
        today + datetime.timedelta(days=7), datetime.time())

    dlg.name_field = ft.TextField(
        label=_required_label("任务名称"), color=COLOR_TEXT, width=_COL_W,
        value=task.name if is_update else "",
    )
    dlg.desc_field = ft.TextField(
        label="描述", color=COLOR_TEXT, multiline=True, max_lines=3, width=_FORM_W - 10,
        value=task.description if is_update else "",
    )
    dlg.status_field = ft.Dropdown(
        label=_required_label("状态"), color=COLOR_TEXT, width=_COL_W,
        options=[ft.DropdownOption(key=i, text=i) for i in Status.list()],
        value=Status.normalize(task.status) if is_update else Status.NOT_START,
    )
    dlg.assignee_field = ft.TextField(
        label="负责人", color=COLOR_TEXT, width=_COL_W,
        value=task.assignee if is_update else "",
    )
    dlg.tags_field = ft.TextField(
        label="标签（逗号分隔）", color=COLOR_TEXT, width=_FORM_W - 10,
        value=', '.join(task.tags) if is_update else "",
    )
    dlg.hours_field = ft.TextField(
        label="预估工时（小时）", color=COLOR_TEXT, width=_COL_W,
        keyboard_type=ft.KeyboardType.NUMBER,
        value=str(task.estimate_hours or '') if is_update else '',
    )
    # 两个独立日期选择器：各自显示已选日期，点击弹日历/可直接输入，比单一"选择时间"按钮直观
    dlg.start_picker = _date_picker(start, "开始日期")
    dlg.end_picker = _date_picker(end, "结束日期")

    # 两列紧凑布局：一眼看全，避免底部大片空白；字段定宽避免溢出弹窗
    return ft.Container(
        width=_FORM_W,
        content=ft.Column([
            ft.Row([dlg.name_field, dlg.status_field], spacing=10),
            ft.Row([dlg.assignee_field, dlg.hours_field], spacing=10),
            dlg.tags_field,
            dlg.desc_field,
            ft.Row([dlg.start_picker, dlg.end_picker], spacing=10),
        ], spacing=8, tight=True),
    )


@ft.control("AlertDialog")
class CreateTaskDialog(ft.AlertDialog):
    # 只作 Python 引用，不进控件树
    job_id: int = skip_field()
    on_saved: Callable = skip_field()

    name_field: ft.TextField = skip_field()
    desc_field: ft.TextField = skip_field()
    status_field: ft.Dropdown = skip_field()
    assignee_field: ft.TextField = skip_field()
    tags_field: ft.TextField = skip_field()
    hours_field: ft.TextField = skip_field()
    start_picker: ft.DatePicker = skip_field()
    end_picker: ft.DatePicker = skip_field()

    def init(self):
        self.title = ft.Text("新建任务", color=COLOR_PRIMARY, size=FS_BASE)
        self.bgcolor = BG_PANEL
        self.border_radius = RADIUS_LG
        self.content = _build_form(self)
        self.actions = [
            ft.TextButton("取消", on_click=lambda e: ft.context.page.pop_dialog()),
            ft.Button(
                content="确定",
                bgcolor=COLOR_PRIMARY,
                color=BTN_TEXT,
                on_click=self.submit,
            ),
        ]

    def submit(self, e):
        if not (self.name_field.value or '').strip():
            ft.context.page.show_dialog(ft.SnackBar(ft.Text("任务名称不能为空")))
            return
        if not _valid_range(self.start_picker, self.end_picker):
            return
        try:
            tags = [t.strip() for t in (self.tags_field.value or '').split(',') if t.strip()]
            hours = int(self.hours_field.value or 0)
        except ValueError:
            ft.context.page.show_dialog(ft.SnackBar(ft.Text("预估工时需为整数")))
            return
        try:
            TaskService.create(
                job_id=self.job_id,
                name=(self.name_field.value or "").strip(),
                description=(self.desc_field.value or "").strip(),
                status=self.status_field.value,
                start_time=self.start_picker.value,
                end_time=self.end_picker.value,
                assignee=(self.assignee_field.value or '').strip(),
                estimate_hours=hours,
                tags=tags,
            )
        except Exception as ex:
            ft.context.page.show_dialog(ft.SnackBar(ft.Text(f"创建失败：{ex}")))
            return

        ft.context.page.pop_dialog()
        if self.on_saved:
            self.on_saved()  # noqa


@ft.control("AlertDialog")
class UpdateTaskDialog(ft.AlertDialog):
    task: Task = skip_field()
    on_saved: Callable = skip_field()

    name_field: ft.TextField = skip_field()
    desc_field: ft.TextField = skip_field()
    status_field: ft.Dropdown = skip_field()
    assignee_field: ft.TextField = skip_field()
    tags_field: ft.TextField = skip_field()
    hours_field: ft.TextField = skip_field()
    start_picker: ft.DatePicker = skip_field()
    end_picker: ft.DatePicker = skip_field()

    def init(self):
        self.title = ft.Text("更新任务", color=COLOR_PRIMARY, size=FS_BASE)
        self.bgcolor = BG_PANEL
        self.border_radius = RADIUS_LG
        self.content = _build_form(self, self.task)
        self.actions = [
            ft.TextButton("取消", on_click=lambda e: ft.context.page.pop_dialog()),
            ft.Button(
                content="确定",
                bgcolor=COLOR_PRIMARY,
                color=BTN_TEXT,
                on_click=self.submit,
            ),
        ]

    def submit(self, e):
        if not (self.name_field.value or '').strip():
            ft.context.page.show_dialog(ft.SnackBar(ft.Text("任务名称不能为空")))
            return
        if not _valid_range(self.start_picker, self.end_picker):
            return
        try:
            tags = [t.strip() for t in (self.tags_field.value or '').split(',') if t.strip()]
            hours = int(self.hours_field.value or 0)
        except ValueError:
            ft.context.page.show_dialog(ft.SnackBar(ft.Text("预估工时需为整数")))
            return
        try:
            TaskService.update(
                id=self.task.id,
                name=(self.name_field.value or "").strip(),
                description=(self.desc_field.value or "").strip(),
                status=self.status_field.value,
                start_time=self.start_picker.value,
                end_time=self.end_picker.value,
                assignee=(self.assignee_field.value or '').strip(),
                estimate_hours=hours,
                tags=tags,
            )
        except Exception as ex:
            ft.context.page.show_dialog(ft.SnackBar(ft.Text(f"更新失败：{ex}")))
            return

        ft.context.page.pop_dialog()
        if self.on_saved:
            self.on_saved()  # noqa


@ft.control("AlertDialog")
class DropTaskDialog(ft.AlertDialog):
    task: Task = skip_field()
    on_saved: Callable = skip_field()

    def init(self):
        self.title = ft.Text("删除任务", color=COLOR_PRIMARY, size=FS_BASE)
        self.bgcolor = BG_PANEL
        self.border_radius = RADIUS_LG

        self.content = ft.Column([
            ft.Text(f"确定要删除任务{self.task.name}么？", color=COLOR_TEXT, size=FS_SM),
        ], tight=True)

        self.actions = [
            ft.TextButton("取消", on_click=lambda e: ft.context.page.pop_dialog()),
            ft.Button(
                content="确定",
                bgcolor=COLOR_PRIMARY,
                color=BTN_TEXT,
                on_click=self.submit,
            ),
        ]

    def submit(self, e):
        try:
            TaskService.delete(id=self.task.id)
        except Exception as ex:
            ft.context.page.show_dialog(ft.SnackBar(ft.Text(f"删除失败：{ex}")))
            return

        ft.context.page.pop_dialog()
        if self.on_saved:
            self.on_saved()  # noqa
