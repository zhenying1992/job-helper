import logging

from peewee import SqliteDatabase, Model

from config import get_db_path

logger = logging.getLogger(__name__)

# 开启外键约束，让 ON DELETE CASCADE 生效
db = SqliteDatabase(get_db_path(), pragmas={'foreign_keys': 1})


class BaseModel(Model):
    class Meta:
        database = db


MODELS = []


def _load_models():
    global MODELS
    if not MODELS:
        from data.model import Job, Task, Log, DailyReport, Plugin
        MODELS = [Job, Task, Log, DailyReport, Plugin]
    return MODELS


def init_db():
    """初始化数据库，可重复调用；表结构以当前模型为准。

    模型变更时不在运行时做兼容，而是用一次性重建处理（建新表 → 迁数据 →
    换旧表），保证代码里只描述当前结构。
    """
    models = _load_models()
    logger.info('初始化数据库: %s', get_db_path())
    if db.is_closed():
        db.connect()
    db.create_tables(models, safe=True)
