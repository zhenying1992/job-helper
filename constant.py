"""业务常量：日期格式、枚举、统计参数。

视觉配置（颜色/字体/字号/圆角/边框/表格）统一在 theme.py。
这里通过别名导出，使旧的 `from constant import COLOR_TEXT` 等写法继续可用，
但颜色的唯一定义权在 theme.py。枚举是状态/优先级的唯一数据源。
"""

from theme import (
    DANGER as COLOR_DANGER,
    WARN as COLOR_WARN,
    SAFE as COLOR_SAFE,
    JOB_FINISH as COLOR_JOB_FINISH,
    TASK_FINISH as COLOR_TASK_FINISH,
    SLATE as COLOR_UNKNOWN,
    BG_MAIN,
    BG_PANEL,
    BG_HEADER,
    TEXT as COLOR_TEXT,
    PRIMARY as COLOR_PRIMARY,
    SUCCESS as COLOR_SUCCESS,
    RADIUS as BORDER_RADIUS,
    NODE_W,
    NODE_H,
    ACCENT,
)

DATE_FMT = '%Y-%m-%d'
DATE_TIME_FMT = '%Y-%m-%d %H:%M:%S'
DEFAULT_JOB_END_DAY = 7
TREND_DAY = 30  # 趋势图统计天数

# 逾期：未完成且已过结束时间时的展示状态（派生状态，非数据库枚举）
OVERDUE = '逾期'


class Status:
    FINISHED = '已完成'
    EXECUTING = '执行中'
    BLOCKED = '阻塞中'
    NOT_START = '未开始'

    # 历史版本用过的别名 → 现行枚举值，读库后统一归一化，避免同义状态分裂图例
    ALIASES = {
        '待开始': NOT_START,
        '进行中': EXECUTING,
        '暂停中': BLOCKED,
        '已暂停': BLOCKED,
        '完成': FINISHED,
    }

    COLORS = {
        NOT_START: COLOR_UNKNOWN,
        EXECUTING: ACCENT,
        BLOCKED: COLOR_WARN,
        FINISHED: COLOR_SUCCESS,
        OVERDUE: COLOR_DANGER,
    }

    @classmethod
    def list(cls):
        """工作流正序：未开始 → 执行中 → 阻塞中 → 已完成。

        看板列、状态下拉框、统计图例统一用这个顺序，避免各处顺序不一致。
        """
        return [cls.NOT_START, cls.EXECUTING, cls.BLOCKED, cls.FINISHED]

    @classmethod
    def normalize(cls, status: str) -> str:
        """把任意历史状态名归一化为现行枚举值；未知值原样返回。"""
        value = (status or '').strip()
        return cls.ALIASES.get(value, value)

    @classmethod
    def color(cls, status: str) -> str:
        return cls.COLORS.get(cls.normalize(status), COLOR_UNKNOWN)


class Priority:
    LOW = '低'
    MEDIUM = '中'
    HIGH = '高'

    COLORS = {HIGH: COLOR_DANGER, MEDIUM: COLOR_WARN, LOW: COLOR_SAFE}

    @classmethod
    def list(cls):
        return [cls.HIGH, cls.MEDIUM, cls.LOW]

    @classmethod
    def color(cls, priority: str) -> str:
        return cls.COLORS.get(priority, COLOR_TEXT)


class JobType:
    COMMON = '通用工作'

    @classmethod
    def list(cls):
        return [cls.COMMON]
