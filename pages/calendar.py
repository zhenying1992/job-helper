"""
任务日历（月视图）

- 固定 6 行 × 7 列，从「当月 1 号所在周的周一」开始铺 42 天
- 任务条按自然周切段，跨周处用 ‹ › 标记，首尾段才带圆角
- 同一周内时间重叠的任务自动往下排泳道，超过 3 条折叠为 +N
- 图例按工作流顺序：未开始→执行中→阻塞中→已完成（见 LEGEND_ORDER，不含逾期）
- 历史状态名（待开始/进行中等）在读取时由 Status.normalize 归一化，图例只显示现行枚举
- 列宽随窗口自适应，留 176 的最小宽度；更窄则整体横向滚动
- 星期头与网格放在同一个滚动容器里，拖动时一起移动
- 日期标签绘制在任务条之上，永不被遮挡
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

import flet as ft

from common.decorate import catch_error
from constant import (
    BG_PANEL, BORDER_RADIUS, COLOR_DANGER, COLOR_PRIMARY, COLOR_TEXT, OVERDUE, Status,
)
from data.model import Task
from data.service import TaskService
from theme import (
    BG_CELL, BG_CELL_DIM, BG_TODAY, BORDER_SOFT as LINE, MUTED as TXT_DAY,
    TEXT_WEEKEND as TXT_DAY_WEEKEND, TEXT_DIM as TXT_DAY_DIM,
    BG_CANVAS, BORDER_STRONG, ACCENT, SLATE, TEXT_SUBTLE,
    FS_XS, FS_SM, FS_MD,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------- 版式常量
MIN_COL_W = 176      # 单格最小宽（窗口再窄就横向滚动）
ROW_H = 112          # 单格高
BAR_H = 18           # 任务条高度
BAR_GAP = 4          # 条与条的垂直间距
BAR_TOP = 30         # 第一条距格子顶部，给日期留安全区
MAX_LANES = 3        # 每格最多展示几条
BAR_HANDLE_W = 12    # 条两端拖拽热区宽度

GRID_H = ROW_H * 6

# 日历容器左右内边距之和。若外层还有 padding，请把这里调大。
OUTER_PAD = 40

# 窗口宽度未知时的兜底宽度
DEFAULT_WIN_W = 1280

# 图例按工作流顺序展示：未开始→执行中→阻塞中→已完成（不展示派生状态「逾期」）
LEGEND_ORDER = [Status.NOT_START, Status.EXECUTING, Status.BLOCKED, Status.FINISHED]
LEGEND_NAMES = LEGEND_ORDER

# 未完成且已过截止时间的任务，是否自动按「逾期」渲染。
# 打开后，历史上所有过期未完成的任务都会变红；按需开启。
AUTO_OVERDUE = False

# 拖动端点时按「目标日期范围」实时重切段（含跨行/跨周），渲染层每帧重建预览段。
# 几何放在 use_state 里而非控件属性上，跨帧 key 稳定 → pan 手势不会断。


# ---------------------------------------------------------------- 数据计算
@dataclass
class _Seg:
    """一条任务在某一周内的一段连续横条。

    普通段由任务真实日期切分而来；preview=True 的段是拖动端点时按目标
    日期范围临时生成的预览段，只用于渲染，不落库。
    """
    task: Task
    row: int
    c0: int
    c1: int
    lane: int = 0
    first: bool = True       # 整条（或本次预览范围）的首段
    last: bool = True        # 整条（或本次预览范围）的末段
    multi: bool = False      # 是否跨了多段
    preview: bool = False    # 拖动预览段（非真实数据）


def _task_key(task) -> int:
    """任务稳定标识：优先数据库 id，兜底对象地址。"""
    return getattr(task, "id", id(task))


def _as_date(v) -> Optional[date]:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return None


def _shift_month(ym: tuple[int, int], delta: int) -> tuple[int, int]:
    y, m = ym
    m += delta
    while m < 1:
        m += 12
        y -= 1
    while m > 12:
        m -= 12
        y += 1
    return (y, m)


def _month_window(year: int, month: int) -> list[date]:
    """当月 1 号所在周的周一起，连续 42 天。"""
    first = date(year, month, 1)
    origin = first - timedelta(days=first.weekday())
    return [origin + timedelta(days=i) for i in range(42)]


def _status_of(task: Task) -> str:
    """归一化任务状态；逾期开启时对过期未完成任务派生 OVERDUE。"""
    name = Status.normalize(getattr(task, "status", "") or "")
    if not AUTO_OVERDUE or not name or name == Status.FINISHED:
        return name
    end = _as_date(getattr(task, "end_time", None))
    if end is not None and end < date.today():
        return OVERDUE
    return name


def _color_of(status: str) -> str:
    """状态名 → 颜色，与全局枚举保持一致。"""
    if status == OVERDUE:
        return COLOR_DANGER
    return Status.color(status)


def _build_segments(tasks: list[Task], cells: list[date]) -> list[_Seg]:
    """把任务按自然周切段，只保留落在 42 天窗口内的部分。"""
    win_start, win_end = cells[0], cells[-1]
    segs: list[_Seg] = []

    for task in tasks:
        start = _as_date(getattr(task, "start_time", None))
        end = _as_date(getattr(task, "end_time", None))
        if start is None or end is None:
            continue
        if end < start:
            start, end = end, start
        if end < win_start or start > win_end:
            continue

        start = max(start, win_start)
        end = min(end, win_end)

        cur: Optional[_Seg] = None
        day = start
        while day <= end:
            n = (day - win_start).days
            row, col = divmod(n, 7)
            if cur is None or cur.row != row:
                cur = _Seg(task=task, row=row, c0=col, c1=col)
                segs.append(cur)
            else:
                cur.c1 = col
            day += timedelta(days=1)

    # 首末段标记（首段左侧圆角，末段右侧圆角，中间段两端平口）
    groups: dict[int, list[_Seg]] = {}
    for seg in segs:
        groups.setdefault(getattr(seg.task, "id", id(seg.task)), []).append(seg)
    for lst in groups.values():
        lst.sort(key=lambda s: (s.row, s.c0))
        for i, seg in enumerate(lst):
            seg.first = i == 0
            seg.last = i == len(lst) - 1
            seg.multi = len(lst) > 1

    return segs


def _assign_lanes(segs: list[_Seg], focus_id=None) -> None:
    """任务级全局泳道分配：一条任务跨周所有段共用同一条泳道。

    旧算法按 row 逐行贪心，导致同一任务在 11.12 和 11.13 落到不同泳道，
    hover 时无法把折叠的那一段和其余段拼成一条连续的横条。这里改为以
    「任务」为粒度做一次图着色：两任务只要在任意一天有交集就占用不同泳道，
    因此同一任务天然在所有周、所有天保持同一 lane。

    focus_id 指定的任务最先分配，稳定拿到 lane 0（可见区），原来占 lane 0
    的任务被顺延到后面的泳道，超出 MAX_LANES 的就被折叠进「更多」——这正是
    「把关注的挪出来、把别的挪进去」的语义。
    """
    by_task: dict[int, list[_Seg]] = {}
    for seg in segs:
        by_task.setdefault(_task_key(seg.task), []).append(seg)
    if not by_task:
        return

    # 每个任务占用的 (row, col) 格子集合
    cells_of: dict[int, set[tuple[int, int]]] = {}
    for tk, task_segs in by_task.items():
        occupied = set()
        for seg in task_segs:
            for col in range(seg.c0, seg.c1 + 1):
                occupied.add((seg.row, col))
        cells_of[tk] = occupied

    def order(tk: int):
        first_cell = min(cells_of[tk])
        # 关注任务最优先；其次按最早出现位置；再按跨度长的优先（长任务稳定靠前）
        focus_rank = 0 if (focus_id is not None and tk == focus_id) else 1
        return (focus_rank, first_cell, -len(cells_of[tk]), tk)

    lane_cells: dict[int, set[tuple[int, int]]] = {}
    for tk in sorted(by_task, key=order):
        mine = cells_of[tk]
        lane = 0
        while lane in lane_cells and bool(mine & lane_cells[lane]):
            lane += 1
        lane_cells.setdefault(lane, set()).update(mine)
        for seg in by_task[tk]:
            seg.lane = lane


def _range_segs(task, start: date, end: date, cells: list[date], lane: int) -> list[_Seg]:
    """按任意日期范围生成预览段（拖动端点时的实时几何）。

    与 _build_segments 共用「按自然周切段」的规则，但只需要一个任务的日期范围，
    不查库、不碰真实 task 的日期，因此每帧重建成本极低。
    """
    if start is None or end is None:
        return []
    if end < start:
        start, end = end, start
    win_start, win_end = cells[0], cells[-1]
    if end < win_start or start > win_end:
        return []
    start = max(start, win_start)
    end = min(end, win_end)

    raw: list[list[int]] = []
    day = start
    while day <= end:
        n = (day - win_start).days
        row, col = divmod(n, 7)
        if raw and raw[-1][0] == row:
            raw[-1][2] = col
        else:
            raw.append([row, col, col])
        day += timedelta(days=1)

    out: list[_Seg] = []
    for i, (row, c0, c1) in enumerate(raw):
        out.append(_Seg(
            task=task, row=row, c0=c0, c1=c1, lane=lane,
            first=i == 0, last=i == len(raw) - 1,
            multi=len(raw) > 1, preview=True,
        ))
    return out


def _blend(fg: str, bg: str = BG_CELL, alpha: float = 0.16) -> str:
    """把状态色以 alpha 混到格子底色上，得到不透明的条背景。"""
    f = fg.lstrip("#")
    b = bg.lstrip("#")
    fr, fg_, fb = int(f[0:2], 16), int(f[2:4], 16), int(f[4:6], 16)
    br, bg_, bb = int(b[0:2], 16), int(b[2:4], 16), int(b[4:6], 16)
    return "#{:02x}{:02x}{:02x}".format(
        int(fr * alpha + br * (1 - alpha)),
        int(fg_ * alpha + bg_ * (1 - alpha)),
        int(fb * alpha + bb * (1 - alpha)),
    )


# 横条内可塞元信息的最小宽度：1 天格约 170px，足够放「@负责人 · 3h」
META_MIN_W = 108
TAG_MIN_W = 280


def _bar_meta(task, bar_width: float) -> str:
    """按横条宽度决定要附加的元信息；放不下的留给 tooltip。"""
    if bar_width < META_MIN_W:
        return ""
    parts = []
    assignee = (getattr(task, "assignee", "") or "").strip()
    hours = getattr(task, "estimate_hours", 0) or 0
    tags = getattr(task, "tags", None) or []
    if assignee:
        parts.append(f"@{assignee}")
    if hours:
        parts.append(f"{hours}h")
    if tags and bar_width >= TAG_MIN_W:
        parts.append(f"#{tags[0]}")
    return " · ".join(parts)


def _bar_tooltip(task, label: str) -> str:
    """hover 时展示的完整信息：名称 + 负责人/工时/标签/描述。"""
    lines = [label.strip("‹ › ").strip() or "（未命名任务）"]
    assignee = (getattr(task, "assignee", "") or "").strip()
    hours = getattr(task, "estimate_hours", 0) or 0
    tags = getattr(task, "tags", None) or []
    desc = (getattr(task, "description", "") or "").strip()
    bits = []
    if assignee:
        bits.append(f"负责人 {assignee}")
    if hours:
        bits.append(f"工时 {hours}h")
    if bits:
        lines.append(" · ".join(bits))
    if tags:
        lines.append("标签 " + "、".join(tags))
    if desc:
        lines.append(desc)
    return "\n".join(lines)


# ---------------------------------------------------------------- 视图
@ft.component
@catch_error
def calendar_view():
    today = date.today()
    ym, set_ym = ft.use_state((today.year, today.month))
    year, month = ym

    # 任务被编辑后自增，触发重渲染并重新查库
    rev, set_rev = ft.use_state(0)

    # 手势累积态放 use_ref（改 .current 不触发重渲染）。
    drag_ref = ft.use_ref(None)

    # 拖动预览几何放 use_state：每帧换一个新 dict → 触发声明式重渲染。
    # 关键（踩坑）：重渲染时所有真实段的 key 保持不变，正在被拖的把手控件始终
    # 留在树里；预览条是「额外追加」的独立控件（pv- 前缀），绝不替换真实段。
    # 原先「摘掉真实段、用新 key 的预览段顶替」会把正在拖的 GestureDetector
    # 卸载 → 客户端 pan 的 control id 失效 → 后续 pan_update 丢失（不实时+报错）。
    drag, set_drag = ft.use_state(None)

    # 悬停高亮：当前鼠标所在任务的 id（同任务跨周多段一起高亮）。
    # hover 只改这一项（不进 cache_key），所以只刷颜色、绝不重排泳道 → 不抖动。
    hover_key, set_hover = ft.use_state(None)

    # 关注任务：只在「点击横条」或「点/悬浮更多清单项」时改。
    # 绝不在横条 on_enter 里改——那会重排泳道→条移动到光标下→再触发 enter→
    # 无限循环抖动。点击是一次性动作，弹窗会盖住光标，不会形成反馈环。
    focus_key, set_focus = ft.use_state(None)

    # 拖动每帧都重渲染，query + 分组 + 排泳道没必要每帧重算，缓存住。
    calc_ref = ft.use_ref(None)

    # 图例开关：被关掉的状态不参与绘制，也不计入统计
    hidden, set_hidden = ft.use_state(frozenset())

    def toggle_status(name: str):
        set_hidden(lambda cur: cur - {name} if name in cur else cur | {name})

    # 拖动提示浮层挂到 page.overlay：它是回调里新建的控件，没有 _frozen，
    # 可以直接改 left/top 并 update()，完全不触发日历重渲染 —— 手势不会被打断。
    def _overlay_add(c: ft.Control):
        try:
            page = ft.context.page
            page.overlay.append(c)
            page.update()
        except Exception:
            pass

    def _overlay_remove(c: ft.Control):
        try:
            page = ft.context.page
            if c in page.overlay:
                page.overlay.remove(c)
                page.update()
        except Exception:
            pass

    # ---- 宽度自适应：窗口变宽时按比例加宽列，变窄时保底横向滚动 ----
    # 初始就取当前窗口宽度，避免首帧用默认值 1280 导致宽窗口右侧留白。
    def _current_width() -> int:
        try:
            page = ft.context.page
            return int(page.window.width or 0)
        except Exception:
            return 0

    win_w, set_win_w = ft.use_state(_current_width())

    def _bind_resize():
        try:
            page = ft.context.page
            # PageResizeEvent.width 才是新宽度；page.width 在 1.0.3 不存在，
            # 之前读它抛异常被吞，win_w 一直为 0，网格按默认 1280 算→右侧留白。
            page.on_resize = lambda e: set_win_w(int(e.width or 0))
            w = _current_width()
            if w and w != win_w:
                set_win_w(w)
        except Exception:
            pass

    ft.use_effect(_bind_resize, [])

    col_w = max(MIN_COL_W, ((win_w or DEFAULT_WIN_W) - OUTER_PAD) // 7)
    grid_w = col_w * 7

    # 拖动期间 rev / 月份 / 筛选 / 关注任务不变 → 计算只做一次
    cache_key = (year, month, rev, hidden, focus_key)
    calc = calc_ref.current
    if calc is not None and calc[0] == cache_key:
        tasks, cells, segs, month_count = calc[1:]
    else:
        tasks = TaskService.filter()
        cells = _month_window(year, month)

        # 被关掉的状态先剔掉，再分组排泳道
        visible = [t for t in tasks if _status_of(t) not in hidden]
        segs = _build_segments(visible, cells)
        _assign_lanes(segs, focus_key)

        # 本月有交集的任务数（跟随筛选）
        month_first = date(year, month, 1)
        month_last = date(year + (month == 12), (month % 12) + 1, 1) - timedelta(days=1)
        month_count = 0
        for t in visible:
            s = _as_date(getattr(t, "start_time", None))
            e = _as_date(getattr(t, "end_time", None))
            if s and e and not (e < month_first or s > month_last):
                month_count += 1

        calc_ref.current = (cache_key, tasks, cells, segs, month_count)

    def goto(delta: int):
        set_ym(lambda cur: _shift_month(cur, delta))

    def goto_today(e=None):
        set_ym((today.year, today.month))

    def open_task(task: Task):
        """点条 → 置顶该任务（放出来的横条）并弹出编辑窗，保存后重查库刷新。"""
        # 点击即设为关注任务：被折叠进「更多」的任务点开清单项后也会被放出来
        tk = getattr(task, "id", id(task))
        set_focus(tk)
        try:
            from pages.task import UpdateTaskDialog

            ft.context.page.show_dialog(
                UpdateTaskDialog(task=task, on_saved=lambda: set_rev(lambda v: v + 1))
            )
        except Exception:
            # 不想静默失败：导入路径或 dialog 签名不对时能立刻看到
            logger.exception("打开任务编辑失败")

    def _focus_from_list(task: Task):
        """在「更多」清单里 hover/点击：高亮 + 置顶，把折叠任务放出来。

        清单浮层不在网格里，置顶重排不会把别的条移到光标下，无抖动反馈环。
        """
        tk = _task_key(task)
        if hover_key != tk:
            set_hover(tk)
        if focus_key != tk:
            set_focus(tk)

    def open_cell_list(tasks: list[Task], e):
        """点 +N 更多 → 在鼠标位置弹一张清单卡，列出被折叠的任务，逐条可点进编辑。"""
        by_id: dict = {}
        for t in tasks:
            by_id.setdefault(getattr(t, "id", id(t)), t)
        dedup = list(by_id.values())

        def close(_=None):
            _overlay_remove(card)

        rows = []
        for t in dedup:
            status = _status_of(t)
            c = _color_of(status)
            name = (getattr(t, "name", "") or "").strip()
            extra = _bar_meta(t, 1000)  # 清单卡里塞全量元信息
            rows.append(
                ft.GestureDetector(
                    on_tap=lambda ev, task=t: (open_task(task), close()),
                    on_hover=lambda ev, task=t: _focus_from_list(task),
                    mouse_cursor=ft.MouseCursor.CLICK,
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Container(width=8, height=8, bgcolor=c, border_radius=2),
                                    ft.Text(
                                        name,
                                        size=12,
                                        color=COLOR_TEXT,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                        tooltip=_bar_tooltip(t, name),
                                    ),
                                ],
                                spacing=8,
                            ),
                            ft.Text(extra, size=FS_XS, color=SLATE) if extra else ft.Container(height=0),
                        ],
                        spacing=2,
                        tight=True,
                    ),
                )
            )

        card_w = 260
        gx = e.global_position.x
        gy = e.global_position.y
        left = min(max(0.0, gx), max(0.0, (win_w or DEFAULT_WIN_W) - card_w - 16))
        top = min(max(0.0, gy), GRID_H - 120)

        card = ft.Container(
            left=left,
            top=top,
            width=card_w,
            bgcolor=BG_CANVAS,
            border=ft.Border(
                top=ft.BorderSide(1, BORDER_STRONG),
                right=ft.BorderSide(1, BORDER_STRONG),
                bottom=ft.BorderSide(1, BORDER_STRONG),
                left=ft.BorderSide(1, BORDER_STRONG),
            ),
            border_radius=8,
            padding=ft.Padding(left=12, top=10, right=12, bottom=10),
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(f"当日 {len(dedup)} 个任务", size=FS_SM, color=SLATE),
                            ft.Container(expand=True),
                            ft.TextButton("×", on_click=close, width=24, height=24),
                        ],
                        spacing=0,
                    ),
                    ft.Column(rows, spacing=8, tight=True),
                ],
                spacing=10,
                tight=True,
            ),
        )
        _overlay_add(card)

    # ---------- 背景格子（只负责底色和描边） ----------
    cell_controls: list[ft.Control] = []
    for i, day in enumerate(cells):
        row, col = divmod(i, 7)
        is_dim = (day.year, day.month) != (year, month)
        is_today = day == today
        border_color = COLOR_PRIMARY if is_today else LINE

        cell_controls.append(
            ft.Container(
                key=f"cell-{i}",
                left=col * col_w,
                top=row * ROW_H,
                width=col_w,
                height=ROW_H,
                bgcolor=BG_TODAY if is_today else (BG_CELL_DIM if is_dim else BG_CELL),
                border=ft.Border(
                    top=ft.BorderSide(1, border_color),
                    right=ft.BorderSide(1, border_color),
                    bottom=ft.BorderSide(1, border_color),
                    left=ft.BorderSide(1, border_color),
                ),
            )
        )

    # ---------- 任务条 + 两端拖拽把手 ----------
    bar_controls: list[ft.Control] = []
    overflow: dict[tuple[int, int], list[Task]] = {}

    def commit_resize(task: Task, side: str, days: int):
        """把拖动结果写回任务：side='start' 改开始日，'end' 改结束日。"""
        if days:
            try:
                s = _as_date(getattr(task, "start_time", None))
                e = _as_date(getattr(task, "end_time", None))
                if s and e:
                    if side == "start":
                        ns = min(s + timedelta(days=days), e)      # 不能越过结束日
                        task.start_time = task.start_time.replace(
                            year=ns.year, month=ns.month, day=ns.day
                        )
                    else:
                        ne = max(e + timedelta(days=days), s)      # 不能早于开始日
                        task.end_time = task.end_time.replace(
                            year=ne.year, month=ne.month, day=ne.day
                        )
                    task.save()
            except Exception:
                logger.exception("调整任务日期失败")

    def make_handle(
        seg: _Seg,
        side: str,
        bar_key: str,
        b_left: float,
        b_width: float,
        b_top: float,
        color: str,
    ):
        """两端拖拽热区：pan 期间用声明式状态画实时预览条（跨行多段）。

        踩坑要点：本把手控件在整个手势期间必须始终留在渲染树里、key 不变。
        pan 回调只 set_drag（声明式重渲染），渲染层用预览条「额外叠加」而非
        「顶替」真实段——真实段与把手的 key 恒定，Flet 按 key 复用同一控件，
        control id 不变 → 客户端 pan 手势不中断。切勿在 pan 里 page.update()。
        """

        def _tip_text(days: int) -> str:
            base = _as_date(seg.task.start_time if side == "start" else seg.task.end_time)
            if base is None:
                return ""
            target = base + timedelta(days=days)
            s = _as_date(seg.task.start_time)
            e = _as_date(seg.task.end_time)
            if s and e:
                target = min(target, e) if side == "start" else max(target, s)
            prefix = "开始" if side == "start" else "结束"
            return f"{prefix} → {target.month} 月 {target.day} 日"

        def on_start(e):
            s0 = _as_date(seg.task.start_time)
            e0 = _as_date(seg.task.end_time)
            span = (e0 - s0).days if s0 and e0 else 0
            drag_ref.current = {
                "task": seg.task,
                "side": side,
                "s0": s0,
                "e0": e0,
                "span": span,
                "hx0": b_left if side == "start" else b_left + b_width - BAR_HANDLE_W,
                "lane": seg.lane,
                "lane_offset": b_top - seg.row * ROW_H,
                "orig_row": seg.row,
                "orig_col": seg.c0 if side == "start" else seg.c1,
                "g0": e.global_position,
                "dx": 0.0,
                "dy": 0.0,
                "days": 0,
                "preview_on": False,
            }

        def on_update(e):
            st = drag_ref.current
            if not st:
                return
            g = e.global_position
            st["dx"] = g.x - st["g0"].x
            st["dy"] = g.y - st["g0"].y

            new_col = max(0, min(6, int((st["hx0"] + st["dx"]) // col_w)))
            new_row = st["orig_row"] + int((st["lane_offset"] + st["dy"]) // ROW_H)
            new_row = max(0, min(5, new_row))
            days = (new_row * 7 + new_col) - (st["orig_row"] * 7 + st["orig_col"])
            if side == "start":
                days = min(days, st["span"])
            else:
                days = max(days, -st["span"])
            st["days"] = days

            if days == 0 and abs(st["dx"]) < 6:
                return
            st["preview_on"] = True

            s0, e0 = st["s0"], st["e0"]
            if s0 is None or e0 is None:
                return
            if side == "start":
                ns, ne = min(s0 + timedelta(days=days), e0), e0
            else:
                ns, ne = s0, max(e0 + timedelta(days=days), s0)

            # 只更新声明式状态；预览段作为「额外控件」进渲染树，真实段/把手不动
            set_drag({
                "tk": _task_key(st["task"]),
                "task": st["task"],
                "side": side,
                "segs": _range_segs(st["task"], ns, ne, cells, st["lane"]),
                "lane": st["lane"],
                "days": days,
                "tip_text": _tip_text(days),
                "gx": g.x,
                "gy": g.y,
            })

        def on_end(e):
            st = drag_ref.current
            drag_ref.current = None
            days = st["days"] if st else 0
            set_drag(None)          # 清掉预览，渲染层只剩真实几何
            commit_resize(seg.task, side, days)
            set_rev(lambda v: v + 1)

        return ft.GestureDetector(
            key=f"{bar_key}-{'l' if side == 'start' else 'r'}",
            left=(b_left if side == "start" else b_left + b_width - BAR_HANDLE_W),
            top=b_top,
            width=BAR_HANDLE_W,
            height=BAR_H,
            mouse_cursor=ft.MouseCursor.RESIZE_LEFT_RIGHT,
            drag_interval=16,
            on_pan_start=on_start,
            on_pan_update=on_update,
            on_pan_end=on_end,
            content=ft.Container(
                content=ft.Container(width=2, height=8, bgcolor=color, border_radius=1),
                alignment=ft.Alignment.CENTER,
            ),
        )

    # 渲染真实段。拖动预览走 page.overlay，完全不碰这里的控件树 —— 被拖的把手
    # 始终留在树里、key 稳定，客户端 pan 手势不会因重渲染而中断。
    for seg in segs:
        tk = _task_key(seg.task)
        status = _status_of(seg.task)
        color = _color_of(status)

        if seg.lane >= MAX_LANES:
            for col in range(seg.c0, seg.c1 + 1):
                overflow.setdefault((seg.row, col), []).append(seg.task)
            continue

        label = (getattr(seg.task, "name", "") or "").strip()
        if not seg.first:
            label = "‹ " + label
        if not seg.last:
            label = label + " ›"

        bar_key = f"bar-{tk}-{seg.row}"
        b_left = seg.c0 * col_w + 3
        b_width = (seg.c1 - seg.c0 + 1) * col_w - 6
        b_top = seg.row * ROW_H + BAR_TOP + seg.lane * (BAR_H + BAR_GAP)

        is_hover = hover_key == tk
        meta = _bar_meta(seg.task, b_width)
        alpha = 0.30 if is_hover else 0.16

        body = ft.Container(
            bgcolor=_blend(color, BG_CELL, alpha),
            border_radius=ft.BorderRadius(
                top_left=4 if seg.first else 0,
                bottom_left=4 if seg.first else 0,
                top_right=4 if seg.last else 0,
                bottom_right=4 if seg.last else 0,
            ),
            border=ft.Border(left=ft.BorderSide(3, color)),
            padding=ft.Padding(left=10, top=0, right=10, bottom=0),
            alignment=ft.Alignment.CENTER_LEFT,
            on_click=lambda e, t=seg.task: open_task(t),
            content=ft.Row(
                controls=[
                    ft.Text(
                        label,
                        size=11,
                        color=color,
                        expand=True,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        tooltip=_bar_tooltip(seg.task, label),
                    ),
                    ft.Text(meta, size=FS_XS, color=SLATE, max_lines=1)
                    if meta else ft.Container(width=0),
                ],
                spacing=6,
            ),
        )

        def _hover_task(t):
            # 只高亮、不重排：hover 不进 cache_key，绝不改泳道布局。
            # 置顶/放出来只在点击(open_task)或点「更多」清单时发生，避免抖动循环。
            if hover_key != t:
                set_hover(t)

        bar_controls.append(
            ft.GestureDetector(
                key=bar_key,
                left=b_left,
                top=b_top,
                width=b_width,
                height=BAR_H,
                on_enter=lambda e, t=tk: _hover_task(t),
                on_exit=lambda e: set_hover(None),
                mouse_cursor=ft.MouseCursor.CLICK,
                content=body,
            )
        )
        if seg.first:
            bar_controls.append(
                make_handle(seg, "start", bar_key, b_left, b_width, b_top, color)
            )
        if seg.last:
            bar_controls.append(
                make_handle(seg, "end", bar_key, b_left, b_width, b_top, color)
            )

    # ---------- 拖动预览条（额外叠加，不顶替真实段） ----------
    # 真实段与把手已在上面渲染且 key 固定；这里只追加 pv- 前缀的展示条。
    # 每帧重渲染时真实控件按 key 复用、control id 不变 → pan 手势不中断。
    if drag and drag.get("segs"):
        pv_color = _color_of(_status_of(drag["task"]))
        for i, ps in enumerate(drag["segs"]):
            pv_label = (getattr(drag["task"], "name", "") or "").strip()
            if not ps.first:
                pv_label = "‹ " + pv_label
            if not ps.last:
                pv_label = pv_label + " ›"
            bar_controls.append(
                ft.Container(
                    key=f"pv-{i}-{ps.row}",
                    left=ps.c0 * col_w + 3,
                    top=ps.row * ROW_H + BAR_TOP + ps.lane * (BAR_H + BAR_GAP),
                    width=(ps.c1 - ps.c0 + 1) * col_w - 6,
                    height=BAR_H,
                    bgcolor=_blend(pv_color, BG_CELL, 0.46),
                    border=ft.Border(
                        left=ft.BorderSide(3, ACCENT),
                        top=ft.BorderSide(1, pv_color),
                        right=ft.BorderSide(1, pv_color),
                        bottom=ft.BorderSide(1, pv_color),
                    ),
                    border_radius=ft.BorderRadius(
                        top_left=4 if ps.first else 0, bottom_left=4 if ps.first else 0,
                        top_right=4 if ps.last else 0, bottom_right=4 if ps.last else 0,
                    ),
                    padding=ft.Padding(left=10, top=0, right=8, bottom=0),
                    alignment=ft.Alignment.CENTER_LEFT,
                    content=ft.Text(
                        pv_label, size=11, color=pv_color, max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                )
            )
        # 日期提示浮层：用网格局部坐标（跟随被拖端点所在的格），避免全局↔局部换算误差
        tip_seg = drag["segs"][0] if drag["side"] == "start" else drag["segs"][-1]
        tip_col = tip_seg.c0 if drag["side"] == "start" else tip_seg.c1
        tip_x = min(max(0.0, tip_col * col_w + 6), grid_w - 120)
        tip_y = max(0.0, tip_seg.row * ROW_H + BAR_TOP - 22)
        bar_controls.append(
            ft.Container(
                key="pv-tip",
                left=tip_x,
                top=tip_y,
                bgcolor=BG_CANVAS,
                border=ft.Border(
                    top=ft.BorderSide(1, ACCENT), right=ft.BorderSide(1, ACCENT),
                    bottom=ft.BorderSide(1, ACCENT), left=ft.BorderSide(1, ACCENT),
                ),
                border_radius=6,
                padding=ft.Padding(left=10, top=5, right=10, bottom=5),
                content=ft.Text(
                    drag["tip_text"], size=FS_SM, color=ACCENT,
                    weight=ft.FontWeight.W_500,
                ),
            )
        )

    for (row, col), tasks in overflow.items():
        bar_controls.append(
            ft.GestureDetector(
                key=f"ov-{row}-{col}",
                left=col * col_w + 9,
                top=row * ROW_H + BAR_TOP + MAX_LANES * (BAR_H + BAR_GAP),
                mouse_cursor=ft.MouseCursor.CLICK,
                on_tap=lambda e, r=row, c=col, tl=tasks: open_cell_list(tl, e),
                content=ft.Container(
                    content=ft.Text(f"+{len(tasks)} 更多", size=FS_XS, color=SLATE),
                ),
            )
        )

    # ---------- 日期标签（放在 Stack 最后，永远压在任务条之上） ----------
    label_controls: list[ft.Control] = []
    for i, day in enumerate(cells):
        row, col = divmod(i, 7)
        is_dim = (day.year, day.month) != (year, month)
        is_today = day == today
        is_weekend = col >= 5

        num_color = (
            COLOR_PRIMARY if is_today
            else TXT_DAY_DIM if is_dim
            else TXT_DAY_WEEKEND if is_weekend
            else TXT_DAY
        )

        label_controls.append(
            ft.Container(
                key=f"lab-{i}",
                left=col * col_w + 9,
                top=row * ROW_H + 6,
                width=col_w - 18,
                height=18,
                content=ft.Row(
                    controls=[
                        ft.Text(
                            str(day.day),
                            size=13,
                            color=num_color,
                            weight=ft.FontWeight.BOLD if is_today else None,
                        ),
                        ft.Container(expand=True),
                        ft.Text("今天", size=10, color=COLOR_PRIMARY)
                        if is_today else ft.Container(),
                    ],
                    spacing=0,
                ),
            )
        )

    grid = ft.Stack(
        width=grid_w,
        height=GRID_H,
        controls=cell_controls + bar_controls + label_controls,
    )

    # ---------- 顶部：标题在左、月份控件居中、统计在右 ----------
    header = ft.Container(
        height=64,
        border=ft.Border(bottom=ft.BorderSide(1, LINE)),
        content=ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("任务日历", size=16, weight=ft.FontWeight.BOLD, color=COLOR_PRIMARY),
                        ft.Text("月度视图", size=FS_MD, color=TEXT_SUBTLE),
                    ],
                    spacing=8,
                ),
                ft.Container(expand=True),
                ft.Row(
                    controls=[
                        ft.IconButton(
                            ft.Icons.CHEVRON_LEFT,
                            icon_color=TXT_DAY,
                            icon_size=18,
                            on_click=lambda e: goto(-1),
                        ),
                        ft.Container(
                            ft.Text(
                                f"{year} 年 {month} 月",
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                color=COLOR_TEXT,
                            ),
                            width=132,
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.IconButton(
                            ft.Icons.CHEVRON_RIGHT,
                            icon_color=TXT_DAY,
                            icon_size=18,
                            on_click=lambda e: goto(1),
                        ),
                        ft.Container(width=8),
                        ft.TextButton("今天", on_click=goto_today),
                    ],
                    spacing=2,
                ),
                ft.Container(expand=True),
                ft.Row(
                    controls=[
                        ft.Container(width=7, height=7, bgcolor=COLOR_PRIMARY, border_radius=4),
                        ft.Text(f"本月 {month_count} 个任务", size=FS_MD, color=TXT_DAY),
                    ],
                    spacing=6,
                ),
            ],
            spacing=0,
        ),
    )

    # ---------- 星期头 + 网格（同一个横向滚动容器，拖动时一起走） ----------
    weekhead = ft.Row(
        controls=[
            ft.Container(
                ft.Text(w, size=FS_MD, color=ACCENT if i >= 5 else SLATE),
                width=col_w,
                height=34,
                alignment=ft.Alignment.CENTER,
            )
            for i, w in enumerate("一二三四五六日")
        ],
        spacing=0,
    )

    calendar_area = ft.Row(
        controls=[ft.Column([weekhead, grid], spacing=0)],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    # ---------- 图例（可点击，切换该状态是否显示） ----------
    def legend_item(name: str):
        color = _color_of(name)
        on = name not in hidden
        return ft.GestureDetector(
            mouse_cursor=ft.MouseCursor.CLICK,
            on_tap=lambda e, n=name: toggle_status(n),
            content=ft.Row(
                controls=[
                    ft.Container(
                        width=14,
                        height=8,
                        bgcolor=color if on else _blend(color, BG_PANEL, 0.3),
                        border_radius=3,
                    ),
                    ft.Text(
                        name,
                        size=FS_MD,
                        color=TXT_DAY if on else TXT_DAY_DIM,
                    ),
                ],
                spacing=7,
            ),
        )

    legend = ft.Row(
        controls=[legend_item(n) for n in LEGEND_NAMES]
        + [
            ft.Container(expand=True),
            ft.Text(
                "点击图例筛选状态 · 跨周任务按周断开，首尾带 ‹ › 标记",
                size=FS_SM,
                color=TEXT_SUBTLE,
            ),
        ],
        spacing=24,
        height=44,
    )

    return ft.Container(
        bgcolor=BG_PANEL,
        border_radius=BORDER_RADIUS,
        padding=ft.Padding(left=20, top=8, right=20, bottom=12),
        expand=True,
        content=ft.Column(
            controls=[
                header,
                calendar_area,
                legend,
            ],
            spacing=0,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        ),
    )
