from datetime import datetime, timedelta, date
from typing import Optional

from peewee import SQL

from src.common.pagination import Pagination
from src.common.util import datetime_2_date_str
from src.config import DEFAULT_JOB_END_DAY
from src.constant import Priority, Status
from src.data.model import Job, Task, Log


class JobService:
    @staticmethod
    def query(pagination: Pagination[Job], keyword: str = "", type: str = "", status: str = "") -> Pagination[Job]:
        q = Job.select()
        if keyword:
            q = q.where(Job.name.contains(keyword))

        if type:
            q = q.where(Job.type == type)

        if status:
            q = q.where(Job.status == status)

        pagination.total = q.count()
        pagination.data = list(q.paginate(pagination.current, pagination.page_size))
        return pagination

    @staticmethod
    def create(name: str, type: str, description: str, priority: str = Priority.LOW, status: str = Status.NOT_START,
               start_time: datetime = None, end_time: datetime = None) -> Job:
        if not start_time:
            start_time = datetime.now()

        if not end_time:
            end_time = datetime.now() + timedelta(days=DEFAULT_JOB_END_DAY)

        job = Job(name=name, type=type, description=description, priority=priority, progress=0, status=status,
                  start_time=start_time, end_time=end_time, updated_content='新建工作')
        job.save()
        return job

    @staticmethod
    def get(id: int) -> Job:
        return Job.get(Job.id == id)

    def update(self, id: int, name: Optional[str] = None, description: Optional[str] = None,
               priority: Optional[str] = None, status: Optional[str] = None, start_time: Optional[date] = None,
               end_time: Optional[date] = None, updated_content: Optional[str] = None):
        job = self.get(id)

        if name is not None:
            job.name = name

        if description is not None:
            job.description = description

        if priority is not None:
            job.priority = priority

        if status is not None:
            job.status = status

        if start_time is not None:
            job.start_time = start_time

        if end_time is not None:
            job.end_time = end_time

        if updated_content is not None:
            job.updated_content = updated_content

        job.save()

    @staticmethod
    def delete(id: int):
        Job.delete_by_id(id)

    @staticmethod
    def latest() -> list[Job]:
        return list(Job.select().order_by(Job.updated_time.desc()).limit(10))

    @staticmethod
    def expire() -> list[Job]:
        return list(Job.select().where(
            Job.status != Status.FINISHED,
            Job.end_time > datetime.now() - timedelta(days=7),
        ).order_by(Job.end_time).limit(10))

    @staticmethod
    def total(status: Optional[str] = None) -> tuple[int, int]:
        """工作总数，7天前总数"""
        condition = [SQL("1=1")]
        if status:
            condition.append(Job.status == status)

        c1 = Job.select().where(*condition).count()
        c2 = Job.select().where(
            *condition, Job.updated_time < datetime.now() - timedelta(days=7)
        ).count()
        return c1, c2

    @staticmethod
    def finish_trend( days: int=7) -> dict[str, int]:
        jobs = Job.select().where(
            Job.status == Status.FINISHED,
            Job.end_time > datetime.now() - timedelta(days=days),
            Job.end_time < datetime.now()
        )
        r={}
        for i in range(-7,0):
            day = datetime.now()+timedelta(days=i)
            r.setdefault(datetime_2_date_str(day), 0)

        for job in jobs:
            day = datetime_2_date_str(job.end_time)
            r[day] +=1

        return r

    @staticmethod
    def ratio() -> dict[str, int]:
        jobs = Job.select().where(
            Job.status != Status.FINISHED,
        )
        r = {}
        for job in jobs:
            r.setdefault(job.status, 0)
            r[job.status] += 1

        return r

class TaskService:
    @staticmethod
    def query() -> list[Task]:
        return list(Task.select())

    @staticmethod
    def create(job_id: int, name: str, description: str, priority: str = Priority.LOW, status: str = Status.NOT_START,
               start_time: date = None, end_time: date = None, ):
        if not start_time:
            start_time = datetime.now()
        if not end_time:
            end_time = datetime.now() + timedelta(days=DEFAULT_JOB_END_DAY)

        task = Task(job_id=job_id, name=name, description=description, priority=priority, status=status,
                    start_time=start_time, end_time=end_time, )
        task.save()
        return task

    @staticmethod
    def get(id: int) -> Task:
        return Task.get(Task.id == id)

    @staticmethod
    def update(id: int, name: Optional[str] = None, description: Optional[str] = None, priority: Optional[str] = None,
               status: Optional[str] = None, start_time: date = None, end_time: date = None, ):

        task = TaskService.get(id)
        if name is not None:
            task.name = name

        if description is not None:
            task.description = description

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

    @staticmethod
    def total(status: Optional[str] = None) -> tuple[int, int]:
        """任务总数，7天前总数"""
        condition = [SQL("1=1")]
        if status:
            condition.append(Task.status == status)

        c1 = Task.select().where(*condition).count()
        c2 = Task.select().where(
            *condition, Task.end_time < datetime.now() - timedelta(days=7)
        ).count()
        return c1, c2

    @staticmethod
    def finish_trend( days: int=7) -> dict[str, int]:
        tasks = Task.select().where(
            Task.status == Status.FINISHED,
            Task.end_time > datetime.now() - timedelta(days=days),
            Task.end_time < datetime.now()
        )
        r={}
        for i in range(-7,0):
            day = datetime.now()+timedelta(days=i)
            r.setdefault(datetime_2_date_str(day), 0)

        for task in tasks:
            day = datetime_2_date_str(task.end_time)
            r[day] +=1

        return r


class LogService:
    @staticmethod
    def query(job_id: int) -> list[Log]:
        return list(Log.select().where(Log.job == job_id).order_by(Log.id.desc()))

    @staticmethod
    def create(job_id: int, name: str, content: str, related_files: Optional[list[str]] = None, ):
        log = Log(job_id=job_id, name=name, content=content)
        if related_files is None:
            log.related_files = related_files

        log.save()
        return log
