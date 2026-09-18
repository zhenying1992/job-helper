import json
from datetime import datetime

from peewee import AutoField, CharField, DateTimeField, ForeignKeyField, IntegerField

from src.data.db import BaseModel

from src.constant import DATA_FMT

class Job(BaseModel):
    id = AutoField()
    type = CharField()
    name = CharField(unique=True)
    description = CharField()
    progress = IntegerField()
    priority = CharField()
    status = CharField()
    _start_time = DateTimeField(column_name='start_time')
    _end_time = DateTimeField(column_name='end_time')

    @property
    def start_time(self):
        return self._start_time.strftime(DATA_FMT)   # noqa

    @start_time.setter
    def start_time(self, value: str| datetime):
        if isinstance(value, datetime):
            self._start_time = value
        else:
            self._start_time = datetime.strptime(value, DATA_FMT)

    @property
    def end_time(self):
        return self._end_time.strftime(DATA_FMT)   # noqa

    @end_time.setter
    def end_time(self, value: str | datetime):
        if isinstance(value, datetime):
            self._end_time = value
        else:
            self._end_time = datetime.strptime(value, DATA_FMT)

    class Meta:
        indexes = (
            (('name',), True),
            (('status',), False),
            (('start_time',), False),
            (('end_time',), False),
        )


class Task(BaseModel):
    id = AutoField()
    job = ForeignKeyField(Job, backref='tasks', index=True)
    name = CharField()
    description = CharField()
    priority = CharField()
    status = CharField()
    start_time = DateTimeField()
    end_time = DateTimeField()

    class Meta:
        indexes = (
            (('job_id',), False),
            (('name',), True),
        )


class Log(BaseModel):
    id = AutoField()
    job = ForeignKeyField(Job, backref='logs')
    name = CharField()
    content = CharField()
    created_time = DateTimeField()
    _related_files = CharField(column_name='related_files')

    class Meta:
        indexes = ((('job_id',), False), (('created_time',), False),)

    @property
    def related_files(self):
        return json.loads(self._related_files)

    @related_files.setter
    def related_files(self, value):
        self._related_files = json.dumps(value)
