"""全局视觉主题：颜色、字体、字号、圆角、边框与表格样式的唯一数据源。

风格：暗色科技感（Neon-tech）——近黑蓝的分层背景 + 青蓝霓虹强调 + 冷调文字。
约定：任何页面都不要内联十六进制颜色或魔法字号，统一从这里引用。
业务枚举（状态/优先级/工作类型）在 constant.py，其颜色取自本文件。
"""

# ---------------------------------------------------------------- 强调 / 语义色
PRIMARY = '#22d3ee'        # 主色：青（科技感主色调）
ACCENT = '#00e5ff'         # 霓虹青强调（选中、链接、图表）
ACCENT_SOFT = '#7dd3fc'    # 浅青（次要强调、附件）
ACCENT_BRIGHT = '#22d3ee'  # 亮青（边框、按钮、Tab 指示条）
INFO = '#38bdf8'           # 信息蓝（时间戳）
DANGER = '#ff4d6d'         # 危险 / 逾期（霓虹红）
WARN = '#ffb020'           # 警告（琥珀）
SAFE = '#2ee6a8'           # 安全（霓虹绿）
SUCCESS = '#00e5a0'        # 完成（青绿，科技感）
SLATE = '#5b708f'          # 灰蓝（未知状态、图标、次要文字）
MUTED = '#8fa3c4'          # 冷灰蓝（表头、日期、Tab）
JOB_FINISH = '#00e5ff'     # 工作完成趋势线（青）
TASK_FINISH = '#7c8cff'    # 任务完成趋势线（蓝紫）
SELECTED = '#ffd166'       # 拓扑选中节点
PURPLE = '#a855f7'         # 拓扑阻塞节点
PURPLE_DARK = '#2d1b4e'    # 拓扑阻塞节点底色
GREEN_DARK = '#04352c'     # 拓扑完成节点底色
BTN_ADD = '#0891b2'        # 新增按钮（深青）

# ---------------------------------------------------------------- 背景色（由深到浅分层）
BG_PAGE = '#04070f'        # 应用窗口（最深）
BG_PANEL = '#0a1224'       # 面板
BG_HEADER = '#0d1830'      # 页头
BG_HEADER_BAR = '#08101f'  # 工作详情顶栏
BG_CARD = '#0c1428'        # 卡片
BG_CARD_ALT = '#101c38'    # 拓扑卡片
BG_CANVAS = '#070d1b'      # 画布 / 日历
BG_INPUT = '#0c1730'       # 输入框
BG_SEARCH = '#0b152c'      # 搜索框
BG_TABLE = '#0a1224'       # 表格
BG_TABLE_HEAD = '#10203c'  # 表头
BG_DIALOG = '#0a1224'      # 弹窗 / 导航
BG_CELL = '#0a1528'        # 日历格
BG_CELL_DIM = '#070e1c'    # 日历非当月格
BG_TODAY = '#062a35'       # 日历今日格

# ---------------------------------------------------------------- 文字色（冷白蓝调）
TEXT = '#c7d6ee'           # 正文
TEXT_BRIGHT = '#e6f1ff'    # 高亮正文
TEXT_TITLE = '#e0f2fe'     # 标题
TEXT_ON_DARK = '#04121b'   # 深底按钮上的文字
BTN_TEXT = '#f0fbff'       # 亮底/彩色按钮上的冷白文字
TEXT_TAB_ACTIVE = '#f0fbff'
TEXT_TAB_INACTIVE = '#5b7398'
TEXT_WEEKEND = '#6b83ab'   # 周末日期
TEXT_DIM = '#33445f'       # 非当月日期
TEXT_SUBTLE = '#3a4d6b'    # 极次要（空状态图标）
WHITE = '#ffffff'

# ---------------------------------------------------------------- 边框 / 分割线
BORDER = '#1c3a5e'         # 通用分割线
BORDER_SOFT = '#132340'    # 日历网格线
BORDER_STRONG = '#1d4570'  # 日历弹层边框
BORDER_TOPO = '#24405f'    # 拓扑卡片边框
BORDER_ACCENT = '#22d3ee66'  # 卡片青色描边（带透明）
TRANSPARENT = '#01000000'  # 全透明

# ---------------------------------------------------------------- 发光 / 阴影（科技感核心）
GLOW_SOFT = '#22d3ee33'    # 柔和光晕（带透明，用于卡片）
SHADOW_BLUR = 16           # 光晕模糊半径
SHADOW_SPREAD = 1          # 光晕扩散半径


def glow(color: str = GLOW_SOFT, blur: int = SHADOW_BLUR,
         spread: int = SHADOW_SPREAD, offset=None):
    """构造青蓝光晕阴影，供卡片/按钮/指示条统一复用。"""
    import flet as ft
    return ft.BoxShadow(
        spread_radius=spread, blur_radius=blur, color=color, offset=offset,
    )

# ---------------------------------------------------------------- 圆角 / 节点尺寸
RADIUS = 10
RADIUS_SM = 4
RADIUS_MD = 6
RADIUS_LG = 8
NODE_W, NODE_H = 140, 60   # 拓扑节点长宽

# ---------------------------------------------------------------- 字体
# 科技感：数值/代码用等宽字体，界面用系统无衬线字体。
# Flet 通过 Text(font_family=...) 指定；系统等宽字体无需打包字体文件。
FONT_MONO = 'monospace'    # 数字、进度、时间等数据
FS_XS = 10
FS_SM = 11
FS_MD = 12
FS_LG = 13
FS_BASE = 14
FS_TAB = 15
FS_XL = 16
FS_XXL = 20
FS_DISPLAY = 26
FS_METRIC = 40

# ---------------------------------------------------------------- 表格样式
TABLE_RADIUS = RADIUS
