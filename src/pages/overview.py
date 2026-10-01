import datetime

import flet as ft
from flet import TextAlign
from flet_charts import *

from src.common.util import datetime_2_date_str
from src.constant import *
from src.data.model import Job
from src.data.service import JobService, TaskService
from src.pages.job import COLOR_TEXT, BG_PANEL, BORDER_RADIUS


@ft.component
def overview():
    return ft.Column(
        [
            ft.Container(height=16),
            Top().build(),
            ft.Container(height=16),
            Center().build(),
            ft.Container(height=16),
            Bottom().build(),
        ],
        expand=True
    )


class Top:
    @staticmethod
    def build_card(title, value):
        return ft.Container(
            width=220, height=120, padding=16,
            border=ft.Border(
                left=ft.BorderSide(1, "#22d3ee88"),
                right=ft.BorderSide(1, "#22d3ee88"),
                top=ft.BorderSide(1, "#22d3ee88"),
                bottom=ft.BorderSide(1, "#22d3ee88"),
            ),
            border_radius=6,
            bgcolor="#111827",
            content=ft.Column(
                [
                    ft.Text(title, size=14, color="#94a3b8"),
                    ft.Text(str(value), size=40, weight=ft.FontWeight.BOLD, color="#22d3ee"),
                ],
                alignment=ft.MainAxisAlignment.CENTER
            ),
        )

    def build(self):
        # todo: 对比上周
        total_job_c, _ = JobService.total()
        finish_job, finish_job_7_day_before = JobService.total(status=Status.FINISHED)

        total_task_c, _ = TaskService.total()
        finish_task, finish_task_7_day_before = TaskService.total(status=Status.FINISHED)

        return ft.Row([
            self.build_card("工作总数", value=total_job_c),
            self.build_card("已完成工作", value=finish_job),
            self.build_card("任务总数", value=total_task_c),
            self.build_card("已完成任务", value=finish_task),
        ])


class Center:
    def build(self):
        return ft.Row([
            ft.Container(
                width=340,
                height=330,
                bgcolor="#111827",
                border_radius=8,
                padding=20,
                content=self.build_left(),
            ),
            ft.Container(
                expand=True,
                bgcolor=BG_PANEL,
                height=330,
                border_radius=BORDER_RADIUS,
                padding=20,
                # border=ft.border.all(1, "#254b80"),
                content=self.build_right(),
            )
        ], spacing=16)

    # 左边
    def build_left(self):
        # 悬浮样式
        hover_radius = 90
        hover_title_style = ft.TextStyle(size=14, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)

        def on_hover(e):
            for idx, s in enumerate(chart.sections):
                if idx == e.section_index:
                    s.radius = hover_radius
                    s.title_style = hover_title_style
                else:
                    s.radius = normal_radius
                    s.title_style = normal_title_style
            chart.update()

        chart = PieChart(
            sections=self.get_left_data(),
            # 扇区间隔缝隙
            sections_space=2,
            # 圆环：中间空白大小，0=实心饼图
            center_space_radius=40,
            # 中间文字
            # center_space=ft.Text("任务统计", color="#cbd5e1", size=14),
            # on_chart_event=on_hover,
            expand=True,
        )

        return ft.Column([
            ft.Text("任务分布饼图", color="#3b82f6", size=16, weight=ft.FontWeight.BOLD),
            chart
        ])

    def get_left_data(self):
        normal_radius = 80
        normal_title_style = ft.TextStyle(size=12, color=ft.Colors.WHITE)

        return [
            PieChartSection(value=value, title=status, color="#3b82f6", radius=normal_radius,
                            title_style=normal_title_style)
            for status, value in JobService.ratio().items()
        ]

    # 右边
    def build_right(self):
        return ft.Column(
            controls=[
                ft.Text("工作进展", size=16, color="#22d3ee"),
                LineChart(
                    data_series=[self.get_right_job_data(), self.get_right_task_data()],
                    left_axis=ChartAxis(labels=[], show_labels=False),
                    bottom_axis=ChartAxis(labels=self.get_right_labels()), min_x=0, max_x=TRENT_DAY, bgcolor="#0b1224",
                    # border=ft.border.all(1, "#254b80"),
                    height=250
                )
            ])

    def get_right_job_data(self):
        data = JobService.finish_trend()

        return LineChartData(
            points=[
                LineChartDataPoint(idx, value, tooltip=f'工作: {value}') for idx, value in enumerate(data.values())
            ],
            color=COLOR_JOB_FINISH,
            stroke_width=3,
            point=True,
            curved=True,
        )

    def get_right_task_data(self):
        data = TaskService.finish_trend(TRENT_DAY)

        return LineChartData(
            points=[
                LineChartDataPoint(idx, value, tooltip=f'任务: {value}') for idx, value in enumerate(data.values())
            ],
            color=COLOR_TASK_FINISH,
            stroke_width=3,
            point=True,
            curved=True
        )

    def get_right_labels(self):
        labels = []
        data = JobService.finish_trend(days=TRENT_DAY)

        for idx, day in enumerate(data.keys()):
            day = day.split("-")[-1]  # 取日
            l = ChartAxisLabel(value=idx, label=ft.Text(day, color=COLOR_TEXT, size=11))
            labels.append(l)

        return labels


class Bottom:
    def build(self):
        return ft.Row([  # 左下角：最新更新工作任务
            ft.Container(
                width=420,
                height=300,
                padding=16,
                border=ft.Border(
                    left=ft.BorderSide(1, "#22d3ee88"),
                    right=ft.BorderSide(1, "#22d3ee88"),
                    top=ft.BorderSide(1, "#22d3ee88"),
                    bottom=ft.BorderSide(1, "#22d3ee88"),
                ),
                border_radius=6,
                bgcolor="#111827",
                content=self.build_left()
            ),
            ft.Container(
                expand=True,
                height=300,
                padding=16,
                border=ft.Border(
                    left=ft.BorderSide(1, "#22d3ee88"),
                    right=ft.BorderSide(1, "#22d3ee88"),
                    top=ft.BorderSide(1, "#22d3ee88"),
                    bottom=ft.BorderSide(1, "#22d3ee88"),
                ),
                border_radius=6,
                bgcolor="#111827",
                content=self.build_right()
            )
        ], spacing=16)

    # 左边
    def build_left(self):
        return ft.Column([
            ft.Text("最新更新工作", size=16, color="#22d3ee"),
            ft.ListView(
                controls=[self.build_latest_job_row(job) for job in JobService.latest()],
                spacing=4,
            )
        ])

    def build_latest_job_row(self, job: Job):
        return ft.Container(
            data=job,
            on_click=lambda e: ft.context.page.navigate(f"/job/{job.id}"),
            padding=10,
            border_radius=4,  # hover_color="#1e293b",
            content=ft.Row([  # ft.Container(width=10, height=10, bgcolor=item["status_color"], border_radius=99),
                ft.Container(width=10, height=10, border_radius=99), ft.Container(width=10),
                ft.Column(
                    [
                        ft.Text(
                            job.name,
                            color="#22d3ee",
                            size=14,
                            weight=ft.FontWeight.W_500,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS
                        ),
                        ft.Text(
                            f"{job.type} | {datetime_2_date_str(job.updated_time, DATE_TIME_FMT)} | {job.updated_content}",
                            size=11,
                            color="#94a3b8"),
                    ],
                    expand=True),
                # ft.Text(job.status, size=12, color=item["status_color"]),
                ft.Text(job.status, size=12),
                ft.Icon(ft.Icons.ARROW_FORWARD_IOS, size=14, color="#64748b"),
            ]),
        )

    # 右边
    def build_right(self):
        return ft.Column([
            ft.Text("即将逾期工作", size=16, color="#22d3ee"),
            ft.Row([
                ft.Text("名称", size=12, color="#94a3b8", text_align=TextAlign.CENTER, width=160),
                ft.Text("类型", size=12, color="#94a3b8", text_align=TextAlign.CENTER, width=180),
                ft.Text("优先级", size=12, color="#94a3b8", text_align=TextAlign.CENTER, width=80),
                ft.Text("结束时间", size=12, color="#94a3b8", text_align=TextAlign.CENTER, width=140),
                ft.Text("剩余时长", size=12, color="#94a3b8", text_align=TextAlign.CENTER, width=100),
                ft.Text("状态", size=12, color="#94a3b8", text_align=TextAlign.CENTER, width=100),
                ft.Container(width=20),
            ]),
            ft.ListView(
                controls=[self.build_expire_job(job) for job in JobService.expire()],
                spacing=6,
            )
        ])

    def build_expire_job(self, job: Job):
        day = (job.end_time.date() - datetime.date.today()).days
        if day < 0:
            text, color = f"已逾期{-day}天", COLOR_DANGER
        elif day <= 3:
            text, color = str(day), COLOR_WARN
        else:
            text, color = str(day), COLOR_SAFE

        return ft.Row([
            ft.TextButton(
                job.name,
                width=160,
                on_click=lambda e: ft.context.page.navigate(f"/job/{job.id}")
            ),
            ft.Text(job.type, size=12, color="#cbd5e1", text_align=TextAlign.CENTER, width=180),
            ft.Text(job.priority, size=12, color="#cbd5e1", text_align=TextAlign.CENTER, width=80),
            ft.Text(job.end_time.strftime("%Y-%m-%d"), size=12, color="#cbd5e1", text_align=TextAlign.CENTER,
                    width=140),
            ft.Text(
                text,
                size=12,
                color=color,
                width=100,
                text_align=TextAlign.CENTER,
            ),
            ft.Text(job.status, size=12, color="#cbd5e1", text_align=TextAlign.CENTER, width=100),
            ft.Icon(ft.Icons.WARNING_AMBER, size=14, color=COLOR_WARN) if day < 3 else ft.Container(width=20),
        ])
