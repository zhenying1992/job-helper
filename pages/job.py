import logging

import flet as ft
import flet_dropzone as ftd
from flet import MainAxisAlignment, TextAlign

from common.decorate import catch_error
from common.plugin_host import build_view, find_for_type
from common.util import datetime_2_date_str, list_dir
from config import get_attachment_path
from constant import (
    BG_PANEL, BORDER_RADIUS, COLOR_PRIMARY, COLOR_SUCCESS, COLOR_TEXT, COLOR_WARN,
    DATE_FMT, Priority, Status,
)
from data.model import Job
from data.service import AttachmentService, JobService
from pages.audit import open_audit, open_export
from pages.task.board import TaskBoard
from pages.task.gantt import TaskGantt
from pages.task.list import task_list_view
from pages.task.topo import TaskTopo
from theme import (
    ACCENT as ACTIVE, MUTED as INACTIVE, BG_HEADER_BAR, BORDER,
    FS_XL, FS_SM, FS_MD, FONT_MONO, BTN_TEXT, TEXT_BRIGHT, RADIUS_SM, glow,
    BG_TABLE_HEAD, ACCENT_SOFT,
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

    # 右侧面板高度 = 窗口高度 - 顶栏 / 内容区内边距 / 详情顶栏等固定开销。
    # 注意：不能用 Row 的 STRETCH 去撑满——Flet 1.0.3 下 STRETCH 会打断右侧
    # 主视图的 expand 高度链，导致整块塌陷为空（历史踩坑）。改用明确高度。
    page = ft.context.page
    panel_h = max(int(getattr(page, "height", 0) or 900) - 168, 460)

    return ft.Column([
        HeaderBar(job).build(),
        ft.Row([
            Left(job, bump).build(),
            ft.Container(width=20),
            Right(job, views, current_view, set_current_view, refresh_flag, bump,
                  panel_h).build(),
        ], expand=True, vertical_alignment=ft.CrossAxisAlignment.START),
    ], expand=True)


def _toast(message: str):
    ft.context.page.show_dialog(ft.SnackBar(ft.Text(message, color=BTN_TEXT)))


@ft.component
def JobDetails(job: Job, bump=None):
    """工作详情卡片：名称/描述/优先级可原地编辑，状态用彩色 chip 展示。

    原地编辑用一个跨渲染稳定的 dict 缓存输入值；on_change 只写缓存、不 set_state，
    避免每次按键都重建控件导致输入框失焦。点保存时才读缓存落库并 bump 上层刷新。
    """
    editing, set_editing = ft.use_state('')  # 当前正在编辑的字段名
    drafts = ft.use_state(lambda: {})[0]  # 跨渲染稳定的输入缓存

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

    # 统一行高与标签宽度，保证 label 与内容在所有行严格对齐、行距一致
    LABEL_W = 56
    ROW_H = 30

    def _label(text: str) -> ft.Control:
        return ft.Text(text, color=COLOR_TEXT, size=13, width=LABEL_W,
                       no_wrap=True)

    def _field(label: str, value: ft.Control) -> ft.Control:
        """普通字段行：固定宽标签 + 内容，行高统一。"""
        return ft.Row([
            _label(f"{label}:"), value,
        ], height=ROW_H, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=4)

    def editable(label: str, field: str):
        """展示态文本 + 编辑按钮；编辑态紧凑输入框/选择器 + 保存/取消。

        所有态都用固定宽度的标签 + 统一行高，避免行距参差和 label 换行。
        展示态文本 expand 占据剩余宽度，长文本按 ELLIPSIS 截断。
        """
        if editing == field:
            if field == 'priority':
                box = ft.Dropdown(
                    value=drafts.get(field, getattr(job, field)),
                    options=[ft.DropdownOption(key=p, text=p) for p in Priority.list()],
                    on_select=lambda e, f=field: drafts.__setitem__(f, e.control.value),
                    dense=True, text_size=12, width=76, height=34,
                    color=TEXT_BRIGHT,
                    content_padding=ft.Padding(4, 0, 4, 0),
                )
            else:
                box = ft.TextField(
                    value=drafts.get(field, getattr(job, field)),
                    on_change=lambda e, f=field: drafts.__setitem__(f, e.control.value),
                    width=118, height=34, text_size=13,
                    color=TEXT_BRIGHT, cursor_color=ACTIVE,
                    content_padding=ft.Padding(6, 4, 6, 4),
                )
            return ft.Row([
                _label(f"{label}:"),
                box,
                ft.IconButton(ft.Icons.CHECK, icon_color=COLOR_SUCCESS, icon_size=15,
                              width=24, height=ROW_H, tooltip="保存",
                              on_click=lambda e, f=field: save(f)),
                ft.IconButton(ft.Icons.CLOSE, icon_color=INACTIVE, icon_size=15,
                              width=24, height=ROW_H, tooltip="取消",
                              on_click=lambda e: set_editing('')),
            ], height=ROW_H, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=2)
        return ft.Row([
            _label(f"{label}:"),
            ft.Text(getattr(job, field) or '—', color=COLOR_TEXT, size=13,
                    max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
            ft.IconButton(ft.Icons.EDIT, icon_color=INACTIVE, icon_size=14,
                          width=24, height=ROW_H,
                          tooltip=f"编辑{label}", on_click=lambda e, f=field: start(f)),
        ], height=ROW_H, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=2)

    return ft.Container(
        width=300, bgcolor=BG_PANEL, border_radius=BORDER_RADIUS, padding=20,
        content=ft.Column([
            ft.Text("工作详情", color=COLOR_PRIMARY, size=FS_XL, weight=ft.FontWeight.BOLD),
            ft.Divider(color=BORDER, height=1),
            ft.Container(height=4),
            editable("名称", "name"),
            editable("描述", "description"),
            editable("优先级", "priority"),
            _field("开始时间", ft.Text(datetime_2_date_str(job.start_time, DATE_FMT),
                                       color=COLOR_TEXT, size=13)),
            _field("结束时间", ft.Text(datetime_2_date_str(job.end_time, DATE_FMT),
                                       color=COLOR_TEXT, size=13)),
            ft.Row([
                _label("进度:"),
                ft.Stack([
                    ft.ProgressBar(bar_height=12, width=160, value=job.progress / 100,
                                   bgcolor=BORDER,
                                   color=COLOR_SUCCESS if job.progress == 100 else COLOR_PRIMARY),
                    ft.Text(f"{job.progress}%", size=11),
                ], width=160, alignment=ft.Alignment.CENTER),
            ], height=ROW_H, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
            ft.Row([
                _label("状态:"),
                ft.Container(
                    ft.Text(job.status, color=BG_HEADER_BAR, size=12,
                            font_family=FONT_MONO, weight=ft.FontWeight.BOLD),
                    bgcolor=Status.color(job.status),
                    border_radius=RADIUS_SM,
                    padding=ft.Padding(8, 2, 8, 2),
                ),
            ], height=ROW_H, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
        ], spacing=6),
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
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
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

    # 附件列表列宽：名称占大头，大小/操作定宽，避免长文件名撑破 300px 面板
    # 面板 300 - 左右 padding 12*2 - 行内 padding 4*2 = 268 可用；留 4px 余量
    _ATT_NAME_W = 156
    _ATT_SIZE_W = 56
    _ATT_OPS_W = 52

    def _attachments(self):
        """附件区：拖拽文件真实落盘，列表实时遍历目录，支持打开与删除。

        数据源始终是 get_attachment_path() 目录的实时遍历，不经审计记录。
        """
        folder = get_attachment_path(self.job.id)

        def open_path(path):
            """用系统默认程序打开文件或目录。"""
            if not path.exists():
                _toast(f"路径不存在：{path}")
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
                logger.exception("打开失败：%s", path)
                _toast(f"无法打开：{path}")

        def on_dropped(e):
            names = AttachmentService.add_many(self.job.id, e.files)
            _toast(f"已保存 {len(names)} 个附件")
            if self.bump:
                self.bump()

        def open_file(name: str):
            open_path(folder / name)

        def del_file(name: str):
            AttachmentService.delete(self.job.id, name)
            AttachmentService.record_delete(self.job.id, name)
            if self.bump:
                self.bump()

        def open_folder(_):
            open_path(folder)

        # 表头：字体整体调小、居中对齐
        header = ft.Container(
            bgcolor=BG_TABLE_HEAD, border_radius=RADIUS_SM,
            padding=ft.Padding(4, 6, 4, 6),
            content=ft.Row([
                ft.Text("文件", size=FS_SM, color=ACCENT_SOFT, width=self._ATT_NAME_W),
                ft.Text("大小", size=FS_SM, color=ACCENT_SOFT, width=self._ATT_SIZE_W,
                        text_align=TextAlign.CENTER),
                ft.Text("操作", size=FS_SM, color=ACCENT_SOFT, width=self._ATT_OPS_W,
                        text_align=TextAlign.CENTER),
            ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        rows = []
        for file in list_dir(folder):
            name, size_h = file['name'], file['size_h']
            rows.append(ft.Container(
                padding=ft.Padding(4, 4, 4, 4),
                border=ft.Border(bottom=ft.BorderSide(1, BORDER)),
                content=ft.Row([
                    # 名称定宽 + 单行折叠，tooltip 保留全名
                    ft.Container(
                        width=self._ATT_NAME_W, tooltip=name,
                        on_click=lambda e, n=name: open_file(n),
                        content=ft.Text(name, size=FS_SM, color=TEXT_BRIGHT,
                                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ),
                    # 大小用更亮的颜色，右对齐便于读数
                    ft.Text(size_h, size=FS_SM, color=ACCENT_SOFT, width=self._ATT_SIZE_W,
                            text_align=TextAlign.CENTER, font_family=FONT_MONO),
                    # 操作：两个紧凑图标按钮，去掉默认内边距
                    ft.Container(
                        width=self._ATT_OPS_W,
                        content=ft.Row([
                            ft.IconButton(ft.Icons.OPEN_IN_NEW, icon_color=ACTIVE, icon_size=15,
                                          width=24, height=24, padding=0, tooltip="打开",
                                          on_click=lambda e, n=name: open_file(n)),
                            ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=INACTIVE, icon_size=15,
                                          width=24, height=24, padding=0, tooltip="删除",
                                          on_click=lambda e, n=name: del_file(n)),
                        ], spacing=0, alignment=MainAxisAlignment.CENTER,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ),
                ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ))

        table = ft.Column([header, *rows], spacing=0) if rows else None

        default = ft.Container(
            ft.Column([
                ft.Icon(ft.Icons.UPLOAD_FILE, size=28, color=INACTIVE),
                ft.Text("拖入文件保存为附件", color=INACTIVE, size=FS_MD),
            ], alignment=MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
            alignment=ft.Alignment.CENTER, height=90,
        )

        zone = ftd.Dropzone(
            content=table or default,
            on_dropped=on_dropped,
        )
        # 标题行：右侧文件夹按钮，打开附件所在目录
        title = ft.Row([
            ft.Text("工作附件", color=COLOR_PRIMARY, size=FS_MD, weight=ft.FontWeight.BOLD),
            ft.IconButton(ft.Icons.FOLDER_OPEN, icon_color=ACCENT_SOFT, icon_size=16,
                          width=26, height=26, padding=0, tooltip="打开附件文件夹",
                          on_click=open_folder),
        ], alignment=MainAxisAlignment.SPACE_BETWEEN,
           vertical_alignment=ft.CrossAxisAlignment.CENTER)
        return ft.Container(
            width=300, bgcolor=BG_PANEL, border_radius=BORDER_RADIUS,
            padding=12,
            content=ft.Column([
                title,
                zone,
            ], spacing=6, tight=True),
        )


class Right:
    def __init__(self, job, views, current_view, set_current_view, refresh_flag, bump, panel_h=610):
        self.job = job
        self.views = views
        self.current_view = current_view
        self.set_current_view = set_current_view
        self.refresh_flag = refresh_flag
        self.bump = bump
        self.panel_h = panel_h

    def build(self):
        # 用明确高度填满可用空间（由外层按窗口高度算好），保持已知可工作的内部
        # 高度链：外层 Column 不 expand，主视图 Container expand + 左上对齐。
        return ft.Container(
            height=self.panel_h,
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
            # 画布高度按右侧面板可用空间自适应，撑满高度（扣除 padding/切换栏/工具栏）
            return TaskTopo(self.job, max(self.panel_h - 130, 400)).build()
        if view.startswith('plugin:'):
            plugin = find_for_type(self.job.type)
            return build_view(plugin, self.job) if plugin else ft.Container()
        return task_list_view(job=self.job)
