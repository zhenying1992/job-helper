import logging

import flet as ft
import flet_dropzone as ftd

from common.decorate import catch_error
from common.plugin_host import build_view, find_for_type
from common.util import datetime_2_date_str
from constant import (
    BG_PANEL, BORDER_RADIUS, COLOR_PRIMARY, COLOR_SUCCESS, COLOR_TEXT, COLOR_WARN,
    DATE_FMT, Priority, Status,
)
from data.model import Job
from data.service import AttachmentService, JobService, LogService
from pages.audit import open_audit, open_export
from pages.task.board import TaskBoard
from pages.task.gantt import TaskGantt
from pages.task.list import task_list_view
from pages.task.topo import TaskTopo
from theme import (
    ACCENT as ACTIVE, MUTED as INACTIVE, BG_HEADER_BAR, BORDER,
    FS_XL, FS_MD, FONT_MONO, BTN_TEXT, RADIUS_SM, glow,
)

logger = logging.getLogger(__name__)

BASE_VIEWS = [
    ('list', '任务列表'),
    ('board', '看板'),
    ('gantt', '甘特图'),
    ('topology', '依赖拓扑图'),
]


def _views_for(job: Job) -> list[tuple[str, str]]:
    """基础视图 + 该工作类型对应的插件视图（真正接线的扩展入口）。"""
    views = list(BASE_VIEWS)
    plugin = find_for_type(job.type)
    if plugin:
        views.append((f'plugin:{plugin.id}', f'⚡ {plugin.name}'))
    return views


@ft.component
@catch_error
def job_view():
    params = ft.use_route_params()
    job_id = int(params['job_id'])
    if not job_id:
        return ft.Text("请在工作列表中选择", color=COLOR_WARN)

    # 每次渲染前按当前任务重算工作进度与状态，确保顶栏/进度条实时反映任务变化
    JobService.sync_progress(job_id)
    job = JobService.get(job_id)
    views = _views_for(job)
    # 当前选中视图若不在可用列表（如插件被卸载），回退到第一个
    current_view, set_current_view = ft.use_state("list")
    if current_view not in {key for key, _ in views}:
        current_view = views[0][0]
    refresh_flag, set_refresh_flag = ft.use_state(0)

    def bump():
        set_refresh_flag(refresh_flag + 1)

    return ft.Column([
        HeaderBar(job).build(),
        ft.Row([
            Left(job, bump).build(),
            ft.Container(width=20),
            Right(job, views, current_view, set_current_view, refresh_flag, bump).build(),
        ], expand=True),
    ], expand=True)


def _toast(message: str):
    ft.context.page.show_dialog(ft.SnackBar(ft.Text(message, color=BTN_TEXT)))


@ft.component
def JobDetails(job: Job, bump=None):
    """工作详情卡片：名称/描述/优先级可原地编辑，状态用彩色 chip 展示。

    原地编辑用一个跨渲染稳定的 dict 缓存输入值；on_change 只写缓存、不 set_state，
    避免每次按键都重建控件导致输入框失焦。点保存时才读缓存落库并 bump 上层刷新。
    """
    editing, set_editing = ft.use_state('')          # 当前正在编辑的字段名
    drafts = ft.use_state(lambda: {})[0]             # 跨渲染稳定的输入缓存

    def start(field: str):
        drafts.setdefault(field, getattr(job, field))
        set_editing(field)

    def save(field: str):
        value = (drafts.get(field) or '').strip()
        if field == 'name':
            if not value:
                _toast('名称不能为空')
                return
            if JobService.exists_name(value, exclude_id=job.id):
                _toast('工作名称已存在')
                return
        try:
            JobService.update(job.id, **{field: value})
        except Exception as ex:
            logger.exception('原地编辑保存失败')
            _toast(f'保存失败：{ex}')
            return
        set_editing('')
        if bump:
            bump()

    def editable(label: str, field: str):
        """展示态文本 + 编辑按钮；编辑态紧凑输入框/选择器 + 保存/取消。

        展示态文本 expand 占据卡片内容区剩余宽度，长文本按 ELLIPSIS 截断，
        不再撑破 300px 卡片。优先级编辑态用 dense Dropdown，比普通下拉更紧凑。
        """
        if editing == field:
            if field == 'priority':
                box = ft.Dropdown(
                    value=drafts.get(field, getattr(job, field)),
                    options=[ft.DropdownOption(key=p, text=p) for p in Priority.list()],
                    on_select=lambda e, f=field: drafts.__setitem__(f, e.control.value),
                    dense=True, text_size=12, width=76, height=36,
                    content_padding=ft.Padding(4, 0, 4, 0),
                )
            else:
                box = ft.TextField(
                    value=drafts.get(field, getattr(job, field)),
                    on_change=lambda e, f=field: drafts.__setitem__(f, e.control.value),
                    width=118, height=34, text_size=13,
                    content_padding=ft.Padding(6, 4, 6, 4),
                )
            return ft.Row([
                ft.Text(f"{label}:", color=COLOR_TEXT, size=12, width=34),
                box,
                ft.IconButton(ft.Icons.CHECK, icon_color=COLOR_SUCCESS, icon_size=15,
                              width=28, tooltip="保存", on_click=lambda e, f=field: save(f)),
                ft.IconButton(ft.Icons.CLOSE, icon_color=INACTIVE, icon_size=15,
                              width=28, tooltip="取消", on_click=lambda e: set_editing('')),
            ], spacing=2)
        return ft.Row([
            ft.Text(f"{label}: {getattr(job, field)}", color=COLOR_TEXT, size=13,
                    max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
            ft.IconButton(ft.Icons.EDIT, icon_color=INACTIVE, icon_size=14,
                          tooltip=f"编辑{label}", on_click=lambda e, f=field: start(f)),
        ], spacing=2)

    return ft.Container(
        width=300, bgcolor=BG_PANEL, border_radius=BORDER_RADIUS, padding=20,
        content=ft.Column([
            ft.Text("工作详情", color=COLOR_PRIMARY, size=FS_XL, weight=ft.FontWeight.BOLD),
            ft.Divider(color=BORDER, height=1),
            ft.Container(height=6),
            editable("名称", "name"),
            editable("描述", "description"),
            editable("优先级", "priority"),
            ft.Text(f"开始时间: {datetime_2_date_str(job.start_time, DATE_FMT)}",
                    color=COLOR_TEXT, size=13),
            ft.Text(f"结束时间: {datetime_2_date_str(job.end_time, DATE_FMT)}",
                    color=COLOR_TEXT, size=13),
            ft.Container(height=4),
            ft.Row([
                ft.Text("进度: ", color=COLOR_TEXT, size=13),
                ft.Stack([
                    ft.ProgressBar(bar_height=12, width=160, value=job.progress / 100,
                                   bgcolor=BORDER,
                                   color=COLOR_SUCCESS if job.progress == 100 else COLOR_PRIMARY),
                    ft.Text(f"{job.progress}%", size=11),
                ], width=160, alignment=ft.Alignment.CENTER),
            ]),
            ft.Row([
                ft.Text("状态:", color=COLOR_TEXT, size=13),
                ft.Container(
                    ft.Text(job.status, color=BG_HEADER_BAR, size=12,
                            font_family=FONT_MONO, weight=ft.FontWeight.BOLD),
                    bgcolor=Status.color(job.status),
                    border_radius=RADIUS_SM,
                    padding=ft.Padding(8, 2, 8, 2),
                ),
            ], spacing=8),
        ], spacing=4),
    )


class HeaderBar:
    def __init__(self, job: Job):
        self.job = job

    def build(self):
        return ft.Container(
            bgcolor=BG_HEADER_BAR,
            content=ft.Row([
                ft.TextButton("← 返回", on_click=lambda e: ft.context.page.navigate('/jobs'),
                              style=ft.ButtonStyle(color=INACTIVE)),
                ft.Text(self.job.name, color=ACTIVE, weight=ft.FontWeight.W_600,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                ft.Container(width=12),
                ft.Container(ft.Text(self.job.status, color=BG_HEADER_BAR,
                                     font_family=FONT_MONO, weight=ft.FontWeight.BOLD),
                             bgcolor=ACTIVE, border_radius=4, shadow=glow(ACTIVE, blur=10)),
                ft.Container(width=12),
                ft.Text(f"进度：{self.job.progress}%", color=COLOR_TEXT, font_family=FONT_MONO),
                ft.Container(expand=True),
                ft.PopupMenuButton(
                    icon=ft.Icons.MORE_VERT,
                    items=[
                        ft.PopupMenuItem("查看审计台账", icon=ft.Icons.HISTORY,
                                         on_click=lambda e: open_audit(self.job)),
                        ft.PopupMenuItem("导出审计台账", icon=ft.Icons.DOWNLOAD,
                                         on_click=lambda e: open_export(self.job)),
                    ],
                ),
            ]),
        )


class Left:
    def __init__(self, job: Job, bump=None):
        self.job = job
        self.bump = bump

    def build(self):
        return ft.Column([
            JobDetails(self.job, self.bump),
            ft.Container(height=10),
            self._attachments(),
        ])

    def _attachments(self):
        """附件区：拖拽文件真实落盘，列出已有附件，支持打开与删除。"""
        def on_dropped(e):
            names = AttachmentService.add_many(self.job.id, e.files)
            ft.context.page.show_dialog(
                ft.SnackBar(ft.Text(f"已保存 {len(names)} 个附件"))
            )
            if self.bump:
                self.bump()

        def open_file(name: str):
            path = AttachmentService.path_of(self.job.id, name)
            if not path.exists():
                ft.context.page.show_dialog(ft.SnackBar(ft.Text(f"文件不存在：{name}")))
                return
            try:
                import os
                import subprocess
                import sys
                if sys.platform == 'win32':
                    os.startfile(str(path))  # noqa
                elif sys.platform == 'darwin':
                    subprocess.run(['open', str(path)], check=False)
                else:
                    subprocess.run(['xdg-open', str(path)], check=False)
            except Exception:
                logger.exception("打开附件失败：%s", name)
                ft.context.page.show_dialog(
                    ft.SnackBar(ft.Text(f"无法打开：{name}"))
                )

        def del_file(name: str):
            AttachmentService.delete(self.job.id, name)
            AttachmentService.record_delete(self.job.id, name)
            if self.bump:
                self.bump()

        # 汇总审计记录里出现过的附件名（去重），作为附件列表来源
        names: list[str] = []
        for log in LogService.query(self.job.id):
            for name in log.related_files:
                if name not in names:
                    names.append(name)

        file_rows = [
            ft.Row([
                ft.Icon(ft.Icons.INSERT_DRIVE_FILE, size=FS_MD, color=ACTIVE),
                ft.TextButton(name, on_click=lambda e, n=name: open_file(n), width=190,
                              style=ft.ButtonStyle(color=COLOR_TEXT)),
                ft.IconButton(ft.Icons.OPEN_IN_NEW, icon_color=ACTIVE, icon_size=16,
                              tooltip="打开", on_click=lambda e, n=name: open_file(n)),
                ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=INACTIVE, icon_size=16,
                              tooltip="删除", on_click=lambda e, n=name: del_file(n)),
            ], spacing=2)
            for name in names
        ]
        listing = ft.Column(file_rows, spacing=2, scroll=ft.ScrollMode.AUTO, height=120) \
            if file_rows else ft.Container()

        zone = ftd.Dropzone(
            content=ft.Container(
                ft.Column([
                    ft.Icon(ft.Icons.UPLOAD_FILE, size=28, color=INACTIVE),
                    ft.Text("拖入文件保存为附件", color=INACTIVE, size=FS_MD),
                ], alignment=ft.MainAxisAlignment.CENTER,
                   horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
                alignment=ft.Alignment.CENTER, height=90,
            ),
            on_dropped=on_dropped,
        )
        return ft.Container(
            width=300, bgcolor=BG_PANEL, border_radius=BORDER_RADIUS,
            padding=12,
            content=ft.Column([
                ft.Text("工作附件", color=COLOR_PRIMARY, size=FS_MD, weight=ft.FontWeight.BOLD),
                zone,
                listing,
            ], spacing=6, tight=True),
        )


class Right:
    def __init__(self, job, views, current_view, set_current_view, refresh_flag, bump):
        self.job = job
        self.views = views
        self.current_view = current_view
        self.set_current_view = set_current_view
        self.refresh_flag = refresh_flag
        self.bump = bump

    def build(self):
        return ft.Container(
            height=610,
            bgcolor=BG_PANEL, border_radius=BORDER_RADIUS, padding=20,
            content=ft.Column([
                self._switch_bar(),
                ft.Container(self._main_view(), expand=True,
                             alignment=ft.Alignment(-1.0, -1.0)),
            ], spacing=4,
               horizontal_alignment=ft.CrossAxisAlignment.START,
               alignment=ft.MainAxisAlignment.START),
            expand=True,
        )

    def _switch_bar(self):
        buttons = [
            ft.TextButton(
                label,
                on_click=lambda e, key=key: self.set_current_view(key),
                style=ft.ButtonStyle(color=ACTIVE if self.current_view == key else INACTIVE),
            )
            for key, label in self.views
        ]
        return ft.Column([
            ft.Row([*buttons, ft.Container(expand=True)]),
            ft.Divider(color=BORDER, height=1),
        ])

    def _main_view(self):
        view = self.current_view
        if view == 'list':
            return task_list_view(job=self.job, on_changed=self.bump)
        if view == 'board':
            return TaskBoard(self.job, self.bump).build()
        if view == 'gantt':
            return TaskGantt(self.job, self.refresh_flag, self.bump).build()
        if view == 'topology':
            return TaskTopo(self.job).build()
        if view.startswith('plugin:'):
            plugin = find_for_type(self.job.type)
            return build_view(plugin, self.job) if plugin else ft.Container()
        return task_list_view(job=self.job)
