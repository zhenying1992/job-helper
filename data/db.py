import logging

from peewee import SqliteDatabase, Model
from playhouse.migrate import SqliteMigrator

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
        from data.model import Job, Task, Log, Plugin
        MODELS = [Job, Task, Log, Plugin]
    return MODELS


def _column_sql(field, column: str) -> str:
    """生成 '列定义 + 默认值'，供 SQLite 原生 ADD COLUMN 使用。

    peewee 的 default 是应用层的，DDL 里不带 DEFAULT；这里手动补上，
    这样加 NOT NULL 列时无需重建整张表（重建会触发外键约束失败）。
    """
    ctx = SqliteMigrator(db).make_context()
    ctx.literal('').sql(field.ddl(ctx))
    definition = ctx.query()[0].strip()

    parts = [f'"{column}"']
    # 去掉 ddl 里的列名与 NOT NULL，稍后按 null 属性重新拼装
    definition = definition[len(f'"{column}"'):].strip()
    definition = definition.replace(' NOT NULL', '').replace(' PRIMARY KEY', '')
    parts.append(definition)

    if not field.null:
        default = field.default() if callable(field.default) else field.default
        if default is not None:
            literal = field.db_value(default)
            if isinstance(literal, str):
                literal = literal.replace("'", "''")
                default_sql = f"'{literal}'"
            elif isinstance(literal, bool):
                default_sql = '1' if literal else '0'
            elif isinstance(literal, (int, float)):
                default_sql = str(literal)
            else:
                default_sql = "'0'"  # 日期等类型用占位，后续由业务写入
            parts.append(f'NOT NULL DEFAULT {default_sql}')
        else:
            parts.append('NOT NULL DEFAULT 0' if 'INT' in definition else "NOT NULL DEFAULT ''")
    else:
        parts.append('NULL')

    return ' '.join(parts)


def _migrate_columns():
    """为旧库补齐模型中新增的列，避免改表结构后必须手动删库。"""
    for model in _load_models():
        table = model._meta.table_name
        existing = {col.name for col in db.get_columns(table)}
        for field in model._meta.sorted_fields:
            column = field.column_name
            if field.primary_key or column in existing:
                continue
            sql = _column_sql(field, column)
            logger.info('数据库迁移: %s 新增列 %s', table, column)
            db.execute_sql(f'ALTER TABLE "{table}" ADD COLUMN {sql}')


def init_db():
    """初始化数据库，可重复调用；自动建表并补齐缺失字段。"""
    models = _load_models()
    logger.info('初始化数据库: %s', get_db_path())
    if db.is_closed():
        db.connect()
    db.create_tables(models, safe=True)  # 建缺失的表，不动已有表
    _migrate_columns()                    # 补已有表缺失的列
