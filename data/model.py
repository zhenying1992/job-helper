import json
from dataclasses import dataclass, asdict
from datetime import datetime

from peewee import (
    AutoField, BooleanField, CharField, DateField, DateTimeField, ForeignKeyField,
    IntegerField, TextField,
)

from constant import Priority
from data.db import BaseModel


def _json_list(raw) -> list[str]:
    """容错解析 JSON 列表字段。

    历史库里可能存在 NULL / '' / 'null' / 非法 JSON / 类型不符等脏数据，
    统一兜底为字符串列表，避免调用方迭代 None 时崩溃。
    """
    try:
        value = json.loads(raw or '[]')
    except (ValueError, TypeError):
        return []
    return [str(x) for x in value] if isinstance(value, list) else []


def _json_dict(raw) -> dict:
    """容错解析 JSON 对象字段，兜底为空字典。"""
    try:
        value = json.loads(raw or '{}')
    except (ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


class Job(BaseModel):
    id = AutoField()
    type = CharField()
    name = CharField(unique=True)
    description = CharField(default='')
    progress = IntegerField(default=0)
    priority = CharField(default=Priority.LOW)
    status = CharField(default='未开始')
    start_time = DateTimeField(default=datetime.now)
    end_time = DateTimeField(default=datetime.now)
    created_time = DateTimeField(default=datetime.now)
    deleted = BooleanField(default=False)          # 软删除：进入回收站

    class Meta:
        indexes = (
            (('status',), False),
            (('start_time',), False),
            (('end_time',), False),
        )


@dataclass
class Position:
    x: int
    y: int
    downstreams: list[int]


class Task(BaseModel):
    id = AutoField()
    job = ForeignKeyField(Job, backref='tasks', on_delete='CASCADE', index=True)
    name = CharField()
    description = CharField(default='')
    priority = CharField(default=Priority.LOW)
    status = CharField(default='未开始')
    start_time = DateTimeField(default=datetime.now)
    end_time = DateTimeField(default=datetime.now)
    assignee = CharField(default='')                # 负责人
    estimate_hours = IntegerField(default=0)        # 预估工时
    _tags = CharField(column_name='tags', default='[]')
    deleted = BooleanField(default=False)           # 软删除：进入回收站
    _position = TextField(column_name='position', default='{}')

    @property
    def tags(self) -> list[str]:
        return _json_list(self._tags)

    @tags.setter
    def tags(self, value: list[str]):
        self._tags = json.dumps(value or [], ensure_ascii=False)

    @property
    def position(self) -> Position:
        raw = _json_dict(self._position)
        return Position(x=raw.get('x', 0), y=raw.get('y', 0),
                        downstreams=raw.get('downstreams', []))

    @position.setter
    def position(self, value: Position):
        self._position = json.dumps(asdict(value))

    class Meta:
        indexes = ((('job_id', 'name'), True),)


class Log(BaseModel):
    """工作审计日志：记录一次操作/事件及其关联文件。"""
    id = AutoField()
    job = ForeignKeyField(Job, backref='logs', on_delete='CASCADE', index=True)
    name = CharField()          # 事件名，如「新建工作」「上传附件」
    content = CharField(default='')
    created_time = DateTimeField(default=datetime.now)
    _related_files = CharField(column_name='related_files', default='[]')

    class Meta:
        indexes = (
            (('job_id',), False),
            (('created_time',), False),
        )

    @property
    def related_files(self) -> list[str]:
        return _json_list(self._related_files)

    @related_files.setter
    def related_files(self, value: list[str]):
        self._related_files = json.dumps(value or [], ensure_ascii=False)


class DailyReport(BaseModel):
    """按自然日保存的工作日报正文，与审计日志视图一一对应。"""
    day = DateField(unique=True)
    content = TextField(default='')
    created_time = DateTimeField(default=datetime.now)
    updated_time = DateTimeField(default=datetime.now)


class Plugin(BaseModel):
    id = AutoField()
    name = CharField()
    description = CharField(default='')
    version = IntegerField()
    file_name = CharField()
    created_time = DateTimeField(default=datetime.now)

    class Meta:
        indexes = ((('name', 'version'), True),)
