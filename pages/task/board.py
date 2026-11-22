"""任务看板：按状态分列，卡片可跨列拖拽换状态。

- 四列按工作流顺序展示：未开始/执行中/阻塞中/已完成
- 卡片用 Draggable(group='board') 携带任务 id；整列是 DragTarget，拖到列内任意位置都能接收
- 落库后调用 bump() 触发上层重渲染，其它视图（甘特/日历）同步刷新
- 卡片双击打开编辑弹窗
"""

import flet as ft

from common.decorate import catch_error
from constant import Priority, Status
from data.model import Job
from data.service import TaskService
from pages.task import UpdateTaskDialog
from theme import (
    BG_CANVAS, BG_CARD, BORDER_SOFT as LINE, ACCENT, SLATE, MUTED, TEXT, TEXT_BRIGHT,
    RADIUS_MD, FS_BASE, FS_MD, FS_SM, FS_XL, glow, GLOW_SOFT,
)

GROUP = 'board'

# 看板展示顺序：直接复用全局工作流正序，杜绝与下拉框/图例顺序不一致
BOARD_ORDER = Status.list()


def _due_text(task) -> tuple[str, str]:
    """返回 (截止提示, 颜色)；逾期标红。"""
    from datetime import date
    end = task.end_time
    d = end.date() if hasattr(end, 'date') else end
    if task.status == Status.FINISHED:
        return f"{d}", SLATE
    if d < date.today():
        return f"逾期 {d}", Priority.color(Priority.HIGH)
    return f"{d}", MUTED


def _card(task: Job, bump) -> ft.Control:
    """一张任务卡片。"""
    due, due_color = _due_text(task)
    tags = ' '.join(f'#{t}' for t in task.tags)
    meta = [part for part in (task.assignee, tags) if part]
    return ft.Draggable(
        group=GROUP,
        data=task.id,
        content_feedback=ft.Container(
            width=180,
            padding=12,
            bgcolor=BG_CARD,
            border=ft.Border(left=ft.BorderSide(3, Status.color(task.status))),
            border_radius=RADIUS_MD,
            content=ft.Text(task.name, color=TEXT_BRIGHT, size=FS_BASE),
        ),
        content=ft.GestureDetector(
            on_double_tap=lambda e: ft.context.page.show_dialog(
                UpdateTaskDialog(task=task, on_saved=bump)
            ),
            mouse_cursor=ft.MouseCursor.GRAB,
            content=ft.Container(
                width=210,
                bgcolor=BG_CARD,
                border=ft.Border(left=ft.BorderSide(3, Status.color(task.status))),
                border_radius=RADIUS_MD,
                shadow=glow(GLOW_SOFT, blur=8),
                padding=12,
                content=ft.Column([
                    ft.Text(task.name, color=TEXT_BRIGHT, size=FS_BASE,
                            weight=ft.FontWeight.W_500, max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Row([
                        ft.Text(due, color=due_color, size=FS_SM, font_family='monospace'),
                        ft.Container(expand=True),
                        ft.Text(f"{task.estimate_hours}h" if task.estimate_hours else '',
                                color=MUTED, size=FS_SM),
                    ]),
                    ft.Text(' '.join(meta), color=MUTED, size=FS_SM, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            visible=bool(meta)),
                ], spacing=4, tight=True),
            ),
        ),
    )


def _column(status: str, tasks: list, bump) -> ft.Control:
    """一列看板：可接收拖入的任务并改为本列状态。"""
    def on_accept(e):
        # Flet 1.0：拖拽携带的数据在 e.src.data（Draggable.data），不在 e.data
        task_id = getattr(getattr(e, 'src', None), 'data', None) or e.data
        try:
            if task_id is not None:
                # 使用 TaskService.update 触发审计与进度同步
                TaskService.update(int(task_id), status=status)
                if bump:
                    bump()
        except Exception:
            import logging
            logging.getLogger(__name__).exception('看板拖拽更新状态失败')

    cards = [_card(t, bump) for t in tasks]
    # 整列都是 DragTarget：无论拖到卡片间隙还是下方空白，都能接收
    return ft.DragTarget(
        group=GROUP,
        on_accept=on_accept,
        content=ft.Container(
            width=236,
            bgcolor=BG_CANVAS,
            border=ft.Border.all(1, LINE),
            border_radius=RADIUS_MD,
            padding=10,
            content=ft.Column([
                ft.Row([
                    ft.Container(width=8, height=8, bgcolor=Status.color(status), border_radius=4),
                    ft.Text(status, color=TEXT, size=FS_BASE, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.Text(str(len(tasks)), color=ACCENT, size=FS_MD, font_family='monospace'),
                ]),
                ft.Divider(color=LINE, height=1),
                ft.Column(
                    cards if cards else [
                        ft.Container(
                            content=ft.Text("拖到这里", color=SLATE, size=FS_SM),
                            alignment=ft.Alignment.CENTER, height=80,
                        )
                    ],
                    spacing=10, scroll=ft.ScrollMode.AUTO, expand=True,
                ),
            ], spacing=8, expand=True),
        ),
    )


@ft.component
@catch_error
def TaskBoard(job: Job, bump=None):
    """看板视图：按状态分列，拖拽后由 bump 触发上层刷新。"""

    tasks = TaskService.query(job.id)  # 已过滤软删除
    by_status: dict[str, list] = {s: [] for s in BOARD_ORDER}
    for t in tasks:
        key = Status.normalize(t.status)
        if key in by_status:
            by_status[key].append(t)
    columns = [_column(s, by_status[s], bump) for s in BOARD_ORDER]
    return ft.Container(
        expand=True,
        content=ft.Column([
            ft.Text("任务看板 · 拖动卡片切换状态", color=ACCENT, size=FS_XL,
                    weight=ft.FontWeight.BOLD),
            ft.Row(columns, spacing=12, expand=True,
                   vertical_alignment=ft.CrossAxisAlignment.STRETCH),
        ], spacing=12, expand=True),
    )

