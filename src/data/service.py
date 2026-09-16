from datetime import datetime, timedelta
from typing import Optional

from src.config import DEFAULT_JOB_END_DAY
from src.constant import Priority, Status
from src.data.model import Job, Task, Log


class JobService:
    @staticmethod
    def query() -> list[Job]:
        return list(Job.select())

    @staticmethod
    def create(name: str, type: str, comment: str, priority: str = Priority.LOW, status: str = Status.NOT_START,
            start_time: datetime = None, end_time: datetime = None, ) -> Job:
        if not start_time:
            start_time = datetime.now()

        if not end_time:
            end_time = datetime.now() + timedelta(days=DEFAULT_JOB_END_DAY)

        job = Job(name=name, type=type, comment=comment, priority=priority, status=status, start_time=start_time,
            end_time=end_time, )
        job.save()
        return job

    @staticmethod
    def get(id: int) -> Job:
        return Job.get(Job.id == id)

    def update(self, id: int, name: Optional[str] = None, comment: Optional[str] = None, priority: Optional[str] = None,
            status: Optional[str] = None, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None, ):
        job = self.get(id)

        if name is not None:
            job.name = name

        if comment is not None:
            job.comment = comment

        if priority is not None:
            job.priority = priority

        if status is not None:
            job.status = status

        if start_time is not None:
            job.start_time = start_time

        if end_time is not None:
            job.end_time = end_time

        job.save()

    @staticmethod
    def delete(id: int):
        Job.delete_by_id(id)


class TaskService:
    @staticmethod
    def query() -> list[Task]:
        return list(Task.select())

    @staticmethod
    def create(job_id: int, name: str, comment: str, priority: str = Priority.LOW, status: str = Status.NOT_START,
            start_time: datetime = None, end_time: datetime = None, ):
        if not start_time:
            start_time = datetime.now()
        if not end_time:
            end_time = datetime.now() + timedelta(days=DEFAULT_JOB_END_DAY)

        task = Task(job_id=job_id, name=name, comment=comment, priority=priority, status=status, start_time=start_time,
            end_time=end_time, )
        task.save()
        return task

    @staticmethod
    def get(id: int) -> Task:
        return Task.get(Task.id == id)

    def update(self, id: int, name: Optional[str] = None, comment: Optional[str] = None, priority: Optional[str] = None,
            status: Optional[str] = None, start_time: datetime = None, end_time: datetime = None, ):
        task = self.get(id)
        if name is not None:
            task.name = name

        if comment is not None:
            task.comment = comment

        if priority is not None:
            task.priority = priority

        if status is not None:
            task.status = status

        if start_time is not None:
            task.start_time = start_time

        if end_time is not None:
            task.end_time = end_time

        task.save()

    @staticmethod
    def delete(id: int):
        Task.delete_by_id(id)


class LogService:
    @staticmethod
    def query(job_id: int) -> list[Log]:
        return list(Log.select().where(Log.job == job_id))

    @staticmethod
    def create(job_id: int, name: str, content: str, related_files: Optional[list[str]] = None, ):
        log = Log(job_id=job_id, name=name, content=content, )
        if related_files is None:
            related_files = []

        log.files = related_files

        log.save()
        return log
