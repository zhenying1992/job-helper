import json
from datetime import datetime

from peewee import AutoField, CharField, DateTimeField, ForeignKeyField, IntegerField

from data.db import BaseModel


class Job(BaseModel):
    id = AutoField()
    type = CharField()
    name = CharField(unique=True)
    description = CharField()
    progress = IntegerField(default=0)
    priority = IntegerField()
    status = CharField()
    start_time = DateTimeField()
    end_time = DateTimeField()
    created_time = DateTimeField(default=datetime.now)
    updated_time = DateTimeField(default=datetime.now)
    updated_content = CharField(default='')

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
    status = CharField()
    start_time = DateTimeField()
    end_time = DateTimeField()

    class Meta:
        indexes = (
            (('job_id', 'name'), True),
        )


class Log(BaseModel):
    id = AutoField()
    job = ForeignKeyField(Job, backref='logs')
    name = CharField()
    content = CharField()
    created_time = DateTimeField(default=datetime.now)
    _related_files = CharField(column_name='related_files')

    class Meta:
        indexes = ((('job_id',), False), (('created_time',), False),)

    @property
    def related_files(self):
        return json.loads(self._related_files)

    @related_files.setter
    def related_files(self, value):
        self._related_files = json.dumps(value)


class Plugin(BaseModel):
    id = AutoField()
    name = CharField()
    description = CharField()
    version = IntegerField()
    file_name = CharField()
    created_time = DateTimeField(default=datetime.now)

    class Meta:
        indexes = (
            (('name', 'version'), True),
        )
