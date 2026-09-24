
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
        return [cls.LOW, cls.MEDIUM, cls.HIGH]
