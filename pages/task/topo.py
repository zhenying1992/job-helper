from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import flet as ft
import flet.canvas as cv

from constant import NODE_H, NODE_W, Status
from data.model import Job
from data.service import TaskService
from pages.task import CreateTaskDialog, UpdateTaskDialog, DropTaskDialog
from theme import (
    BG_CANVAS as BG, BG_CARD_ALT as CARD, BORDER_TOPO as BORDER,
    PRIMARY as ACCENT, ACCENT_SOFT as GHOST, TEXT_BRIGHT as TEXT,
    SELECTED as SEL, TEXT_SUBTLE, TRANSPARENT, FS_LG, FS_MD, FS_XS,
)

# ---------------- 尺寸与配色 ----------------

# 画布尽量撑满工作详情右侧区域；下限保证节点排布空间。
# 工作详情右侧约为窗口宽 - 左侧 300 - 内边距，取一个偏大的自适应值。
def _canvas_size(height: int | None = None) -> tuple[int, int]:
    # 宽度：右侧工作区 ≈ 窗口宽 - 左侧详情 300 - 内边距 ≈ window - 360
    try:
        win_w = ft.context.page.window.width or 1280
    except Exception:
        win_w = 1280
    # 高度由调用方按右侧面板高度传入，未传时用默认值（保持其它调用兼容）
    return max(780, int(win_w) - 360), (height or CANVAS_H)


# 导入期无渲染上下文，这里只是兜底；真实尺寸在 FlowEditorView 渲染时取窗口宽度。
CANVAS_H = 560

# 颜色统一来自 theme；上面的别名保持下方绘图代码的可读性。

PORT_BAND = 18  # 节点四条边往内多少像素算"连线带"
LINK_HIT_DIST = 9  # 点击选中连线的判定距离（px）
HIT_PAD = 10  # 连线落点吸附节点的外扩容差

ARROW_SIZE = 12  # 箭头三角形长度
DRAG_INTERVAL = 1  # 拖动识别阈值（px）

# 光标：连线带一种，节点中段一种
CURSOR_LINK = ft.MouseCursor.ALIAS
CURSOR_MOVE = ft.MouseCursor.GRAB

# 四条边的外法线方向，画临时连线时用来定控制点
DIR_VEC = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


# ==================== 状态模型 ====================

@ft.observable
@dataclass
class Node:
    """纯数据节点。不持有任何 Flet 控件引用。"""
    id: int
    x: float
    y: float
    text: str
    kind: str = "process"       # start / process / end（连线形态用）
    status: str = ""            # 任务状态：决定节点配色
    assignee: str = ""          # 负责人：节点副信息
    hours: int = 0              # 预估工时：节点副信息
    tags: str = ""              # 标签：节点副信息（逗号拼接，超长截断）

    def anchor(self, direction: str) -> tuple[float, float]:
        """某一侧的中点（Stack 坐标）"""
        if direction == "up":
            return (self.x + NODE_W / 2, self.y)
        if direction == "down":
            return (self.x + NODE_W / 2, self.y + NODE_H)
        if direction == "left":
            return (self.x, self.y + NODE_H / 2)
        return (self.x + NODE_W, self.y + NODE_H / 2)


@ft.observable
@dataclass
class EditorState:
    """整张图的唯一数据源。所有交互都只改这里的字段。"""
    job: Job
    nodes: list[Node] = field(default_factory=lambda: [])
    edges: list[tuple[int, int]] = field(
        default_factory=lambda: []
    )
    next_id: int = 5
    rev: int = 0  # 拖动节点时 +1，用来带动画布重绘

    selected: int | None = None  # 选中节点的 id
    selected_edge: tuple[int, int] | None = None

    # 一次手势要么在拉线、要么在拖节点，不会同时
    link_from: int | None = None  # 拉线的源节点 id
    link_dir: str | None = None  # 从哪条边起拖
    link_pos: tuple[float, float] | None = None
    drag: int | None = None  # 正在拖动的节点 id
    hover: int | None = None  # 拖连线时悬停的目标节点 id

    def node(self, nid: int) -> Node | None:
        for n in self.nodes:
            if n.id == nid:
                return n
        return None

    def reload(self):
        tasks = TaskService.query(job_id=self.job.id)

        nodes, edges = [], []
        for task in tasks:
            nodes.append(Node(
                id=task.id,
                x=task.position.x,
                y=task.position.y,
                text=task.name,
                kind=task.status,
                status=Status.normalize(task.status),
                assignee=(task.assignee or "").strip(),
                hours=task.estimate_hours or 0,
                tags=", ".join(task.tags),
            ))
            for downstream in task.position.downstreams:
                edges.append((task.id, downstream))

        self.nodes = nodes
        self.edges = edges


# ==================== 配色 ====================

def _tint(color: str, alpha: float = 0.18) -> str:
    """把前景色按 alpha 混到卡片底色，得到不透明的节点填充。"""
    f = color.lstrip("#")
    b = CARD.lstrip("#")
    fr, fg_, fb = int(f[0:2], 16), int(f[2:4], 16), int(f[4:6], 16)
    br, bg_, bb = int(b[0:2], 16), int(b[2:4], 16), int(b[4:6], 16)
    return "#{:02x}{:02x}{:02x}".format(
        int(fr * alpha + br * (1 - alpha)),
        int(fg_ * alpha + bg_ * (1 - alpha)),
        int(fb * alpha + bb * (1 - alpha)),
    )


def node_colors(node: Node) -> tuple[str, str]:
    """返回 (填充色, 默认边框色)。随任务状态色变化，未识别状态回退到中性色。"""
    state = Status.normalize(node.status)
    color = Status.color(state)
    if not state or state not in Status.COLORS:
        return CARD, TEXT_SUBTLE
    return _tint(color), color


# ==================== 几何（纯函数） ====================

def curve(na: Node, nb: Node):
    """按两节点相对位置自动选边，返回 (起点, 控制点1, 控制点2, 终点)"""
    if nb.y >= na.y + NODE_H:  # 目标在下方 → 底出顶进
        x1, y1 = na.x + NODE_W / 2, na.y + NODE_H
        x2, y2 = nb.x + NODE_W / 2, nb.y
        d = max(abs(y2 - y1) * 0.45, 24)
        return (x1, y1), (x1, y1 + d), (x2, y2 - d), (x2, y2)
    if na.y >= nb.y + NODE_H:  # 目标在上方 → 顶出底进
        x1, y1 = na.x + NODE_W / 2, na.y
        x2, y2 = nb.x + NODE_W / 2, nb.y + NODE_H
        d = max(abs(y1 - y2) * 0.45, 24)
        return (x1, y1), (x1, y1 - d), (x2, y2 + d), (x2, y2)
    if nb.x >= na.x:  # 目标在右侧 → 右出左进
        x1, y1 = na.x + NODE_W, na.y + NODE_H / 2
        x2, y2 = nb.x, nb.y + NODE_H / 2
        d = max(abs(x2 - x1) * 0.45, 24)
        return (x1, y1), (x1 + d, y1), (x2 - d, y2), (x2, y2)
    x1, y1 = na.x, na.y + NODE_H / 2  # 目标在左侧 → 左出右进
    x2, y2 = nb.x + NODE_W, nb.y + NODE_H / 2
    d = max(abs(x1 - x2) * 0.45, 24)
    return (x1, y1), (x1 - d, y1), (x2 + d, y2), (x2, y2)


def unit(c2, end):
    """曲线末段切线单位向量：箭头顺着线走，不能写死四个正交方向"""
    dx, dy = end[0] - c2[0], end[1] - c2[1]
    length = math.hypot(dx, dy) or 1.0
    return dx / length, dy / length


def curve_path(start, c1, c2, end, color, width=2):
    """曲线本体；线头回退一段藏进三角形，避免线尖从箭头顶点戳出来"""
    ux, uy = unit(c2, end)
    trim = ARROW_SIZE * 0.75
    ex, ey = end[0] - ux * trim, end[1] - uy * trim
    return cv.Path(
        elements=[
            cv.Path.MoveTo(start[0], start[1]),
            cv.Path.CubicTo(c1[0], c1[1], c2[0], c2[1], ex, ey),
        ],
        paint=ft.Paint(stroke_width=width, color=color,
                       style=ft.PaintingStyle.STROKE),
    )


def arrow_path(c2, end, color):
    """在终点画一个填充三角箭头，方向跟着末段切线走"""
    size = ARROW_SIZE
    ux, uy = unit(c2, end)
    px, py = -uy, ux  # 切线转 90° 得到三角底边方向
    x, y = end
    bx, by = x - ux * size, y - uy * size
    left = (bx + px * size * 0.55, by + py * size * 0.55)
    right = (bx - px * size * 0.55, by - py * size * 0.55)
    return cv.Path(
        elements=[
            cv.Path.MoveTo(x, y),
            cv.Path.LineTo(left[0], left[1]),
            cv.Path.LineTo(right[0], right[1]),
            cv.Path.Close(),
        ],
        paint=ft.Paint(color=color, style=ft.PaintingStyle.FILL),
    )


def bezier_point(p0, p1, p2, p3, t):
    """三次贝塞尔参数方程，给定 t∈[0,1] 求曲线上一点"""
    mt = 1.0 - t
    x = (mt ** 3) * p0[0] + 3 * (mt ** 2) * t * p1[0] \
        + 3 * mt * (t ** 2) * p2[0] + (t ** 3) * p3[0]
    y = (mt ** 3) * p0[1] + 3 * (mt ** 2) * t * p1[1] \
        + 3 * mt * (t ** 2) * p2[1] + (t ** 3) * p3[1]
    return x, y


def dist_to_segment(p, a, b):
    """点到线段的最短距离（不是到无限延长的直线）"""
    ax, ay = a
    vx, vy = b[0] - ax, b[1] - ay
    l2 = vx * vx + vy * vy
    if l2 == 0:
        return math.hypot(p[0] - ax, p[1] - ay)
    t = max(0.0, min(1.0, ((p[0] - ax) * vx + (p[1] - ay) * vy) / l2))
    return math.hypot(p[0] - (ax + vx * t), p[1] - (ay + vy * t))


def dist_to_curve(pos, p0, p1, p2, p3, steps=24):
    """把曲线切成折线求最短距离，够准且够快"""
    best = float("inf")
    prev = p0
    for i in range(1, steps + 1):
        cur = bezier_point(p0, p1, p2, p3, i / steps)
        d = dist_to_segment(pos, prev, cur)
        if d < best:
            best = d
        prev = cur
    return best


def edge_dir(node: Node, lp):
    """按下的点落在哪条边的连线带上；返回 up/down/left/right，中段返回 None"""
    if node.kind == "end" or lp is None:
        return None
    if lp.y <= PORT_BAND:            return "up"
    if lp.y >= NODE_H - PORT_BAND:   return "down"
    if lp.x <= PORT_BAND:            return "left"
    if lp.x >= NODE_W - PORT_BAND:   return "right"
    return None


def hit_node(state: EditorState, pos) -> Node | None:
    """落点在哪个节点内（外扩 HIT_PAD，吸附更好按）"""
    x, y = pos
    for n in state.nodes:
        if (n.x - HIT_PAD <= x <= n.x + NODE_W + HIT_PAD
                and n.y - HIT_PAD <= y <= n.y + NODE_H + HIT_PAD):
            return n
    return None


def compute_shapes(state: EditorState):
    """唯一的绘制出口：从 state 算出全部 shape，无副作用"""
    shapes = []

    for a, b in state.edges:
        na, nb = state.node(a), state.node(b)
        if na is None or nb is None:
            continue
        start, c1, c2, end = curve(na, nb)
        is_sel = state.selected_edge == (a, b)
        color, width = (SEL, 3) if is_sel else (ACCENT, 2)
        shapes.append(curve_path(start, c1, c2, end, color, width))
        shapes.append(arrow_path(c2, end, color))

    # 正在拖的临时连线：从起拖那条边的中点出去，控制点沿该边外法线
    if state.link_from is not None and state.link_pos:
        n = state.node(state.link_from)
        if n is not None:
            x1, y1 = n.anchor(state.link_dir or "right")
            x2, y2 = state.link_pos
            dx, dy = DIR_VEC.get(state.link_dir or "right", (1, 0))
            c1 = (x1 + dx * 50, y1 + dy * 50)
            c2 = (x2 - dx * 40, y2 - dy * 40)

            ux, uy = unit(c2, (x2, y2))
            trim = ARROW_SIZE * 0.75
            shapes.append(cv.Path(
                elements=[
                    cv.Path.MoveTo(x1, y1),
                    cv.Path.CubicTo(c1[0], c1[1], c2[0], c2[1],
                                    x2 - ux * trim, y2 - uy * trim),
                ],
                paint=ft.Paint(stroke_width=1.5, color=GHOST,
                               style=ft.PaintingStyle.STROKE),
            ))
            shapes.append(arrow_path(c2, (x2, y2), GHOST))
    return shapes


# ==================== 交互：只改 state，不碰控件 ====================

def pan_start(state: EditorState, node: Node, e):
    """按下瞬间分流：四边连线带 → 拉线；中间区域 → 拖节点"""
    d = edge_dir(node, e.local_position)
    if d:
        state.link_from = node.id
        state.link_dir = d
        state.link_pos = node.anchor(d)
        state.drag = None
        state.selected_edge = None
    else:
        state.drag = node.id
        state.link_from = None
        state.link_dir = None


def pan_update(state: EditorState, node: Node, e):
    """拖动过程：拉线只累积鼠标位置，拖节点改坐标并 rev+1 带动画布"""
    dl = e.local_delta or ft.Offset(0, 0)

    if state.link_from is not None:
        if state.link_pos is None:
            return
        lx, ly = state.link_pos
        state.link_pos = (lx + dl.x, ly + dl.y)  # 换新 tuple → 通知订阅者
        t = hit_node(state, state.link_pos)
        state.hover = t.id if (t is not None and t.id != state.link_from) else None
        return

    if state.drag is not None:
        node.x += dl.x
        node.y += dl.y
        state.rev += 1  # 节点坐标不是 state 字段，靠它触发画布重绘


def pan_end(state: EditorState, node, e):
    """松手收尾：落点命中另一节点才建边，然后清干净临时状态"""
    if state.link_from is not None and state.link_pos:
        t = hit_node(state, state.link_pos)
        if (
                t is not None and
                t.id != state.link_from and
                (state.link_from, t.id) not in state.edges
        ):
            state.edges.append((state.link_from, t.id))
            move_node(state.link_from, node.x, node.y, t.id)

    # 2) 拖节点收尾
    if state.drag is not None:
        move_node(node.id, node.x, node.y)

    state.link_from = None
    state.link_dir = None
    state.link_pos = None
    state.drag = None
    state.hover = None


def tap_canvas(state: EditorState, e):
    """点空白处：命中哪条线就选中它，没命中就全清"""
    if e.local_position is None:
        return
    pos = (e.local_position.x, e.local_position.y)
    best, best_d = None, LINK_HIT_DIST
    for edge in state.edges:
        na, nb = state.node(edge[0]), state.node(edge[1])
        if na is None or nb is None:
            continue
        d = dist_to_curve(pos, *curve(na, nb))
        if d < best_d:
            best_d, best = d, edge
    state.selected_edge = best
    state.selected = None


def select_node(state: EditorState, node: Node):
    """单击选中节点。节点与连线选中互斥"""
    state.selected = node.id
    state.selected_edge = None


def delete_selected(state: EditorState):
    """删除当前选中的东西：优先连线，其次节点；删节点连带清掉它的边"""
    # 删线
    if state.selected_edge is not None:
        state.edges = [x for x in state.edges if x != state.selected_edge]
        delete_edge(state.selected_edge)
        state.selected_edge = None
        return

    if state.selected is None:
        return

    # 删节点
    delete_node(state, state.selected)
    # sid = state.selected
    # state.nodes = [n for n in state.nodes if n.id != sid]
    # state.edges = [(a, b) for a, b in state.edges if a != sid and b != sid]
    # state.selected = None

# ==================== 数据 ====================

def add_node(state: EditorState):
    ft.context.page.show_dialog(
        CreateTaskDialog(job_id=state.job.id, on_saved=state.reload)
    )


def move_node(task_id: int, x: int, y: int, downstream_task_id: Optional[int]=None):
    task = TaskService.get(task_id)
    position = task.position
    position.x, position.y = x, y

    if downstream_task_id is not None:
        position.downstreams.append(downstream_task_id)

    task.position = position
    task.save()


def update_node(state: EditorState, node: Node):
    task = TaskService.get(node.id)
    ft.context.page.show_dialog(
        UpdateTaskDialog(task=task, on_saved=state.reload)
    )


def delete_edge(select_edge: tuple[int, int]):
    task = TaskService.get(select_edge[0])
    position = task.position
    position.downstreams = [i for i in position.downstreams if i != select_edge[1]]
    task.position = position
    task.save()


def delete_node(state: EditorState, node_id: int):
    task = TaskService.get(node_id)
    ft.context.page.show_dialog(
        DropTaskDialog(task=task, on_saved=state.reload)
    )


# ==================== 组件 ====================

@ft.component
def NodeView(state: EditorState, node: Node):
    """单个节点。光标用组件局部 state，避免每次 hover 全量重画"""
    cursor, set_cursor = ft.use_state(CURSOR_MOVE)

    def hover(e):
        if state.link_from is not None or state.drag is not None:
            return  # 拖动进行中不闪光标
        c = CURSOR_LINK if edge_dir(node, e.local_position) else CURSOR_MOVE
        if c != cursor:
            set_cursor(c)  # 只重渲染这一个节点

    fill, default_border = node_colors(node)
    state_color = default_border if default_border != TEXT_SUBTLE else GHOST

    if state.hover is not None and state.hover == node.id:
        border = state_color
    elif state.selected is not None and state.selected == node.id:
        border = ACCENT
    else:
        border = default_border

    # 副信息：只展示有值的项，评估后取「负责人 · 工时」，标签作 tooltip 不占高度。
    # 任务名可能较长，用 ELLIPSIS 截断保证不撑破节点。
    meta_parts = []
    if node.assignee:
        meta_parts.append(node.assignee)
    if node.hours:
        meta_parts.append(f"{node.hours}h")
    meta = " · ".join(meta_parts)
    tooltip = node.tags or None

    info = ft.Column(
        controls=[
            ft.Text(node.text, color=TEXT, size=FS_LG,
                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                    text_align=ft.TextAlign.CENTER),
            ft.Text(meta, color=state_color, size=FS_XS,
                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                    text_align=ft.TextAlign.CENTER),
        ] if meta else [
            ft.Text(node.text, color=TEXT, size=FS_LG,
                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                    text_align=ft.TextAlign.CENTER),
        ],
        spacing=2,
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    return ft.Container(
        left=node.x,
        top=node.y,
        width=NODE_W,
        height=NODE_H,
        content=ft.GestureDetector(
            mouse_cursor=cursor,
            drag_interval=DRAG_INTERVAL,
            on_tap=lambda e: select_node(state, node),
            on_double_tap=lambda e: update_node(state, node),
            on_hover=hover,
            on_pan_start=lambda e: pan_start(state, node, e),
            on_pan_update=lambda e: pan_update(state, node, e),
            on_pan_end=lambda e: pan_end(state, node, e),
            content=ft.Container(
                width=NODE_W,
                height=NODE_H,
                bgcolor=fill,
                border=ft.Border.all(2, border),
                border_radius=10,
                alignment=ft.Alignment.CENTER,
                tooltip=tooltip,
                content=info,
            ),
        ),
    )


@ft.component
def FlowEditorView(state: EditorState, canvas_h: int | None = None):
    """整张图：画布 + 命中层 + 全部节点，全部由 state 派生"""
    canvas_w, canvas_h = _canvas_size(canvas_h)
    return ft.Column(
        [
            ft.Row(
                [
                    ft.Button("新增节点", icon=ft.Icons.ADD,
                              on_click=lambda e: add_node(state)),
                    ft.Button("删除选中", icon=ft.Icons.DELETE_OUTLINE,
                              on_click=lambda e: delete_selected(state)),
                    ft.Text("拖四边 = 连线 · 单击连线 = 选中 · 双击节点 = 改名",
                            size=FS_MD, color=TEXT_SUBTLE),
                ],
                spacing=10,
            ),
            ft.Container(
                content=ft.Stack(
                    [
                        cv.Canvas(
                            shapes=compute_shapes(state),
                            width=canvas_w,
                            height=canvas_h,
                        ),
                        ft.GestureDetector(
                            on_tap=lambda e: tap_canvas(state, e),
                            content=ft.Container(
                                width=canvas_w,
                                height=canvas_h,
                                bgcolor=TRANSPARENT,
                            ),
                        ),
                        *[NodeView(state, n) for n in state.nodes],
                    ],
                    width=canvas_w,
                    height=canvas_h,
                ),
                bgcolor=BG,
                border=ft.Border.all(1, BORDER),
                border_radius=12,
            ),
        ],
        spacing=10,
    )


# ==================== 挂载入口 ====================

class TaskTopo:
    def __init__(self, job: Job, canvas_h: int | None = None):
        self.job = job
        self.canvas_h = canvas_h
        # 状态必须挂在页面级对象上：在 @ft.component 里 new 会每次重渲染都丢
        self.state = EditorState(job=self.job)
        self.state.reload()

    def build(self):
        return FlowEditorView(self.state, self.canvas_h)
