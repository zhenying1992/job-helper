import datetime
from collections.abc import Callable

import flet as ft
from flet.controls.base_control import skip_field

from constant import COLOR_TEXT, Status, COLOR_PRIMARY
from data.model import Task
from data.service import TaskService


@ft.control("AlertDialog")
class CreateTaskDialog(ft.AlertDialog):
    # 只作 Python 引用，不进控件树
    job_id: int = skip_field()
    on_saved: Callable = skip_field()

    name_field: ft.TextField = skip_field()
    desc_field: ft.TextField = skip_field()
    status_field: ft.Dropdown = skip_field()
    picker: ft.DateRangePicker = skip_field()

    def init(self):
        today = datetime.date.today()
        today_7 = today + datetime.timedelta(days=7)

        self.name_field = ft.TextField(
            label="任务名称",
            color=COLOR_TEXT,
            on_change=lambda e: setattr(self.name_field, "value", e.control.value),
        )
        self.desc_field = ft.TextField(
            label="描述",
            color=COLOR_TEXT,
            multiline=True,
            on_change=lambda e: setattr(self.desc_field, "value", e.control.value),
        )
        self.status_field = ft.Dropdown(
            label="状态",
            color=COLOR_TEXT,
            options=[ft.DropdownOption(i) for i in Status.list()],
            value=Status.NOT_START,
            # on_change=lambda e: setattr(self.status_field, "value", e.control.value),
        )
        self.picker = ft.DateRangePicker(
            locale=ft.Locale("zh", "Hans"),
            start_value=datetime.datetime.combine(today, datetime.time()),
            end_value=datetime.datetime.combine(today_7, datetime.time()),
            current_date=today,
        )

        picker_button = ft.Button(
            icon=ft.Icons.CALENDAR_MONTH,
            content="选择时间",
            on_click=lambda _: ft.context.page.show_dialog(self.picker),
        )

        self.title = ft.Text("新建任务", color=COLOR_PRIMARY)
        self.content = ft.Column(
            [self.name_field, self.desc_field, self.status_field, picker_button],
            tight=True,
        )
        self.actions = [
            ft.TextButton("取消", on_click=lambda e: ft.context.page.pop_dialog()),
            ft.Button(
                content="确定",
                bgcolor=COLOR_PRIMARY,
                color="white",
                on_click=self.submit,
            ),
        ]

    def submit(self, e):
        try:
            TaskService.create(
                job_id=self.job_id,
                name=(self.name_field.value or "").strip(),
                description=(self.desc_field.value or "").strip(),
                status=self.status_field.value,
                start_time=self.picker.start_value,
                end_time=self.picker.end_value,
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
    picker: ft.DateRangePicker = skip_field()

    def init(self):
        today = datetime.date.today()

        self.name_field = ft.TextField(
            label="任务名称",
            color=COLOR_TEXT,
            value=self.task.name,
            on_change=lambda e: setattr(self.name_field, "value", e.control.value),
        )
        self.desc_field = ft.TextField(
            label="描述",
            color=COLOR_TEXT,
            multiline=True,
            value=self.task.description,
            on_change=lambda e: setattr(self.desc_field, "value", e.control.value),
        )
        self.status_field = ft.Dropdown(
            label="状态",
            color=COLOR_TEXT,
            options=[ft.DropdownOption(i) for i in Status.list()],
            value=self.task.status,
            # on_change=lambda e: setattr(self.status_field, "value", e.control.value),
        )
        self.picker = ft.DateRangePicker(
            locale=ft.Locale("zh", "Hans"),
            start_value=self.task.start_time,
            end_value=self.task.end_time,
            current_date=today,
        )

        picker_button = ft.Button(
            icon=ft.Icons.CALENDAR_MONTH,
            content="选择时间",
            on_click=lambda _: ft.context.page.show_dialog(self.picker),
        )

        self.title = ft.Text("更新任务", color=COLOR_PRIMARY)
        self.content = ft.Column(
            [self.name_field, self.desc_field, self.status_field, picker_button],
            tight=True,
        )
        self.actions = [
            ft.TextButton("取消", on_click=lambda e: ft.context.page.pop_dialog()),
            ft.Button(
                content="确定",
                bgcolor=COLOR_PRIMARY,
                color="white",
                on_click=self.submit,
            ),
        ]

    def submit(self, e):
        try:
            TaskService.update(
                id=self.task.id,
                name=(self.name_field.value or "").strip(),
                description=(self.desc_field.value or "").strip(),
                status=self.status_field.value,
                start_time=self.picker.start_value,
                end_time=self.picker.end_value,
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
        self.title = ft.Text("删除任务", color=COLOR_PRIMARY)

        self.content = ft.Column([
            ft.Text(f"确定要删除任务{self.task.name}么？", color=COLOR_TEXT, size=11),
        ], tight=True)

        self.actions = [
            ft.TextButton("取消", on_click=lambda e: ft.context.page.pop_dialog()),
            ft.Button(
                content="确定",
                bgcolor=COLOR_PRIMARY,
                color="white",
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
