import json
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from common.pagination import Pagination
from common.util import datetime_2_date_str, cal_position, as_naive
from config import get_attachment_path, get_backup_path
from constant import (
    DEFAULT_JOB_END_DAY, TREND_DAY, Priority, Status,
)
from data.db import db
from data.model import Job, Task, Log, Plugin, Position

# 允许通过 update() 修改的业务字段（id/关联键/时间戳等由系统维护）
UPDATABLE_FIELDS = {
    'name', 'description', 'priority', 'status', 'start_time', 'end_time',
    'assignee', 'estimate_hours', 'tags',
}


def _changes(fields: dict) -> dict:
    """从入参里挑出允许更新且非 None 的字段。"""
    changed = {k: v for k, v in fields.items() if k in UPDATABLE_FIELDS and v is not None}
    # 时间统一归一为 naive，避免 DatePicker 的 aware 时间与 now() 混用导致比较崩溃
    for key in ('start_time', 'end_time'):
        if key in changed:
            changed[key] = as_naive(changed[key])
    # tags 是 Python 列表，批量 update 前需序列化为 JSON 字符串
    if 'tags' in changed and not isinstance(changed['tags'], str):
        changed['tags'] = json.dumps(changed['tags'], ensure_ascii=False)
    return changed


def _describe(changes: dict) -> str:
    """把字段变更拼成可读的审计描述。"""
    return '，'.join(f'{k} → {v}' for k, v in changes.items())


def _total(model, status: Optional[str]) -> int:
    """返回未删除的记录总数（软删除不计入统计）。"""
    condition = [model.deleted == False]  # noqa: E712
    if status:
        condition.append(model.status == Status.normalize(status))
    return model.select().where(*condition).count()


def _week_change(model, status: Optional[str] = None, field: str = 'created_time') -> int:
    """本周数量 - 上周数量（按自然周统计）。

    周一为一周起点；field 决定按哪个时间字段归属周次：
    总数按 created_time（新增），已完成按 end_time（完成）。
    返回值 > 0 表示比上周多，< 0 表示更少。用于大盘指标的"相比上周"环比值。
    """
    today = datetime.now().date()
    this_monday = today - timedelta(days=today.weekday())
    last_monday = this_monday - timedelta(days=7)
    time_field = getattr(model, field)

    def count_between(start: date, end: date) -> int:
        condition = [
            model.deleted == False,  # noqa: E712
            time_field >= datetime.combine(start, datetime.min.time()),
            time_field < datetime.combine(end, datetime.min.time()),
        ]
        if status:
            condition.append(model.status == Status.normalize(status))
        return model.select().where(*condition).count()

    return count_between(this_monday, today + timedelta(days=1)) - count_between(last_monday, this_monday)


class LogService:
    """审计日志：记录工作生命周期内的关键操作。"""

    @staticmethod
    def query(job_id: int) -> list[Log]:
        return list(Log.select().where(Log.job == job_id).order_by(Log.id.desc()))

    @staticmethod
    def latest_updates(limit: int = 10) -> list[Log]:
        """每个工作取最新的一条审计日志，按日志时间倒序返回。

        首页「最新更新工作」用：时间与动作都来自日志，不再依赖 Job 上
        冗余的更新时间/更新内容字段；同一工作只出现一次。
        """
        rows = (Log.select(Log, Job).join(Job)
                .where(Job.deleted == False)  # noqa: E712  回收站里的工作不展示
                .order_by(Log.created_time.desc(), Log.id.desc()))
        result: list[Log] = []
        seen: set[int] = set()
        for log in rows:
            if log.job_id in seen:
                continue
            seen.add(log.job_id)
            result.append(log)
            if len(result) >= limit:
                break
        return result

    @staticmethod
    def create(job_id: int, name: str, content: str = '',
               related_files: Optional[list[str]] = None) -> Log:
        log = Log(job_id=job_id, name=name, content=content)
        log.related_files = related_files or []  # 始终写 JSON，避免 '' 无法解析
        log.save()
        return log

    @staticmethod
    def record(job_id: int, action: str, detail: str = '', **kwargs):
        """供各 Service 调用的便捷埋点入口。"""
        return LogService.create(job_id, action, detail, **kwargs)


class JobService:
    @staticmethod
    def query(pagination: Pagination[Job], keyword: str = "", type: str = "",
              status: str = "") -> Pagination[Job]:
        q = Job.select().where(Job.deleted == False)  # noqa: E712
        if keyword:
            q = q.where(Job.name.contains(keyword))
        if type:
            q = q.where(Job.type == type)
        if status:
            q = q.where(Job.status == Status.normalize(status))

        pagination.total = q.count()
        pagination.data = list(
            q.order_by(Job.id.desc()).paginate(pagination.current, pagination.page_size)
        )
        return pagination

    @staticmethod
    def create(name: str, type: str, description: str = '',
               priority: str = Priority.LOW, status: str = Status.NOT_START,
               start_time: Optional[datetime] = None,
               end_time: Optional[datetime] = None) -> Job:
        now = datetime.now()
        job = Job.create(
            name=name, type=type, description=description, priority=priority,
            progress=0, status=Status.normalize(status),
            start_time=as_naive(start_time) or now,
            end_time=as_naive(end_time) or now + timedelta(days=DEFAULT_JOB_END_DAY),
        )
        LogService.record(job.id, '新建工作', f'类型：{type}，优先级：{priority}')
        return job

    @staticmethod
    def get(id: int) -> Job:
        return Job.get_by_id(id)

    @staticmethod
    def exists_name(name: str, exclude_id: Optional[int] = None) -> bool:
        """检查工作名是否已存在（新建/重命名时校验唯一性）。"""
        q = Job.select().where(Job.name == name)
        if exclude_id is not None:
            q = q.where(Job.id != exclude_id)
        return q.exists()

    @staticmethod
    def update(id: int, action: str = '更新工作', **fields):
        """按传入字段局部更新，并记录审计日志。"""
        changed = _changes(fields)
        if not changed:
            return
        if 'status' in changed:
            changed['status'] = Status.normalize(changed['status'])

        Job.update(**changed).where(Job.id == id).execute()
        LogService.record(id, action, _describe(changed))

    @staticmethod
    def delete(id: int):
        """软删除：移入回收站，任务与日志随之隐藏但保留，可还原。"""
        job = JobService.get(id)
        job.deleted = True
        job.save()
        LogService.record(id, '删除工作', job.name)

    @staticmethod
    def restore(id: int):
        job = JobService.get(id)
        job.deleted = False
        job.save()
        LogService.record(id, '还原工作', job.name)

    @staticmethod
    def purge(id: int):
        """彻底删除：清理工作本体及级联的任务、日志、附件目录。"""
        attachments = get_attachment_path(id)
        if attachments.exists():
            shutil.rmtree(attachments, ignore_errors=True)
        Job.delete_by_id(id)  # 外键 ON DELETE CASCADE 清理任务与日志

    @staticmethod
    def recycle_bin() -> list[Job]:
        return list(Job.select().where(Job.deleted == True).order_by(Job.id.desc()))  # noqa: E712

    @staticmethod
    def _derive_status(id: int, total: int, done: int) -> str:
        """按未删除任务聚合推导工作状态。

        全部完成 → 已完成；无任务 → 未开始；否则按优先级取最"活跃"的子状态：
        执行中 > 阻塞中 > 未开始。这样任务看板/编辑改状态后，工作页顶栏即时同步。
        """
        if total == 0:
            return Status.NOT_START
        if done == total:
            return Status.FINISHED
        statuses = {
            Status.normalize(t.status)
            for t in Task.select(Task.status).where(Task.job == id, Task.deleted == False)  # noqa: E712
        }
        for candidate in (Status.EXECUTING, Status.BLOCKED):
            if candidate in statuses:
                return candidate
        return Status.NOT_START

    @staticmethod
    def time_ranges(ids: list[int]) -> dict[int, tuple[Optional[datetime], Optional[datetime]]]:
        """按任务聚合工作起止时间：最早开始、最晚结束；无任务返回 (None, None)。"""
        result = {job_id: (None, None) for job_id in ids}
        if not ids:
            return result
        rows = Task.select(Task.job, Task.start_time, Task.end_time).where(
            Task.job.in_(ids), Task.deleted == False,  # noqa: E712
        )
        for task in rows:
            start, end = result.get(task.job_id, (None, None))
            # 历史库可能残留 DatePicker 写入的 aware 时间，比较前统一归一
            t_start, t_end = as_naive(task.start_time), as_naive(task.end_time)
            result[task.job_id] = (
                min(start, t_start) if start else t_start,
                max(end, t_end) if end else t_end,
            )
        return result

    @staticmethod
    def time_range(id: int) -> tuple[Optional[datetime], Optional[datetime]]:
        """单个工作的时间范围，便于详情页调用。"""
        return JobService.time_ranges([id])[id]

    @staticmethod
    def sync_progress(id: int):
        total = Task.select().where(Task.job == id, Task.deleted == False).count()  # noqa: E712
        done = Task.select().where(
            Task.job == id, Task.deleted == False, Task.status == Status.FINISHED,  # noqa: E712
        ).count()
        progress = int(done / total * 100) if total else 0
        status = JobService._derive_status(id, total, done)
        fields = {'progress': progress, 'status': status}
        start, end = JobService.time_range(id)
        if start and end:  # 有任务时同步，无任务保留默认时间
            fields.update(start_time=start, end_time=end)
        Job.update(**fields).where(Job.id == id).execute()

    @staticmethod
    def expire() -> list[Job]:
        """未完成且未来 7 天内到期（含已逾期）的工作。"""
        return list(Job.select().where(
            Job.deleted == False,  # noqa: E712
            Job.status != Status.FINISHED,
            Job.end_time < datetime.now() + timedelta(days=7),
        ).order_by(Job.end_time).limit(10))

    @staticmethod
    def total(status: Optional[str] = None) -> int:
        return _total(Job, status)

    @staticmethod
    def week_change(status: Optional[str] = None, field: str = 'created_time') -> int:
        """本周相对上周的数量差。field 决定归属周次的依据。"""
        return _week_change(Job, status, field)

    @staticmethod
    def finish_trend(days: int = TREND_DAY) -> dict[str, int]:
        return _daily_trend(Job, days)

    @staticmethod
    def ratio() -> dict[str, int]:
        result = {}
        for job in Job.select().where(Job.deleted == False, Job.status != Status.FINISHED):  # noqa: E712
            status = Status.normalize(job.status)
            result[status] = result.get(status, 0) + 1
        return result


class TaskService:
    @staticmethod
    def query(job_id: int) -> list[Task]:
        return list(Task.select().where(Task.job == job_id, Task.deleted == False))  # noqa: E712

    @staticmethod
    def filter(status: Optional[str] = None, start_time: Optional[datetime] = None,
               end_time: Optional[datetime] = None) -> list[Task]:
        q = Task.select().where(Task.deleted == False)  # noqa: E712
        if status:
            q = q.where(Task.status == Status.normalize(status))
        if start_time:
            q = q.where(Task.start_time >= start_time)
        if end_time:
            q = q.where(Task.end_time <= end_time)
        return list(q)

    @staticmethod
    def create(job_id: int, name: str, description: str = '',
               priority: str = Priority.LOW, status: str = Status.NOT_START,
               start_time: Optional[date] = None, end_time: Optional[date] = None,
               downstreams: Optional[list[int]] = None, assignee: str = '',
               estimate_hours: int = 0, tags: Optional[list[str]] = None) -> Task:
        now = datetime.now()
        x, y = cal_position(Task.select().where(Task.job == job_id).count())
        task = Task(
            job_id=job_id, name=name, description=description, priority=priority,
            status=Status.normalize(status), start_time=as_naive(start_time) or now,
            end_time=as_naive(end_time) or now + timedelta(days=DEFAULT_JOB_END_DAY),
            assignee=assignee or '', estimate_hours=estimate_hours or 0,
            position=Position(x=x, y=y, downstreams=downstreams or []),
        )
        task.tags = tags or []
        task.save()
        JobService.sync_progress(job_id)
        LogService.record(job_id, '新建任务', f'{name}（{priority}）')
        return task

    @staticmethod
    def get(id: int) -> Task:
        return Task.get_by_id(id)

    @staticmethod
    def update(id: int, action: str = '更新任务', **fields):
        """局部更新任务，同步工作进度并记录审计日志。"""
        changed = _changes(fields)
        if not changed:
            return
        if 'status' in changed:
            changed['status'] = Status.normalize(changed['status'])

        task = TaskService.get(id)
        Task.update(**changed).where(Task.id == id).execute()
        JobService.sync_progress(task.job_id)
        LogService.record(task.job_id, action, f'{task.name}：{_describe(changed)}')

    @staticmethod
    def delete(id: int):
        """软删除：任务移入回收站，同步进度并记录审计。"""
        task = TaskService.get(id)
        task.deleted = True
        task.save()
        JobService.sync_progress(task.job_id)
        LogService.record(task.job_id, '删除任务', task.name)

    @staticmethod
    def restore(id: int):
        task = TaskService.get(id)
        task.deleted = False
        task.save()
        JobService.sync_progress(task.job_id)
        LogService.record(task.job_id, '还原任务', task.name)

    @staticmethod
    def purge(id: int):
        """彻底删除任务本体。"""
        Task.delete_by_id(id)

    @staticmethod
    def recycle_bin() -> list[Task]:
        return list(Task.select().where(Task.deleted == True).order_by(Task.id.desc()))  # noqa: E712

    @staticmethod
    def total(status: Optional[str] = None) -> int:
        return _total(Task, status)

    @staticmethod
    def week_change(status: Optional[str] = None, field: str = 'start_time') -> int:
        """本周相对上周的数量差。Task 无 created_time，默认按 start_time 归属周次。"""
        return _week_change(Task, status, field)

    @staticmethod
    def finish_trend(days: int = TREND_DAY) -> dict[str, int]:
        return _daily_trend(Task, days)


class AttachmentService:
    """工作附件：真实落盘到工作目录，避免只登记文件名导致换机丢失。"""

    @staticmethod
    def add(job_id: int, src: str | Path) -> str:
        """复制一个文件到工作附件目录，返回存档后的文件名。重名自动加序号。"""
        src = Path(src)
        folder = get_attachment_path(job_id)
        name = src.name
        target = folder / name
        if target.exists():
            stem, suffix = target.stem, target.suffix
            idx = 1
            while (folder / f'{stem}_{idx}{suffix}').exists():
                idx += 1
            name = f'{stem}_{idx}{suffix}'
            target = folder / name
        shutil.copy2(src, target)
        return name

    @staticmethod
    def add_many(job_id: int, files: list) -> list[str]:
        names = []
        for f in files:
            path = getattr(f, 'path', None)
            if not path:
                continue
            try:
                names.append(AttachmentService.add(job_id, path))
            except OSError:
                continue
        if names:
            LogService.record(job_id, '上传附件', f'新增 {len(names)} 个文件',
                              related_files=names)
        return names

    @staticmethod
    def path_of(job_id: int, name: str) -> Path:
        return get_attachment_path(job_id) / name

    @staticmethod
    def delete(job_id: int, name: str):
        path = AttachmentService.path_of(job_id, name)
        if path.exists():
            path.unlink()

    @staticmethod
    def record_delete(job_id: int, name: str):
        """删除附件后同步从审计记录的 related_files 中移除。"""
        for log in LogService.query(job_id):
            if name in log.related_files:
                log.related_files = [f for f in log.related_files if f != name]
                log.save()


def _daily_trend(model, days: int) -> dict[str, int]:
    """统计最近 days 天（含今天）每天完成的数量，按日期升序返回。"""
    today = datetime.now().date()
    start = today - timedelta(days=days - 1)
    result = {datetime_2_date_str(datetime.combine(start + timedelta(days=i), datetime.min.time())): 0
              for i in range(days)}

    rows = model.select().where(
        model.deleted == False,  # noqa: E712
        model.status == Status.FINISHED,
        model.end_time >= datetime.combine(start, datetime.min.time()),
        model.end_time <= datetime.combine(today, datetime.max.time()),
    )
    for row in rows:
        key = datetime_2_date_str(row.end_time)
        if key in result:
            result[key] += 1
    return result


class PluginService:
    @staticmethod
    def create(name: str, version: int, description: str, file_name: str):
        return Plugin.create(name=name, version=version,
                             description=description, file_name=file_name)

    @staticmethod
    def update(id: int, version: int):
        Plugin.update(version=version).where(Plugin.id == id).execute()

    @staticmethod
    def list() -> list[Plugin]:
        return list(Plugin.select().order_by(Plugin.id.desc()))

    @staticmethod
    def query(name: str, version: Optional[int] = None) -> Optional[Plugin]:
        q = Plugin.select().where(Plugin.name == name)
        if version is not None:
            q = q.where(Plugin.version == version)
        return q.get_or_none()

    @staticmethod
    def delete(id: int):
        Plugin.delete_by_id(id)


class BackupService:
    """数据备份与迁移：整库快照 + 业务数据 JSON 导入导出。"""

    @staticmethod
    def backup(name: str = 'sqlite') -> Path:
        """生成一份整库快照，返回备份文件路径。

        文件名格式：<安全名称>_<YYYYMMDD_HHMMSS>.db，UI 据此拆分出名称与日期。
        """
        import re
        folder = get_backup_path()
        safe = re.sub(r'[^\w\u4e00-\u9fff-]', '_', (name or '').strip()) or 'sqlite'
        dest = folder / f'{safe}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
        # SQLite 在线备份：用连接句柄复制，避免写事务中直接拷贝文件损坏
        source = db.connection()
        target = __import__('sqlite3').connect(str(dest))
        source.backup(target)
        target.close()
        return dest

    @staticmethod
    def backup_info(path: Path) -> dict:
        """从备份文件名解析出 {name, date, size}，供列表展示。"""
        import re
        stem = path.stem
        m = re.match(r'^(.*)_(\d{8}_\d{6})$', stem)
        if m:
            name, raw_time = m.group(1), m.group(2)
            date = datetime.strptime(raw_time, '%Y%m%d_%H%M%S').strftime('%Y-%m-%d %H:%M')
        else:
            name, date = stem, datetime.fromtimestamp(path.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
        return {'name': name, 'date': date, 'size': path.stat().st_size, 'path': path}

    @staticmethod
    def list_backups() -> list[Path]:
        return sorted(
            (p for p in get_backup_path().glob('*.db')),
            key=lambda p: p.stat().st_mtime, reverse=True,
        )

    @staticmethod
    def restore(path: Path):
        """用备份覆盖当前库。恢复前需调用方确认，并提示重启应用。"""
        if not path.exists():
            raise FileNotFoundError(f'备份文件不存在：{path}')
        target = db.connection()
        source = __import__('sqlite3').connect(str(path))
        source.backup(target)
        source.close()

    # 外键字段 → 存 id 的列名，导入时按此白名单还原，避免把导出元字段误写入
    _EXPORT_MODELS = (
        ('jobs', Job, ('id', 'type', 'name', 'description', 'progress', 'priority', 'status',
                       'start_time', 'end_time', 'created_time', 'deleted')),
        ('tasks', Task, ('id', 'job_id', 'name', 'description', 'priority', 'status',
                         'start_time', 'end_time', 'assignee', 'estimate_hours',
                         'tags', 'deleted', '_position')),
        ('logs', Log, ('id', 'job_id', 'name', 'content', 'created_time', 'related_files')),
    )

    @staticmethod
    def export_json() -> dict:
        """导出全部业务数据为可序列化结构。"""
        result = {
            'version': 1,
            'exported_at': datetime.now().isoformat(timespec='seconds'),
        }
        for key, model, fields in BackupService._EXPORT_MODELS:
            rows = []
            for obj in model.select():
                row = {}
                for name in fields:
                    value = getattr(obj, name)
                    # 时间对象序列化为 ISO 字符串；_position/tags/related_files
                    # 本身就是 JSON 字符串，直接落盘
                    if isinstance(value, datetime):
                        value = value.isoformat(timespec='seconds')
                    row[name] = value
                rows.append(row)
            result[key] = rows
        return result

    @staticmethod
    def import_json(data: dict, merge: bool = True) -> dict:
        """从 JSON 导入业务数据。merge=False 时先清空现有数据。返回导入条数。"""
        if not isinstance(data, dict) or 'jobs' not in data:
            raise ValueError('不是有效的备份文件')
        counters = {'jobs': 0, 'tasks': 0, 'logs': 0}
        field_map = {key: (model, fields)
                     for key, model, fields in BackupService._EXPORT_MODELS}
        # 保留原始主键，让 task/log 的 job_id 外键天然对得上；
        # 合并模式下若 id 已占用则跳过该条及其子记录。
        skip_jobs: set[int] = set()
        with db.atomic():
            if not merge:
                Log.delete().execute()
                Task.delete().execute()
                Job.delete().execute()
            for key in ('jobs', 'tasks', 'logs'):
                model, allowed = field_map[key]
                for raw in data.get(key, []) or []:
                    fields = {k: v for k, v in raw.items() if k in allowed}
                    rid = fields.pop('id', None)
                    if key == 'jobs':
                        if merge and rid is not None and model.get_or_none(model.id == rid):
                            skip_jobs.add(rid)
                            continue
                    else:
                        if fields.get('job_id') in skip_jobs:
                            continue
                    # tags / related_files 是 JSON property，setter 期望 list
                    for jf in ('tags', 'related_files'):
                        if jf in fields and isinstance(fields[jf], str):
                            try:
                                fields[jf] = json.loads(fields[jf])
                            except (ValueError, TypeError):
                                fields[jf] = []
                    # 时间字段是 ISO 字符串 → datetime
                    for tf in ('start_time', 'end_time', 'created_time'):
                        if tf in fields and isinstance(fields[tf], str):
                            fields[tf] = datetime.fromisoformat(fields[tf])
                    obj = model(**fields)
                    if rid is not None:
                        obj.id = rid
                    obj.save(force_insert=True)
                    counters[key] += 1
        return counters
