import logging
import re
import shutil
from pathlib import Path
from typing import Any

import flet as ft
import flet_dropzone as ftd
from flet import MainAxisAlignment

from common.decorate import catch_error
from common.util import datetime_2_date_str
from config import get_plugin_path
from constant import DATE_TIME_FMT
from data.model import Plugin
from data.service import PluginService

logger = logging.getLogger(__name__)


@ft.component
@catch_error
def setting_view():
    selected_key, set_selected_key = ft.use_state("plugins")

    return ft.Row([
        Left(selected_key, set_selected_key).build(),
        Right(selected_key).build(),
    ], expand=True)


class Left:
    def __init__(self, selected_key, set_selected_key):
        self.selected_key = selected_key
        self.set_selected_key = set_selected_key

    def build(self):
        # 配置菜单项
        menu_items = [
            {"key": "plugins", "icon": ft.Icons.PHONE, "label": "插件管理"},
            {"key": "general", "icon": ft.Icons.SETTINGS, "label": "通用设置"},
            {"key": "about", "icon": ft.Icons.INFO_OUTLINE, "label": "关于"},
        ]

        # 左侧菜单
        menu_buttons = []
        for item in menu_items:
            is_selected = item["key"] == self.selected_key
            btn = ft.Container(
                content=ft.Row([
                    ft.Icon(item["icon"], size=20,
                            color=ft.Colors.PRIMARY if is_selected else ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(item["label"], size=14,
                            color=ft.Colors.PRIMARY if is_selected else ft.Colors.ON_SURFACE_VARIANT,
                            weight=ft.FontWeight.W_500 if is_selected else ft.FontWeight.NORMAL),
                ], spacing=10),
                # padding=ft.padding.symmetric(horizontal=16, vertical=12),
                border_radius=8,
                ink=True,
                bgcolor=ft.Colors.PRIMARY_CONTAINER if is_selected else None,
                on_click=lambda e, key=item["key"]: self.set_selected_key(key),
            )
            menu_buttons.append(btn)

        return ft.Container(
            content=ft.Column(menu_buttons, spacing=4),
            width=200,
            padding=10,
            # border=ft.border.only(right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
        )


class Right:
    def __init__(self, selected_key: str):
        self.selected_key = selected_key

    def build(self):
        if self.selected_key == "plugins":
            content = PluginContent().build()
        else:
            content = PluginContent().build()

        return ft.Container(
            content=content,
            expand=True,
        )


class PluginContent:
    plugin_path = get_plugin_path()
    service = PluginService()

    @ft.component
    def build(self):
        self.plugins, self.set_plugins = ft.use_state(self.service.list())

        return ft.Column([
            ft.Text("已安装插件", weight=ft.FontWeight.BOLD),
            ft.Divider(),
            self.build_table(),
        ], expand=True, scroll=ft.ScrollMode.AUTO)

    def build_table(self):
        table = ft.DataTable(
            columns=[
                ft.DataColumn(label=ft.Text("名称", color="#cbd5e1"),
                              heading_row_alignment=MainAxisAlignment.CENTER),
                ft.DataColumn(label=ft.Text("版本", color="#cbd5e1"),
                              heading_row_alignment=MainAxisAlignment.CENTER),
                ft.DataColumn(label=ft.Text("描述", color="#cbd5e1"),
                              heading_row_alignment=MainAxisAlignment.CENTER),
                ft.DataColumn(label=ft.Text("更新时间", color="#cbd5e1"),
                              heading_row_alignment=MainAxisAlignment.CENTER),
                ft.DataColumn(label=ft.Text("操作", color="#cbd5e1"),
                              heading_row_alignment=MainAxisAlignment.CENTER),
            ],
            rows=[
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(plugin.name)),
                    ft.DataCell(ft.Text(plugin.version)),
                    ft.DataCell(ft.Text(plugin.description)),
                    ft.DataCell(
                        ft.Text(datetime_2_date_str(plugin.created_time, fmt=DATE_TIME_FMT),
                                text_align=ft.TextAlign.CENTER, color="#cbd5e1")
                    ),
                    ft.DataCell(
                        ft.TextButton("删除", on_click=lambda e, _plugin=plugin: self.delete_plugin(_plugin)),
                    )]
                )
                for plugin in self.plugins
            ],
            expand=True,
        )

        # 拖拽导入区域
        return ft.Container(
            ftd.Dropzone(
                content=ft.Container(
                    table,
                    # height=500,
                    alignment=ft.Alignment.CENTER,
                    # bgcolor="red",
                ),
                on_dropped=lambda e: self.add_plugins(e.files),
                on_entered=lambda e: print("Entered"),
                on_exited=lambda e: print("Exited"),
            )
        )

    def add_plugins(self, files):
        for file in files:
            self.add_plugin(file)

        self.refresh()

    def add_plugin(self, file):
        try:
            ns = self.load(file.path)
        except Exception as ex:
            ft.context.page.show_dialog(ft.Banner(
                bgcolor=ft.Colors.ERROR_CONTAINER,
                leading=ft.Icon(ft.Icons.ERROR_OUTLINE),
                content=ft.Text(f"校验不通过: {ex}"),
                actions=[
                    ft.TextButton("知道了", on_click=lambda e: ft.context.page.pop_dialog()),
                ],
            ))
            return

        name, version, description = ns['PLUGIN_NAME'], ns['PLUGIN_VERSION'], ns['PLUGIN_DESCRIPTION']
        plugin = self.service.query(name=name)
        if not plugin:
            logger.info(f'Adding plugin {name}')
            shutil.copy2(file.path, f'{self.plugin_path}/{file.name}')
            self.service.create(name=name, version=version, description=description, file_name=file.name)
            logger.info(f'插件{file.name}安装成功')
            return

        # 导入的版本小于当前
        if version <= plugin.version:
            ft.context.page.show_dialog(ft.Banner(
                bgcolor=ft.Colors.ERROR_CONTAINER,
                leading=ft.Icon(ft.Icons.ERROR_OUTLINE),
                content=ft.Text(f"校验不通过: 插件[{name}]文件版本[{version}]低于当前版本[{version}]"),
                actions=[
                    ft.TextButton("知道了", on_click=lambda e: ft.context.page.pop_dialog()),
                ],
            ))
            return

        # 更新插件
        self.delete_plugin(plugin)
        self.service.create(name=name, version=version, description=description, file_name=file.name)
        shutil.copy2(file.path, f'{self.plugin_path}/{file.name}')
        logger.info(f'插件{file.name}安装成功')

    def load(self, path) -> dict[str, Any]:
        ns = {}
        exec(open(path, encoding="utf-8").read(), ns)

        assert 'PLUGIN_NAME' in ns, "缺少PLUGIN_NAME变量"
        assert 'PLUGIN_VERSION' in ns, '缺少PLUGIN_VERSION变量'
        assert 'PLUGIN_DESCRIPTION' in ns, '缺少PLUGIN_DESCRIPTION变量'
        assert 'build' in ns, '缺少build方法'
        return ns

    def is_exist(self, name: str, version: int) -> bool:
        for plugin in self.plugins:
            if plugin.name == name and plugin.version == version:
                return True

        return False

    def refresh(self):
        self.set_plugins(list(Plugin.select()))

    def delete_plugin(self, plugin: Plugin):
        """删除插件"""
        self.service.delete(plugin.id)
        logger.info(f'删除文件: {self.plugin_path}/{plugin.file_name}')
        Path(f'{self.plugin_path}/{plugin.file_name}').unlink(missing_ok=True)
        self.refresh()
