"""
任务日历（月视图）

- 固定 6 行 × 7 列，从「当月 1 号所在周的周一」开始铺 42 天
- 任务条按自然周切段，跨周处用 ‹ › 标记，首尾段才带圆角
- 同一周内时间重叠的任务自动往下排泳道，超过 3 条折叠为 +N
- 图例按工作流顺序：未开始→执行中→阻塞中→已完成→逾期（见 LEGEND_ORDER）
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

# 图例按工作流顺序展示：未开始→执行中→阻塞中→已完成，逾期作为派生状态附在最后
LEGEND_ORDER = [Status.NOT_START, Status.EXECUTING, Status.BLOCKED, Status.FINISHED]
LEGEND_NAMES = LEGEND_ORDER + [OVERDUE]

# 未完成且已过截止时间的任务，是否自动按「逾期」渲染。
# 打开后，历史上所有过期未完成的任务都会变红；按需开启。
AUTO_OVERDUE = False

# 拖动端点时，条本身是否实时跟着伸缩。
# True  = 每次 pan_update 只改「数据侧的几何」并触发重渲染，条跟着鼠标伸缩。
#         这就是拓扑页的做法（node.x += dl.x 改的是普通对象，不碰 _frozen）。
#         代价：每帧重建整棵日历（91 个控件）并做一次 diff。
# False = 日历一次都不重渲染，只在 page.overlay 里弹一个日期提示卡。
#         代价：拖动过程中条不变长，松手才跳位。
LIVE_PREVIEW = True


# ---------------------------------------------------------------- 数据计算
@dataclass
class _Seg:
    """一条任务在某一周内的一段连续横条。"""
    task: Task
    row: int
    c0: int
    c1: int
    lane: int = 0
    first: bool = True       # 整条任务的首段
    last: bool = True        # 整条任务的末段
    multi: bool = False      # 整条任务是否跨周切成了多段


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


def _assign_lanes(segs: list[_Seg]) -> None:
    """同一行内贪心找互不重叠的泳道。"""
    occupied: dict[int, list[list[tuple[int, int]]]] = {}

    for seg in sorted(segs, key=lambda s: (s.row, s.c0, -(s.c1 - s.c0))):
        lanes = occupied.setdefault(seg.row, [])
        lane = 0
        while True:
            if lane >= len(lanes):
                lanes.append([])
                break
            if all(seg.c1 < a or seg.c0 > b for a, b in lanes[lane]):
                break
            lane += 1
        lanes[lane].append((seg.c0, seg.c1))
        seg.lane = lane


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


# ---------------------------------------------------------------- 视图
@ft.component
@catch_error
def calendar_view():
    today = date.today()
    ym, set_ym = ft.use_state((today.year, today.month))
    year, month = ym

    # 任务被编辑后自增，触发重渲染并重新查库
    rev, set_rev = ft.use_state(0)

    # 拖拽过程态。用 use_ref 而不是 use_state：改 .current 不触发重渲染，
    # 只用来累积位移，不参与渲染。
    drag_ref = ft.use_ref(None)

    # 拖动几何放在「数据侧」，不写在控件上 —— 这是拓扑页能实时拖的关键：
    # node.x += dl.x 改的是普通 Python 对象，永远碰不到 _frozen。
    # 条也一样：left/width 放这里，渲染时读出来画，控件本身一个属性都不改。
    drag, set_drag = ft.use_state(None)

    # 悬停高亮：当前鼠标所在任务的 id（同任务跨周多段一起高亮）
    hover_key, set_hover = ft.use_state(None)

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
    win_w, set_win_w = ft.use_state(0)

    def _bind_resize():
        try:
            page = ft.context.page
            page.on_resize = lambda e: set_win_w(page.width)
        except Exception:
            pass

    ft.use_effect(_bind_resize, [])

    col_w = max(MIN_COL_W, ((win_w or DEFAULT_WIN_W) - OUTER_PAD) // 7)
    grid_w = col_w * 7

    # 拖动期间 rev / 月份 / 筛选不变 → 计算只做一次
    cache_key = (year, month, rev, hidden)
    calc = calc_ref.current
    if calc is not None and calc[0] == cache_key:
        tasks, cells, segs, month_count = calc[1:]
    else:
        tasks = TaskService.filter()
        cells = _month_window(year, month)

        # 被关掉的状态先剔掉，再分组排泳道
        visible = [t for t in tasks if _status_of(t) not in hidden]
        segs = _build_segments(visible, cells)
        _assign_lanes(segs)

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
        """点条 → 弹出编辑窗，保存后重查库刷新日历。"""
        try:
            from pages.task import UpdateTaskDialog

            ft.context.page.show_dialog(
                UpdateTaskDialog(task=task, on_saved=lambda: set_rev(lambda v: v + 1))
            )
        except Exception:
            # 不想静默失败：导入路径或 dialog 签名不对时能立刻看到
            logger.exception("打开任务编辑失败")

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
            rows.append(
                ft.GestureDetector(
                    on_tap=lambda ev, tk=t: (open_task(tk), close()),
                    mouse_cursor=ft.MouseCursor.CLICK,
                    content=ft.Row(
                        controls=[
                            ft.Container(width=8, height=8, bgcolor=c, border_radius=2),
                            ft.Text(
                                getattr(t, "name", "") or "",
                                size=12,
                                color=COLOR_TEXT,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                        spacing=8,
                    ),
                )
            )

        card_w = 220
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
        """
        条两端的拖拽热区：RESIZE 光标 + pan 手势。

        LIVE_PREVIEW=True 走拓扑页那套：只改数据侧几何 → 重渲染 → 条跟着伸缩。
        LIVE_PREVIEW=False 时日历完全不重渲染，只在 page.overlay 弹日期提示卡。
        """

        def _tip_text(days: int) -> str:
            base = _as_date(
                seg.task.start_time if side == "start" else seg.task.end_time
            )
            if base is None:
                return ""
            target = base + timedelta(days=days)
            # 与落库口径保持一致：开始日不越过结束日，结束日不早于开始日
            s = _as_date(seg.task.start_time)
            e = _as_date(seg.task.end_time)
            if s and e:
                target = min(target, e) if side == "start" else max(target, s)
            prefix = "开始" if side == "start" else "结束"
            return f"{prefix} → {target.month} 月 {target.day} 日"

        def on_start(e):
            hx0 = b_left if side == "start" else b_left + b_width - BAR_HANDLE_W
            s0 = _as_date(seg.task.start_time)
            e0 = _as_date(seg.task.end_time)
            span = (e0 - s0).days if s0 and e0 else 0
            drag_ref.current = {
                "task": seg.task,
                "key": bar_key,
                "side": side,
                "x0": b_left,
                "w0": b_width,
                "hx0": hx0,
                "span": span,
                "lane_offset": b_top - seg.row * ROW_H,
                "orig_row": seg.row,
                "orig_col": seg.c0 if side == "start" else seg.c1,
                "g0": e.global_position,
                "dx": 0.0,
                "dy": 0.0,
                "days": 0,
                "tip": None,
            }

        def on_update(e):
            st = drag_ref.current
            if not st:
                return
            g = e.global_position
            # local_delta 是「自起点」的累计值，不能再 +=；直接用全局位置差值
            st["dx"] = g.x - st["g0"].x
            st["dy"] = g.y - st["g0"].y

            # 把手落在哪一格 → 目标行列。floor 取整：进格即吸附；垂直一起算，支持跨行
            new_col = max(0, min(6, int((st["hx0"] + st["dx"]) // col_w)))
            new_row = st["orig_row"] + int((st["lane_offset"] + st["dy"]) // ROW_H)
            new_row = max(0, min(5, new_row))
            days = (new_row * 7 + new_col) - (st["orig_row"] * 7 + st["orig_col"])

            # 钳制：开始把手不能越过结束日，结束把手不能越过开始日
            if side == "start":
                days = min(days, st["span"])
            else:
                days = max(days, -st["span"])
            st["days"] = days

            # 跨周多段任务：单段预览表达不了整体，重渲染 diff 还容易让相邻段错位，
            # 拖动过程保持原条不动，只靠浮层提示目标日期，松手后再重新切段。
            if LIVE_PREVIEW and not seg.multi:
                right = st["x0"] + st["w0"]
                preview_top = new_row * ROW_H + st["lane_offset"]
                min_w = col_w / 2
                if side == "start":
                    nl = max(0.0, min(st["x0"] + st["dx"], right - min_w))
                    set_drag({"k": st["key"], "side": "start", "left": nl, "width": right - nl, "top": preview_top})
                else:
                    nw = max(min_w, st["w0"] + st["dx"])
                    set_drag({"k": st["key"], "side": "end", "left": st["x0"], "width": nw, "top": preview_top})
                return

            # 非实时模式：日历不动，只在浮层里给日期提示
            tip = st["tip"]
            if tip is None:
                # 位移太小当误触，先不弹，避免单击闪一下
                if abs(st["dx"]) < 6:
                    return
                tip = ft.Container(
                    left=0,
                    top=0,
                    bgcolor=BG_CANVAS,
                    border=ft.Border(
                        top=ft.BorderSide(1, ACCENT),
                        right=ft.BorderSide(1, ACCENT),
                        bottom=ft.BorderSide(1, ACCENT),
                        left=ft.BorderSide(1, ACCENT),
                    ),
                    border_radius=6,
                    padding=ft.Padding(left=10, top=5, right=10, bottom=5),
                    content=ft.Text("", size=FS_SM, color=ACCENT, weight=ft.FontWeight.W_500),
                )
                st["tip"] = tip
                _overlay_add(tip)

            try:
                tip.content.value = _tip_text(days)
                tip.left = e.global_position.x + 14
                tip.top = e.global_position.y - 34
                tip.update()
            except Exception:
                pass

        def on_end(e):
            st = drag_ref.current
            drag_ref.current = None
            days = st["days"] if st else 0
            if st and st["tip"] is not None:
                _overlay_remove(st["tip"])
            set_drag(None)          # 清掉预览，渲染层回到真实几何
            commit_resize(seg.task, side, days)
            set_rev(lambda v: v + 1)

        h_left = b_left if side == "start" else b_left + b_width - BAR_HANDLE_W

        return ft.GestureDetector(
            key=f"{bar_key}-{'l' if side == 'start' else 'r'}",
            left=h_left,
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

    for seg in segs:
        if seg.lane >= MAX_LANES:
            for col in range(seg.c0, seg.c1 + 1):
                overflow.setdefault((seg.row, col), []).append(seg.task)
            continue

        status = _status_of(seg.task)
        color = _color_of(status)
        tk = getattr(seg.task, "id", id(seg.task))

        label = (getattr(seg.task, "name", "") or "").strip()
        if not seg.first:
            label = "‹ " + label
        if not seg.last:
            label = label + " ›"

        bar_key = f"bar-{tk}-{seg.row}"
        b_left = seg.c0 * col_w + 3
        b_width = (seg.c1 - seg.c0 + 1) * col_w - 6
        b_top = seg.row * ROW_H + BAR_TOP + seg.lane * (BAR_H + BAR_GAP)

        # 拖动预览：从数据侧取几何，控件自己一个属性都不改。
        # end 侧只改宽，左端位置保持真实值，避免把手侧串扰到左边。
        if drag and drag.get("k") == bar_key:
            b_width = drag["width"]
            b_top = drag.get("top", b_top)
            if drag.get("side") == "start":
                b_left = drag["left"]

        is_hover = hover_key == tk

        body = ft.Container(
            bgcolor=_blend(color, BG_CELL, 0.30 if is_hover else 0.16),
            border_radius=ft.BorderRadius(
                top_left=4 if seg.first else 0,
                bottom_left=4 if seg.first else 0,
                top_right=4 if seg.last else 0,
                bottom_right=4 if seg.last else 0,
            ),
            border=ft.Border(left=ft.BorderSide(3, color)),
            padding=ft.Padding(left=14, top=0, right=14, bottom=0),
            alignment=ft.Alignment.CENTER_LEFT,
            on_click=lambda e, t=seg.task: open_task(t),
            content=ft.Text(
                label,
                size=11,
                color=color,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
        )

        body_det = ft.GestureDetector(
            key=bar_key,
            left=b_left,
            top=b_top,
            width=b_width,
            height=BAR_H,
            on_enter=lambda e, t=tk: set_hover(t),
            on_exit=lambda e: set_hover(None),
            mouse_cursor=ft.MouseCursor.CLICK,
            content=body,
        )

        bar_controls.append(body_det)
        if seg.first:
            bar_controls.append(
                make_handle(seg, "start", bar_key, b_left, b_width, b_top, color)
            )
        if seg.last:
            bar_controls.append(
                make_handle(seg, "end", bar_key, b_left, b_width, b_top, color)
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
