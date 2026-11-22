"""纯逻辑单元测试，不依赖 pytest / flet 运行时。

运行：uv run python -m unittest discover -s tests -v
"""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import config

_TMP = tempfile.TemporaryDirectory()
config.APP_CONF_PATH = Path(_TMP.name) / 'config.json'
config.save_app_config({'WORK_DIR': _TMP.name})

import data.db as db_module  # noqa: E402
db_module.init_db()

from common.pagination import Pagination  # noqa: E402
from constant import OVERDUE, Priority, Status  # noqa: E402
from data.model import Job, Log, Task  # noqa: E402
from data.service import JobService, LogService, TaskService  # noqa: E402


class TestSchema(unittest.TestCase):
    def test_all_tables_created(self):
        tables = set(db_module.db.get_tables())
        self.assertTrue({'job', 'task', 'log', 'plugin'} <= tables)

    def test_tables_match_model_exactly(self):
        """库结构严格等于当前模型：无多余列、无缺失列、无残留表。

        运行时不做 schema 兼容，因此建出的表必须逐字段吻合模型定义。
        """
        from data.model import Job, Log, Plugin, Task  # noqa: F401
        models = (Job, Task, Log, Plugin)
        self.assertEqual(set(db_module.db.get_tables()),
                         {m._meta.table_name for m in models})
        for model in models:
            table = model._meta.table_name
            with self.subTest(table=table):
                cols = {c.name for c in db_module.db.get_columns(table)}
                fields = {f.column_name for f in model._meta.sorted_fields}
                self.assertEqual(cols, fields)

    def test_priority_is_text(self):
        job = JobService.create(f"优先级测试-{datetime.now().timestamp()}", '通用工作', priority='高')
        self.assertEqual(Job.get_by_id(job.id).priority, '高')

    def test_task_has_priority(self):
        job = JobService.create(f"任务字段测试-{datetime.now().timestamp()}", '通用工作')
        task = TaskService.create(job.id, 't', 'd', priority=Priority.HIGH)
        self.assertEqual(Task.get_by_id(task.id).priority, Priority.HIGH)


class TestAuditLog(unittest.TestCase):
    def setUp(self):
        self.job = JobService.create(f"审计测试-{datetime.now().timestamp()}", '通用工作')

    def test_related_files_roundtrip(self):
        log = LogService.create(self.job.id, '上传', '内容', ['a.pdf', 'b.png'])
        self.assertEqual(Log.get_by_id(log.id).related_files, ['a.pdf', 'b.png'])

    def test_empty_related_files_is_list(self):
        LogService.create(self.job.id, '事件')
        self.assertEqual(Log.get_by_id(LogService.query(self.job.id)[0].id).related_files, [])

    def test_legacy_dirty_json_is_safe(self):
        """历史库里 related_files='null'、position=NULL/'' 等脏数据必须安全兜底。"""
        log = LogService.create(self.job.id, '上传')
        log._related_files = 'null'   # 模拟老版本 bug 写入的脏值
        self.assertEqual(log.related_files, [])
        log._related_files = 'not-json'
        self.assertEqual(log.related_files, [])
        log._related_files = None
        self.assertEqual(log.related_files, [])
        task = TaskService.create(self.job.id, '脏数据任务')
        task._position = 'null'
        self.assertEqual(task.position.x, 0)
        self.assertEqual(task.position.downstreams, [])
        task._position = None
        self.assertEqual(task.position.x, 0)
        task._tags = 'null'
        self.assertEqual(task.tags, [])

    def test_auto_record_on_task_ops(self):
        task = TaskService.create(self.job.id, '任务X', 'd')
        self.assertIn('新建任务', [log.name for log in LogService.query(self.job.id)])
        TaskService.delete(task.id)
        self.assertIn('删除任务', [log.name for log in LogService.query(self.job.id)])

    def test_cascade_purge(self):
        """彻底删除才级联清理任务与日志；软删除仅移入回收站。"""
        TaskService.create(self.job.id, '任务Y', 'd')
        LogService.create(self.job.id, '记录')
        JobService.purge(self.job.id)
        self.assertEqual(Task.select().where(Task.job == self.job.id).count(), 0)
        self.assertEqual(Log.select().where(Log.job == self.job.id).count(), 0)

    def test_soft_delete_and_restore(self):
        job = JobService.create(f"回收站测试-{datetime.now().timestamp()}", '通用工作')
        task = TaskService.create(job.id, '任务Z', 'd')
        JobService.delete(job.id)
        self.assertIn(job.id, [j.id for j in JobService.recycle_bin()])
        self.assertNotIn(job.id, [j.id for j in JobService.query(
            __import__('common.pagination', fromlist=['Pagination']).Pagination(1, 100)).data])
        JobService.restore(job.id)
        self.assertNotIn(job.id, [j.id for j in JobService.recycle_bin()])
        TaskService.delete(task.id)
        self.assertIn(task.id, [t.id for t in TaskService.recycle_bin()])
        TaskService.restore(task.id)
        self.assertNotIn(task.id, [t.id for t in TaskService.recycle_bin()])


class TestBackup(unittest.TestCase):
    def test_export_import_roundtrip(self):
        job = JobService.create(f"备份测试-{datetime.now().timestamp()}", '通用工作')
        TaskService.create(job.id, '任务B', tags=['x', 'y'], assignee='李四', estimate_hours=5)
        from data.service import BackupService
        data = BackupService.export_json()
        self.assertEqual(data['version'], 1)
        counters = BackupService.import_json(data, merge=False)
        self.assertGreaterEqual(counters['jobs'], 1)
        self.assertGreaterEqual(counters['tasks'], 1)

    def test_task_extended_fields(self):
        job = JobService.create(f"扩展字段测试-{datetime.now().timestamp()}", '通用工作')
        task = TaskService.create(job.id, '任务C', tags=['a', 'b'], assignee='王五', estimate_hours=12)
        saved = Task.get_by_id(task.id)
        self.assertEqual(saved.tags, ['a', 'b'])
        self.assertEqual(saved.assignee, '王五')
        self.assertEqual(saved.estimate_hours, 12)

    def test_attachment_roundtrip(self):
        from data.service import AttachmentService
        job = JobService.create(f"附件测试-{datetime.now().timestamp()}", '通用工作')
        src = Path(_TMP.name) / 'att.txt'
        src.write_text('content', encoding='utf-8')
        names = AttachmentService.add_many(job.id, [type('F', (), {'path': str(src)})()])
        self.assertEqual(len(names), 1)
        self.assertTrue(AttachmentService.path_of(job.id, names[0]).exists())
        # 审计里能查到附件名
        self.assertIn(names[0], LogService.query(job.id)[0].related_files)
        AttachmentService.delete(job.id, names[0])
        self.assertFalse(AttachmentService.path_of(job.id, names[0]).exists())

    def test_plugin_meta_parsing(self):
        from pages.setting import _parse_meta
        plugin_file = Path(_TMP.name) / 'demo_plugin.py'
        plugin_file.write_text(
            'PLUGIN_NAME = "演示"\nPLUGIN_VERSION = 2\n'
            'PLUGIN_DESCRIPTION = "d"\ndef build(job):\n    return None\n',
            encoding='utf-8',
        )
        self.assertEqual(_parse_meta(plugin_file), ('演示', 2, 'd'))
        plugin_file.write_text('PLUGIN_NAME = "x"\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            _parse_meta(plugin_file)


class TestEnums(unittest.TestCase):
    def test_status_colors_complete(self):
        for status in Status.list():
            self.assertTrue(Status.color(status).startswith('#'), status)

    def test_overdue_distinct(self):
        self.assertNotIn(OVERDUE, Status.list())
        self.assertNotEqual(Status.color(OVERDUE), Status.color('不存在'))

    def test_legacy_status_normalized(self):
        """历史状态名必须归一化到现行枚举，避免图例出现重复状态。"""
        self.assertEqual(Status.normalize('待开始'), Status.NOT_START)
        self.assertEqual(Status.normalize('进行中'), Status.EXECUTING)
        self.assertEqual(Status.normalize('已暂停'), Status.BLOCKED)
        self.assertEqual(Status.color('进行中'), Status.color(Status.EXECUTING))

    def test_create_normalizes_status(self):
        job = JobService.create(
            f"归一化测试-{datetime.now().timestamp()}", '通用工作', status='进行中',
        )
        self.assertEqual(Job.get_by_id(job.id).status, Status.EXECUTING)


class TestPagination(unittest.TestCase):
    def test_total_page(self):
        self.assertEqual(Pagination(current=1, page_size=10, total=0).total_page, 0)
        self.assertEqual(Pagination(current=1, page_size=10, total=1).total_page, 1)
        self.assertEqual(Pagination(current=1, page_size=10, total=11).total_page, 2)

    def test_query_filter(self):
        name = f"分页测试-{datetime.now().timestamp()}"
        JobService.create(name, '通用工作', status=Status.EXECUTING)
        page = JobService.query(Pagination(current=1, page_size=100), keyword=name)
        self.assertGreaterEqual(page.total, 1)
        self.assertTrue(all(name in job.name for job in page.data))


class TestTrend(unittest.TestCase):
    def test_trend_has_today(self):
        trend = JobService.finish_trend(days=7)
        self.assertIn(datetime.now().strftime('%Y-%m-%d'), trend)

    def test_trend_length_equals_days(self):
        """折线图横坐标点数必须与所选天数一一对应（不含今天则多一天）。"""
        for days in (7, 15, 30):
            with self.subTest(days=days):
                for trend in (JobService.finish_trend(days=days),
                              TaskService.finish_trend(days=days)):
                    self.assertEqual(len(trend), days)
                    today = datetime.now().strftime('%Y-%m-%d')
                    self.assertIn(today, trend)
                    self.assertEqual(list(trend)[-1], today)


class TestLatestUpdates(unittest.TestCase):
    """首页「最新更新工作」改由审计日志驱动后的数据层约束。"""

    def test_legacy_update_fields_removed(self):
        """Job 上冗余的 updated_time / updated_content 字段已废弃。"""
        fields = {f.name for f in Job._meta.sorted_fields}
        self.assertNotIn('updated_time', fields)
        self.assertNotIn('updated_content', fields)

    def test_total_returns_plain_int(self):
        self.assertIsInstance(JobService.total(), int)
        self.assertIsInstance(TaskService.total(), int)

    def test_latest_updates_uses_latest_log_per_job(self):
        job = JobService.create(f"日志取数-{datetime.now().timestamp()}", '通用工作')
        LogService.record(job.id, '自定义动作', '详情')

        rows = LogService.latest_updates(limit=50)
        ids = [log.job_id for log in rows]
        self.assertEqual(len(ids), len(set(ids)), '每个工作只能出现一次')

        mine = [log for log in rows if log.job_id == job.id]
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0].name, '自定义动作', '应取该工作最新的一条日志')
        self.assertEqual(mine[0].job.name, job.name, '关联的工作必须可用（无额外字段依赖）')
        self.assertIsInstance(mine[0].created_time, datetime)

    def test_latest_updates_excludes_recycled_jobs(self):
        job = JobService.create(f"日志回收-{datetime.now().timestamp()}", '通用工作')
        LogService.record(job.id, '删除前的动作')
        JobService.delete(job.id)
        self.assertNotIn(job.id, [log.job_id for log in LogService.latest_updates(limit=50)])

    def test_latest_updates_ordered_by_log_time(self):
        rows = LogService.latest_updates(limit=50)
        times = [log.created_time for log in rows]
        self.assertEqual(times, sorted(times, reverse=True))

    def test_export_excludes_deprecated_fields(self):
        from data.service import BackupService
        data = BackupService.export_json()
        for row in data['jobs']:
            self.assertNotIn('updated_time', row)
            self.assertNotIn('updated_content', row)


class TestJobStatusDerivation(unittest.TestCase):
    def test_status_progress_follow_tasks(self):
        job = JobService.create(f"状态联动-{datetime.now().timestamp()}", '通用工作')
        t1 = TaskService.create(job.id, 'A')
        t2 = TaskService.create(job.id, 'B')
        self.assertEqual(JobService.get(job.id).status, Status.NOT_START)
        TaskService.update(t1.id, status=Status.EXECUTING)
        self.assertEqual(JobService.get(job.id).status, Status.EXECUTING)
        TaskService.update(t1.id, status=Status.FINISHED)
        TaskService.update(t2.id, status=Status.FINISHED)
        saved = JobService.get(job.id)
        self.assertEqual(saved.status, Status.FINISHED)
        self.assertEqual(saved.progress, 100)

    def test_no_task_is_not_start(self):
        job = JobService.create(f"空工作-{datetime.now().timestamp()}", '通用工作')
        self.assertEqual(JobService.get(job.id).status, Status.NOT_START)


class TestBackupInfo(unittest.TestCase):
    def test_parse_named_backup(self):
        from data.service import BackupService
        path = BackupService.backup('归档A')
        info = BackupService.backup_info(path)
        self.assertTrue(info['name'].startswith('归档A'))
        self.assertRegex(info['date'], r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$')
        self.assertGreater(info['size'], 0)


if __name__ == '__main__':
    unittest.main()
