import logging

from peewee import SqliteDatabase, Model

from config import get_db_path
logger = logging.getLogger(__name__)

db = SqliteDatabase(get_db_path())

# 基础模型
class BaseModel(Model):
    class Meta:
        database = db

def init_db():
    logger.info(f"开始初始化数据库: {get_db_path()}")
    from data.model import Job, Task, Log
    db.connect()
    logger.info(f"数据库连接成功")
    db.create_tables([Job, Task, Log], safe=True)
