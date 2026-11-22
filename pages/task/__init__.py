import datetime
from collections.abc import Callable

import flet as ft
from flet.controls.base_control import skip_field

from common.util import as_naive
from constant import COLOR_TEXT, Status, COLOR_PRIMARY
from data.model import Task
from data.service import TaskService
from theme import (
    ACCENT, ACCENT_SOFT, BG_INPUT, BORDER_STRONG, BG_PANEL, FS_BASE, FS_SM, RADIUS_LG,
    # 与新建工作弹窗共用的暗色科技感表单样式
    form_field, form_option, required_label as _required_label,
    primary_button, FORM_COL_W as _COL_W, FORM_FULL_W as _FORM_W,
    FORM_GAP,
)


def _valid_range(start_picker, end_picker) -> bool:
    """校验日期齐全且结束不早于开始；不合法时弹提示返回 False。

    DatePicker 选出的值是带 UTC tzinfo 的 aware datetime，而表单初始值是 naive。
    只改了其中一个日期时 e < s 会抛 "can't compare offset-naive and offset-aware
    datetimes"，表现为点击确定后"偶尔闪退"。比较前统一归一到东八区 naive。
    """
    s, e = as_naive(start_picker.value), as_naive(end_picker.value)
    if not s or not e:
        ft.context.page.show_dialog(ft.SnackBar(ft.Text("请选择开始和结束日期")))
        return False
    if e < s:
        ft.context.page.show_dialog(ft.SnackBar(ft.Text("结束日期不能早于开始日期")))
        return False
    return True


def _date_picker(value, label: str) -> tuple[ft.Button, ft.DatePicker]:
    """日期选择按钮 + 日历弹窗（暗色科技感 / 默认日历模式）。

    DatePicker 是对话框控件，只能由 page.show_dialog() 打开，直接放进布局
    不会显示——这正是任务弹窗看不到时间选项的原因。这里用按钮承载当前日期，
    点击弹日历，选中后回填按钮文本；返回 (按钮, 日历) 供表单提交时读值。
    """
    def fmt(dt):
        return dt.strftime('%Y-%m-%d') if dt else '选择日期'

    picker = ft.DatePicker(
        value=as_naive(value),
        entry_mode=ft.DatePickerEntryMode.CALENDAR,  # 默认日历模式，不进输入框
        field_label_text=label,
        locale=ft.Locale("zh", "Hans"),
        first_date=datetime.datetime(2000, 1, 1),
        last_date=datetime.datetime(2100, 12, 31),
    )
    caption = ft.Text(fmt(picker.value), color=ACCENT_SOFT, size=FS_BASE)
    button = ft.Button(
        content=ft.Row([
            ft.Icon(ft.Icons.CALENDAR_MONTH, size=16, color=ACCENT), caption,
        ], spacing=6),
        width=_COL_W,
        bgcolor=BG_INPUT,
        color=ACCENT_SOFT,
        style=ft.ButtonStyle(side=ft.BorderSide(1, BORDER_STRONG)),
        on_click=lambda e: ft.context.page.show_dialog(picker),
    )

    def on_change(e):
        # 选中值当场归一为 naive，避免 aware 值流到比较/入库链路
        picked = as_naive(e.control.value)
        picker.value = picked  # 保持选中值，供提交时读取
        caption.value = fmt(picked)
        try:
            caption.update()
        except Exception:
            # 对话框正在收起时按钮可能已卸载，刷新失败不影响取值
            pass

    picker.on_change = on_change
    return button, picker


def _build_form(dlg, task=None):
    """为新建/更新弹窗创建表单字段，返回紧凑的两列布局内容。

    两个对话框字段完全相同，仅初始值不同，抽出来避免重复且便于统一样式。
    """
    today = datetime.date.today()
    is_update = task is not None
    start = task.start_time if is_update else datetime.datetime.combine(today, datetime.time())
    end = task.end_time if is_update else datetime.datetime.combine(
        today + datetime.timedelta(days=7), datetime.time())

    # 与新建工作弹窗共用同一套暗色科技感表单控件
    dlg.name_field = form_field(
        ft.TextField, label=_required_label("任务名称"), width=_COL_W,
        value=task.name if is_update else "",
    )
    dlg.desc_field = form_field(
        ft.TextField, label="描述", multiline=True, max_lines=3, width=_FORM_W,
        value=task.description if is_update else "",
    )
    dlg.status_field = form_field(
        ft.Dropdown, label=_required_label("状态"), width=_COL_W,
        options=[form_option(i) for i in Status.list()],
        value=Status.normalize(task.status) if is_update else Status.NOT_START,
    )
    dlg.assignee_field = form_field(
        ft.TextField, label="负责人", width=_COL_W,
        value=task.assignee if is_update else "",
    )
    dlg.tags_field = form_field(
        ft.TextField, label="标签（逗号分隔）", width=_FORM_W,
        value=', '.join(task.tags) if is_update else "",
    )
    dlg.hours_field = form_field(
        ft.TextField, label="预估工时（小时）", width=_COL_W,
        keyboard_type=ft.KeyboardType.NUMBER,
        value=str(task.estimate_hours or '') if is_update else '',
    )
    # 两个独立日期选择器：按钮显示已选日期，点击弹日历选择
    start_button, dlg.start_picker = _date_picker(start, "开始日期")
    end_button, dlg.end_picker = _date_picker(end, "结束日期")

    # 两列紧凑布局：一眼看全，避免底部大片空白；字段定宽避免溢出弹窗
    return ft.Container(
        width=_FORM_W,
        content=ft.Column([
            ft.Row([dlg.name_field, dlg.status_field], spacing=10),
            ft.Row([dlg.assignee_field, dlg.hours_field], spacing=10),
            dlg.tags_field,
            dlg.desc_field,
            # 日期选择器放表单最后一行
            ft.Row([start_button, end_button], spacing=10),
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
            primary_button("确定", self.submit),
        ]
        self.actions_padding = ft.Padding(0, 0, FORM_GAP, 12)

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
            primary_button("确定", self.submit),
        ]
        self.actions_padding = ft.Padding(0, 0, FORM_GAP, 12)

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
            primary_button("确定", self.submit),
        ]
        self.actions_padding = ft.Padding(0, 0, FORM_GAP, 12)

    def submit(self, e):
        try:
            TaskService.delete(id=self.task.id)
        except Exception as ex:
            ft.context.page.show_dialog(ft.SnackBar(ft.Text(f"删除失败：{ex}")))
            return

        ft.context.page.pop_dialog()
        if self.on_saved:
            self.on_saved()  # noqa
