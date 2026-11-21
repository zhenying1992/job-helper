"""配置中心：插件管理、数据管理（备份/恢复/导入导出/回收站）、通用设置、关于。"""

import ast
import logging
import shutil
from pathlib import Path

import flet as ft
import flet_dropzone as ftd
from flet import MainAxisAlignment

from common.decorate import catch_error
from common.util import datetime_2_date_str
from config import get_db_path, get_plugin_path, get_work_dir
from constant import DATE_TIME_FMT
from data.model import Plugin
from data.service import (
    BackupService, JobService, PluginService, TaskService,
)
from theme import (
    TEXT, MUTED, ACCENT, ACCENT_SOFT, BG_TABLE, BG_TABLE_HEAD, BG_PANEL, BG_INPUT,
    BORDER, DANGER, SUCCESS, WARN, RADIUS_MD, RADIUS_LG,     FS_XL, FS_BASE, FS_MD, FS_SM,
    BTN_TEXT, FONT_MONO,
)

logger = logging.getLogger(__name__)

REQUIRED = ('PLUGIN_NAME', 'PLUGIN_VERSION', 'PLUGIN_DESCRIPTION', 'build')
MENU = [
    ('plugins', ft.Icons.EXTENSION, '插件管理'),
    ('data', ft.Icons.STORAGE, '数据管理'),
    ('recycle', ft.Icons.DELETE_SWEEP, '回收站'),
    ('general', ft.Icons.SETTINGS, '通用设置'),
    ('about', ft.Icons.INFO_OUTLINE, '关于'),
]


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
        buttons = []
        for key, icon, label in MENU:
            active = key == self.selected_key
            color = ACCENT if active else MUTED
            buttons.append(ft.Container(
                content=ft.Row([
                    ft.Icon(icon, size=20, color=color),
                    ft.Text(label, size=FS_BASE, color=color,
                            weight=ft.FontWeight.W_600 if active else ft.FontWeight.W_400),
                ], spacing=10),
                padding=ft.Padding(12, 10, 12, 10),
                border_radius=RADIUS_LG,
                ink=True,
                bgcolor=BG_TABLE_HEAD if active else None,
                on_click=lambda e, k=key: self.set_selected_key(k),
            ))
        return ft.Container(
            content=ft.Column(buttons, spacing=4), width=210, padding=10,
            bgcolor=BG_PANEL, border_radius=RADIUS_LG,
        )


class Right:
    def __init__(self, selected_key):
        self.selected_key = selected_key

    def build(self):
        pages = {
            'plugins': PluginContent,
            'data': DataContent,
            'recycle': RecycleContent,
            'general': GeneralContent,
            'about': AboutContent,
        }
        cls = pages.get(self.selected_key, PluginContent)
        return ft.Container(cls().build(), expand=True)


def _section(title: str, desc: str = '') -> list[ft.Control]:
    controls = [ft.Text(title, size=FS_XL, weight=ft.FontWeight.BOLD, color=ACCENT)]
    if desc:
        controls.append(ft.Text(desc, size=FS_SM, color=MUTED))
    controls.append(ft.Divider(color=BORDER, height=1))
    return controls


def _banner(message: str, error: bool = True):
    ft.context.page.show_dialog(ft.Banner(
        bgcolor=BG_TABLE_HEAD,
        leading=ft.Icon(ft.Icons.ERROR_OUTLINE if error else ft.Icons.CHECK_CIRCLE_OUTLINE,
                        color=DANGER if error else SUCCESS),
        content=ft.Text(message, color=TEXT),
        actions=[ft.TextButton("知道了", on_click=lambda e: ft.context.page.pop_dialog())],
    ))


# ---------------------------------------------------------------- 插件管理
class PluginContent:
    def __init__(self):
        self.plugin_path = get_plugin_path()
        self.service = PluginService()

    @ft.component
    def build(self):
        plugins, set_plugins = ft.use_state(self.service.list())

        def refresh():
            set_plugins(lambda _: self.service.list())

        def add_plugins(files):
            for file in files:
                self._add_plugin(file)
            refresh()

        columns = [
            ft.DataColumn(label=ft.Text(title, color=TEXT),
                          heading_row_alignment=MainAxisAlignment.CENTER)
            for title in ("名称", "版本", "描述", "安装时间", "操作")
        ]
        rows = [
            ft.DataRow(cells=[
                ft.DataCell(ft.Text(p.name, color=TEXT)),
                ft.DataCell(ft.Text(str(p.version), color=TEXT)),
                ft.DataCell(ft.Text(p.description, color=TEXT)),
                ft.DataCell(ft.Text(datetime_2_date_str(p.created_time, DATE_TIME_FMT),
                                    text_align=ft.TextAlign.CENTER, color=TEXT)),
                ft.DataCell(ft.TextButton(
                    "删除", on_click=lambda e, plugin=p: self._delete_plugin(plugin, refresh))),
            ])
            for p in plugins
        ]
        table = ft.DataTable(
            columns=columns, rows=rows, expand=True,
            border_radius=RADIUS_MD, bgcolor=BG_TABLE, heading_row_color=BG_TABLE_HEAD,
        )

        return ft.Column([
            *_section("插件管理", "拖入 .py 插件安装；插件会在对应类型的工作详情页加载为独立视图"),
            ft.Container(
                ftd.Dropzone(
                    content=ft.Container(table, alignment=ft.Alignment.CENTER),
                    on_dropped=lambda e: add_plugins(e.files),
                ), expand=True,
            ),
        ], expand=True, scroll=ft.ScrollMode.AUTO)

    def _add_plugin(self, file):
        try:
            meta = self._parse_meta(file.path)
        except Exception as ex:
            logger.warning("插件校验失败: %s", ex)
            _banner(f"校验不通过: {ex}")
            return

        name, version, description = meta
        installed = self.service.query(name=name)
        if installed and version <= installed.version:
            _banner(f"插件[{name}]版本[{version}]不高于当前版本[{installed.version}]")
            return
        if installed:
            self._delete_plugin(installed, refresh=None)

        shutil.copy2(file.path, self.plugin_path / file.name)
        self.service.create(name, version, description, file.name)
        logger.info("插件 %s 安装成功", file.name)

    def _delete_plugin(self, plugin, refresh):
        self.service.delete(plugin.id)
        (self.plugin_path / plugin.file_name).unlink(missing_ok=True)
        logger.info("删除插件: %s", plugin.file_name)
        if refresh:
            refresh()

    @staticmethod
    def _parse_meta(path) -> tuple[str, int, str]:
        """用 AST 静态读取插件声明，安装阶段不执行插件代码。"""
        source = Path(path).read_text(encoding='utf-8')
        tree = ast.parse(source, filename=str(path))
        values = {}
        has_build = False
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == 'build':
                has_build = True
            elif isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name):
                key = node.targets[0].id
                if key in REQUIRED and isinstance(node.value, ast.Constant):
                    values[key] = node.value.value
        missing = [n for n in REQUIRED if n != 'build' and n not in values]
        if missing:
            raise ValueError(f"缺少声明: {', '.join(missing)}")
        if not has_build:
            raise ValueError("缺少 build 方法")
        return values['PLUGIN_NAME'], int(values['PLUGIN_VERSION']), values['PLUGIN_DESCRIPTION']


# ---------------------------------------------------------------- 数据管理
class DataContent:
    """数据库整库备份与恢复。备份列表实时刷新。"""

    @ft.component
    def build(self):
        backups, set_backups = ft.use_state(BackupService.list_backups())

        def refresh():
            set_backups(lambda _: BackupService.list_backups())

        def do_backup(e):
            name_field = ft.TextField(
                label="备份名称", color=TEXT,
                hint_text="例如：项目归档", autofocus=True,
            )

            def confirm(_):
                name = (name_field.value or '').strip()
                if not name:
                    _banner("请填写备份名称")
                    return
                try:
                    path = BackupService.backup(name)
                    ft.context.page.pop_dialog()
                    refresh()  # 备份成功后实时刷新列表
                    ft.context.page.show_dialog(
                        ft.SnackBar(ft.Text(f"备份成功：{path.name}")))
                except Exception as ex:
                    logger.exception("备份失败")
                    ft.context.page.pop_dialog()
                    _banner(f"备份失败：{ex}")

            ft.context.page.show_dialog(ft.AlertDialog(
                title=ft.Text("立即备份", color=ACCENT),
                bgcolor=BG_PANEL,
                content=name_field,
                actions=[
                    ft.TextButton("取消", on_click=lambda e: ft.context.page.pop_dialog()),
                    ft.Button("开始备份", bgcolor=ACCENT, color=BTN_TEXT, on_click=confirm),
                ],
            ))

        def do_restore(e):
            def confirm(_):
                try:
                    targets = BackupService.list_backups()
                    if not targets:
                        ft.context.page.pop_dialog()
                        _banner("暂无备份文件")
                        return
                    BackupService.restore(targets[0])
                    ft.context.page.pop_dialog()
                    _banner(f"已从 {targets[0].name} 恢复，请重启应用", error=False)
                except Exception as ex:
                    logger.exception("恢复失败")
                    ft.context.page.pop_dialog()
                    _banner(f"恢复失败：{ex}")

            ft.context.page.show_dialog(ft.AlertDialog(
                title=ft.Text("从备份恢复", color=ACCENT),
                bgcolor=BG_PANEL,
                content=ft.Text("将用最近一次备份覆盖当前数据，当前未备份的改动会丢失。确定继续？",
                                color=TEXT),
                actions=[
                    ft.TextButton("取消", on_click=lambda e: ft.context.page.pop_dialog()),
                    ft.Button("确认恢复", bgcolor=WARN, color=BTN_TEXT, on_click=confirm),
                ],
            ))

        # 表头：备份名 / 日期 / 大小
        head = ft.Row([
            ft.Text("备份名", color=ACCENT_SOFT, size=FS_MD, width=220),
            ft.Text("日期", color=ACCENT_SOFT, size=FS_MD, width=160),
            ft.Text("大小", color=ACCENT_SOFT, size=FS_MD, width=100),
        ], spacing=8)
        backup_rows = []
        for b in backups:
            info = BackupService.backup_info(b)
            size_kb = info['size'] / 1024
            size_text = f"{size_kb:.0f} KB" if size_kb < 1024 else f"{size_kb / 1024:.1f} MB"
            backup_rows.append(ft.Row([
                ft.Icon(ft.Icons.BACKUP, color=ACCENT_SOFT, size=FS_BASE),
                ft.Text(info['name'], color=TEXT, size=FS_MD, width=200,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, tooltip=info['name']),
                ft.Text(info['date'], color=MUTED, size=FS_SM, width=160,
                        font_family=FONT_MONO),
                ft.Text(size_text, color=MUTED, size=FS_SM, width=100,
                        font_family=FONT_MONO),
            ], spacing=8))
        if not backup_rows:
            backup_rows = [ft.Text("暂无备份", color=MUTED, size=FS_MD)]

        return ft.Column([
            *_section("数据管理", "工作目录内的数据库快照，可备份与恢复"),
            ft.Row([
                ft.Button("立即备份", icon=ft.Icons.BACKUP, bgcolor=ACCENT, color=BTN_TEXT,
                          on_click=do_backup),
                ft.Button("从备份恢复", icon=ft.Icons.RESTORE, bgcolor=WARN, color=BTN_TEXT,
                          on_click=do_restore),
            ], spacing=10),
            ft.Container(height=12),
            head,
            ft.Divider(color=BORDER, height=1),
            ft.Column(backup_rows, spacing=6, scroll=ft.ScrollMode.AUTO, expand=True),
        ], expand=True, scroll=ft.ScrollMode.AUTO)


# ---------------------------------------------------------------- 回收站
class RecycleContent:
    """软删除的工作与任务，支持还原与彻底删除。操作后列表实时刷新并提示。"""

    @ft.component
    def build(self):
        jobs, set_jobs = ft.use_state(JobService.recycle_bin())
        tasks, set_tasks = ft.use_state(TaskService.recycle_bin())

        def toast(msg: str, error: bool = False):
            ft.context.page.show_dialog(ft.SnackBar(ft.Text(
                msg, color=DANGER if error else SUCCESS)))

        def refresh():
            set_jobs(lambda _: JobService.recycle_bin())
            set_tasks(lambda _: TaskService.recycle_bin())

        def restore_job(jid, name):
            JobService.restore(jid)
            refresh()
            toast(f"已还原工作：{name}")

        def purge_job(jid, name):
            JobService.purge(jid)
            refresh()
            toast(f"已彻底删除工作：{name}")

        def restore_task(tid, name):
            TaskService.restore(tid)
            refresh()
            toast(f"已还原任务：{name}")

        def purge_task(tid, name):
            TaskService.purge(tid)
            refresh()
            toast(f"已彻底删除任务：{name}")

        job_rows = [
            ft.Row([
                ft.Icon(ft.Icons.FOLDER, color=MUTED, size=FS_BASE),
                ft.Text(j.name, color=TEXT, size=FS_MD, width=300),
                ft.TextButton("还原", on_click=lambda e, i=j.id, n=j.name: restore_job(i, n)),
                ft.TextButton("彻底删除", style=ft.ButtonStyle(color=DANGER),
                              on_click=lambda e, i=j.id, n=j.name: purge_job(i, n)),
            ], spacing=8)
            for j in jobs
        ] or [ft.Text("回收站中没有已删除的工作", color=MUTED, size=FS_MD)]

        task_rows = [
            ft.Row([
                ft.Icon(ft.Icons.CHECK_BOX, color=MUTED, size=FS_BASE),
                ft.Text(t.name, color=TEXT, size=FS_MD, width=300),
                ft.TextButton("还原", on_click=lambda e, i=t.id, n=t.name: restore_task(i, n)),
                ft.TextButton("彻底删除", style=ft.ButtonStyle(color=DANGER),
                              on_click=lambda e, i=t.id, n=t.name: purge_task(i, n)),
            ], spacing=8)
            for t in tasks
        ] or [ft.Text("回收站中没有已删除的任务", color=MUTED, size=FS_MD)]

        return ft.Column([
            *_section("回收站", "软删除的内容保留在此，可还原；彻底删除不可恢复"),
            ft.Text("已删除的工作", color=ACCENT_SOFT, size=FS_BASE, weight=ft.FontWeight.W_500),
            ft.Column(job_rows, spacing=6),
            ft.Container(height=16),
            ft.Text("已删除的任务", color=ACCENT_SOFT, size=FS_BASE, weight=ft.FontWeight.W_500),
            ft.Column(task_rows, spacing=6, scroll=ft.ScrollMode.AUTO, expand=True),
        ], expand=True, scroll=ft.ScrollMode.AUTO)


# ---------------------------------------------------------------- 通用设置
class GeneralContent:
    def build(self):
        work_dir = get_work_dir()
        return ft.Column([
            *_section("通用设置", "当前应用的基础运行信息"),
            ft.Row([
                ft.Icon(ft.Icons.FOLDER_OPEN, color=ACCENT, size=20),
                ft.Text(f"工作目录：{work_dir}", color=TEXT, size=FS_BASE),
            ], spacing=10),
            ft.Row([
                ft.Icon(ft.Icons.STORAGE, color=ACCENT, size=20),
                ft.Text(f"数据库：{get_db_path()}", color=TEXT, size=FS_BASE),
            ], spacing=10),
            ft.Container(height=12),
            ft.Text("主题", color=ACCENT_SOFT, size=FS_BASE, weight=ft.FontWeight.W_500),
            ft.Text("暗色科技风（Neon-tech）· 颜色与字号统一在 theme.py 管理",
                    color=MUTED, size=FS_MD),
        ], expand=True, scroll=ft.ScrollMode.AUTO)


# ---------------------------------------------------------------- 关于
class AboutContent:
    def build(self):
        return ft.Column([
            *_section("关于"),
            ft.Icon(ft.Icons.HUB, color=ACCENT, size=56),
            ft.Text("JobHelper 工作小助手", color=TEXT, size=FS_XL,
                    weight=ft.FontWeight.BOLD),
            ft.Text("版本 0.1.0", color=MUTED, size=FS_BASE),
            ft.Container(height=16),
            ft.Text("工作 / 任务 / 日历 / 甘特 / 依赖拓扑 / 看板 / 审计台账",
                    color=TEXT, size=FS_MD),
            ft.Text("基于 Flet + Peewee 构建", color=MUTED, size=FS_SM),
        ], expand=True, scroll=ft.ScrollMode.AUTO,
           horizontal_alignment=ft.CrossAxisAlignment.CENTER)
