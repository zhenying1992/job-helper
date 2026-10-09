
# 数据
class JobType:
    COMMON = '通用工作'

    @classmethod
    def list(cls):
        return [cls.COMMON]

DATE_FMT = '%Y-%m-%d'
DATE_TIME_FMT = '%Y-%m-%d %H:%M:%S'

class Status:
    FINISHED = '已完成'
    EXECUTING = '执行中'
    WAITING = '阻塞中'
    NOT_START = '未开始'

    @classmethod
    def list(cls):
        return [cls.FINISHED, cls.EXECUTING, cls.WAITING, cls.NOT_START]

class Priority:
    LOW = '低'
    MEDIUM = '中'
    HIGH = '高'

    @classmethod
    def list(cls):
        return [cls.HIGH, cls.MEDIUM, cls.LOW]


# 颜色
COLOR_DANGER = "#ff4757"
COLOR_WARN ="#ffa502"
COLOR_SAFE = "#2ed573"

COLOR_JOB_FINISH = "#26f0d0"
COLOR_TASK_FINISH = "#38a8ff"

#
TRENT_DAY = 30