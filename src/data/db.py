import logging

from peewee import SqliteDatabase, Model

from src.config import get_db_path
logger = logging.getLogger(__name__)

db = SqliteDatabase(get_db_path())

# 基础模型
class BaseModel(Model):
    class Meta:
        database = db

def init_db():
    from src.data.model import Job, Task, Log
    db.connect()
    logger.info(f"数据库连接成功: {db}")
    db.create_tables([Job, Task, Log], safe=True)
