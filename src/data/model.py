import json

from peewee import AutoField, CharField, DateTimeField, ForeignKeyField

from src.data.db import BaseModel


class Job(BaseModel):
    id = AutoField()
    type = CharField()
    name = CharField(unique=True)
    comment = CharField()
    priority = CharField()
    status = CharField()
    start_time = DateTimeField()
    end_time = DateTimeField()

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
    comment = CharField()
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
