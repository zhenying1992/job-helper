from peewee import SqliteDatabase, Model

from src.config import get_db_path

db = SqliteDatabase(get_db_path())

# 基础模型
class BaseModel(Model):
    class Meta:
        database = db

def init_db():
    from src.data.model import Job, Task, Log
    db.connect()
    db.create_tables([Job, Task, Log], safe=True)
