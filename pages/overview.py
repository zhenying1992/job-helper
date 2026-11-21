import datetime

import flet as ft
from flet import TextAlign
from flet_charts import *

from common.util import datetime_2_date_str
from constant import *  # noqa: F403  枚举/日期格式/统计参数
from data.model import Job
from data.service import JobService, TaskService
from theme import (
    BG_CARD, BG_CHART, BORDER_ACCENT, MUTED, ACCENT, SLATE, TEXT_BRIGHT,
    FS_BASE, FS_METRIC, FS_XL, FS_MD, FS_SM, glow, GLOW_SOFT,
    RADIUS_MD, FONT_MONO,
)


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
                left=ft.BorderSide(1, BORDER_ACCENT),
                right=ft.BorderSide(1, BORDER_ACCENT),
                top=ft.BorderSide(1, BORDER_ACCENT),
                bottom=ft.BorderSide(1, BORDER_ACCENT),
            ),
            border_radius=RADIUS_MD,
            bgcolor=BG_CARD,
            shadow=glow(GLOW_SOFT, blur=20),
            content=ft.Column(
                [
                    ft.Text(title, size=FS_BASE, color=MUTED),
                    ft.Text(str(value), size=FS_METRIC, weight=ft.FontWeight.BOLD,
                            color=ACCENT, font_family=FONT_MONO),
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
                bgcolor=BG_CARD,
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
                content=self.build_right(),
            )
        ], spacing=16)

    # 左边
    normal_radius = 80
    hover_radius = 90
    normal_title_style = ft.TextStyle(size=FS_MD, color=TEXT_BRIGHT)
    hover_title_style = ft.TextStyle(size=FS_BASE, color=TEXT_BRIGHT, weight=ft.FontWeight.BOLD)

    def build_left(self):
        chart = PieChart(
            sections=self.get_left_data(),
            sections_space=2,
            center_space_radius=40,
            expand=True,
        )

        def on_hover(e):
            for idx, section in enumerate(chart.sections):
                active = idx == e.section_index
                section.radius = self.hover_radius if active else self.normal_radius
                section.title_style = self.hover_title_style if active else self.normal_title_style
            chart.update()

        chart.on_chart_event = on_hover

        return ft.Column([
            ft.Text("任务分布饼图", color=COLOR_PRIMARY, size=FS_XL, weight=ft.FontWeight.BOLD),
            chart,
        ])

    def get_left_data(self):
        return [
            PieChartSection(value=value, title=status, color=Status.color(status),
                            radius=self.normal_radius, title_style=self.normal_title_style)
            for status, value in JobService.ratio().items()
        ]

    # 右边
    def build_right(self):
        return ft.Column(
            controls=[
                ft.Text("工作进展", size=FS_XL, color=ACCENT),
                LineChart(
                    data_series=[self.get_right_job_data(), self.get_right_task_data()],
                    left_axis=ChartAxis(labels=[], show_labels=False),
                    bottom_axis=ChartAxis(labels=self.get_right_labels()), min_x=0, max_x=TREND_DAY, bgcolor=BG_CHART,
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
        data = TaskService.finish_trend(TREND_DAY)

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
        data = JobService.finish_trend(days=TREND_DAY)

        for idx, day in enumerate(data.keys()):
            day = day.split("-")[-1]  # 取日
            l = ChartAxisLabel(value=idx, label=ft.Text(day, color=COLOR_TEXT, size=FS_SM))
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
                    left=ft.BorderSide(1, BORDER_ACCENT),
                    right=ft.BorderSide(1, BORDER_ACCENT),
                    top=ft.BorderSide(1, BORDER_ACCENT),
                    bottom=ft.BorderSide(1, BORDER_ACCENT),
                ),
                border_radius=6,
                bgcolor=BG_CARD,
                content=self.build_left()
            ),
            ft.Container(
                expand=True,
                height=300,
                padding=16,
                border=ft.Border(
                    left=ft.BorderSide(1, BORDER_ACCENT),
                    right=ft.BorderSide(1, BORDER_ACCENT),
                    top=ft.BorderSide(1, BORDER_ACCENT),
                    bottom=ft.BorderSide(1, BORDER_ACCENT),
                ),
                border_radius=6,
                bgcolor=BG_CARD,
                content=self.build_right()
            )
        ], spacing=16)

    # 左边
    def build_left(self):
        return ft.Column([
            ft.Text("最新更新工作", size=FS_XL, color=ACCENT),
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
            border_radius=4,
            content=ft.Row([
                ft.Container(width=10, height=10, border_radius=99), ft.Container(width=10),
                ft.Column(
                    [
                        ft.Text(
                            job.name,
                            color=ACCENT,
                            size=FS_BASE,
                            weight=ft.FontWeight.W_500,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS
                        ),
                        ft.Text(
                            f"{job.type} | {datetime_2_date_str(job.updated_time, DATE_TIME_FMT)} | {job.updated_content}",
                            size=FS_SM,
                            color=MUTED),
                    ],
                    expand=True),
                ft.Text(job.status, size=FS_MD),
                ft.Icon(ft.Icons.ARROW_FORWARD_IOS, size=FS_BASE, color=SLATE),
            ]),
        )

    # 右边
    def build_right(self):
        return ft.Column([
            ft.Text("即将逾期工作", size=FS_XL, color=ACCENT),
            ft.Row([
                ft.Text(h, size=FS_MD, color=MUTED, text_align=TextAlign.CENTER, width=w)
                for h, w in (("名称", 160), ("类型", 180), ("优先级", 80),
                             ("结束时间", 140), ("剩余时长", 100), ("状态", 100))
            ] + [ft.Container(width=20)]),
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
            ft.Container(
                width=160,
                tooltip=job.name,
                on_click=lambda e: ft.context.page.navigate(f"/job/{job.id}"),
                content=ft.Text(
                    job.name,
                    size=FS_MD,
                    color=ACCENT,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
            ),
            ft.Text(job.type, size=FS_MD, color=COLOR_TEXT, text_align=TextAlign.CENTER, width=180),
            ft.Text(job.priority, size=FS_MD, color=COLOR_TEXT, text_align=TextAlign.CENTER, width=80),
            ft.Text(job.end_time.strftime("%Y-%m-%d"), size=FS_MD, color=COLOR_TEXT, text_align=TextAlign.CENTER,
                    width=140),
            ft.Text(
                text,
                size=FS_MD,
                color=color,
                width=100,
                text_align=TextAlign.CENTER,
            ),
            ft.Text(job.status, size=FS_MD, color=COLOR_TEXT, text_align=TextAlign.CENTER, width=100),
            ft.Icon(ft.Icons.WARNING_AMBER, size=FS_BASE, color=COLOR_WARN) if day < 3 else ft.Container(width=20),
        ])
