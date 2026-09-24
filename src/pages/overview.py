import datetime

import flet as ft
from flet_charts import *

from src.constant import Status
from src.data.model import Job
from src.data.service import JobService, TaskService
from src.pages.job import COLOR_TEXT, BG_PANEL, BORDER_RADIUS

@ft.component
def overview():

    def folder_panel():
        async def handle_get_directory_path(e: ft.Event[ft.Button]):
            a = await ft.FilePicker().get_directory_path()
            print(a)
            # directory_path.value = await ft.FilePicker().get_directory_path()

        return ft.Row(
                controls=[
                    ft.Button(
                        content="Open directory",
                        icon=ft.Icons.FOLDER_OPEN,
                        on_click=handle_get_directory_path,
                        # disabled=page.web,  # disable this button in web mode
                    ),
                    directory_path := ft.Text(),
                ]
            )

    return ft.Column(
        [
            folder_panel(),
            ft.Container(height=16),
         build_top(),
         ft.Container(height=16),
         get_center(),
         ft.Container(height=16),
         get_bottom_row()],
        expand=True)


def tech_card(title, value, sub_text):
    return ft.Container(width=360, height=220, padding=20, border_radius=12,  # 四边边框，0.86.5 兼容写法
                        border=ft.Border(top=ft.BorderSide(1, "#4488FF33"), bottom=ft.BorderSide(1, "#4488FF33"),
                                         left=ft.BorderSide(1, "#4488FF33"), right=ft.BorderSide(1, "#4488FF33"), ),
                        gradient=ft.LinearGradient(  # begin=ft.Alignment.top_left,
                            # end=ft.Alignment.bottom_right,
                            colors=["#0f1933", "#081022"]),
                        shadow=ft.BoxShadow(blur_radius=20, spread_radius=1, color="#2178FF40"), content=ft.Column(
            [ft.Text(title, size=16, color="#96b8e8"),
             ft.Text(value, size=42, weight=ft.FontWeight.BOLD, color="#ffffff",
                     # shadow=ft.BoxShadow(blur_radius=8, color="#4488FF")
                     ), ft.Text(sub_text, size=13, color="#6989b9"), ], spacing=12))


def build_top():
    # todo: 对比上周
    total_job_c, _ = JobService.total()
    finish_job, finish_job_7_day_before = JobService.total(status=Status.FINISHED)

    total_task_c, _ = TaskService.total()
    finish_task, finish_task_7_day_before = TaskService.total(status=Status.FINISHED)

    def build_kpi_card(title, value):
        return ft.Container(width=220, height=120, padding=16,
                            border=ft.Border(left=ft.BorderSide(1, "#22d3ee88"), right=ft.BorderSide(1, "#22d3ee88"),
                                             top=ft.BorderSide(1, "#22d3ee88"), bottom=ft.BorderSide(1, "#22d3ee88"), ),
                            border_radius=6, bgcolor="#111827", content=ft.Column(
                [ft.Text(title, size=14, color="#94a3b8"),
                 ft.Text(str(value), size=40, weight=ft.FontWeight.BOLD, color="#22d3ee"), ],
                alignment=ft.MainAxisAlignment.CENTER), )

    return ft.Row([build_kpi_card("工作总数", value=total_job_c), build_kpi_card("已完成工作", value=finish_job),
                   build_kpi_card("任务总数", value=total_task_c), build_kpi_card("已完成任务", value=finish_task),

                   ])


# ---------------------- 点击跳转事件 ----------------------
def get_center():
    # 中间区域：左【任务状态环形图】 + 右【完成趋势图】
    def pie_chart_demo():
        # 悬浮样式
        normal_radius = 80
        hover_radius = 90
        normal_title_style = ft.TextStyle(size=12, color=ft.Colors.WHITE)
        hover_title_style = ft.TextStyle(size=14, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)

        def get_data():
            return [
                PieChartSection(value=value, title=status, color="#3b82f6", radius=normal_radius,
                                title_style=normal_title_style)
                for status, value in JobService.ratio().items()
            ]

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
            sections=get_data(),
            # 扇区间隔缝隙
            sections_space=2,
            # 圆环：中间空白大小，0=实心饼图
            center_space_radius=40,
            # 中间文字
            # center_space=ft.Text("任务统计", color="#cbd5e1", size=14),
            # on_chart_event=on_hover,
            expand=True,
        )

        return ft.Container(
            width=340,
            bgcolor="#1e293b",
            border_radius=8,
            padding=20,
            content=ft.Column([
                ft.Text("任务分布饼图", color="#3b82f6", size=16, weight=ft.FontWeight.BOLD),
                chart
            ])
        )

    ####

    data = JobService.finish_trend()
    task = TaskService.finish_trend()

    def get_data():
        return [LineChartData(
            points=[
                LineChartDataPoint(idx, value, tooltip=str(value))
                for idx, value in enumerate(data.values())
            ], color="#22c55e", stroke_width=3, point=True, curved=True),

            LineChartData(
                points=[
                    LineChartDataPoint(idx, value, tooltip=str(value))
                    for idx, value in enumerate(task.values())
                ], color="#ef4444", stroke_width=3, point=True, curved=True)
        ]

    def get_labels():
        labels = []
        for idx, day in enumerate(data.keys()):
            l = ChartAxisLabel(value=idx, label=ft.Text(day, color=COLOR_TEXT, size=11))
            labels.append(l)

        return labels

    line = LineChart(data_series=get_data(), left_axis=ChartAxis(labels=[], show_labels=False),
                     bottom_axis=ChartAxis(labels=get_labels(), ), min_x=0, max_x=7, bgcolor="#0b1224",
                     # border=ft.border.all(1, "#254b80"),
                     height=220)
    return ft.Row([  # 任务状态分布卡片（替换PieChart，纯文本图例面板）
        pie_chart_demo(),
        ft.Container(expand=True, bgcolor=BG_PANEL, border_radius=BORDER_RADIUS, padding=20,
                     # border=ft.border.all(1, "#254b80"),
                     content=ft.Column(
                         controls=[ft.Text("工作进展", size=16, color="#22d3ee"), ft.Container(height=30),  # 占位,
                                   line], expand=True))

    ], spacing=16)


def get_bottom_row():
    # 最新更新工作条目（可点击跳转）
    def build_latest_job_row(job: Job):
        return ft.Container(data=job, on_click=lambda e: ft.context.page.navigate(f"/job/{job.id}"), padding=10,
                            border_radius=4,  # hover_color="#1e293b",
                            content=ft.Row(
                                [  # ft.Container(width=10, height=10, bgcolor=item["status_color"], border_radius=99),
                                    ft.Container(width=10, height=10, border_radius=99), ft.Container(width=10),
                                    ft.Column([ft.Text(job.name, color="#22d3ee", size=14, weight=ft.FontWeight.W_500),
                                               ft.Text(f"{job.type} | {job.updated_time} | {job.updated_content}",
                                                       size=11, color="#94a3b8"), ], expand=True),
                                    # ft.Text(job.status, size=12, color=item["status_color"]),
                                    ft.Text(job.status, size=12),
                                    ft.Icon(ft.Icons.ARROW_FORWARD_IOS, size=14, color="#64748b"), ]), )

    # 即将逾期任务行
    def build_expire_job(job: Job):
        # warn_color = "#ef4444" if item["warn"] else "#f97316"
        warn_color = "#ef4444"
        return ft.Row([ft.Text(job.name, size=12, color="#cbd5e1", width=180),
                       ft.Text(job.type, size=12, color="#cbd5e1", width=160),
                       ft.Text(job.priority, size=12, color="#cbd5e1", width=80),
                       ft.Text(job.end_time, size=12, color="#cbd5e1", width=140),
                       ft.Text((job.end_time.date() - datetime.date.today()).days, size=12, color=warn_color,
                               width=100), ft.Text(job.status, size=12, color="#cbd5e1", width=100),
                       # ft.Icon(ft.Icons.WARNING_AMBER, size=14, color=warn_color) if item["warn"] else ft.Container(width=20),
                       ])

    # 底部区域：左【最新更新任务（可点击跳转）】 + 右【即将逾期任务关注列表】
    return ft.Row([  # 左下角：最新更新工作任务
        ft.Container(width=420, padding=16,
                     border=ft.Border(left=ft.BorderSide(1, "#22d3ee88"), right=ft.BorderSide(1, "#22d3ee88"),
                                      top=ft.BorderSide(1, "#22d3ee88"), bottom=ft.BorderSide(1, "#22d3ee88"), ),
                     border_radius=6, bgcolor="#111827", content=ft.Column(
                [ft.Text("最新更新工作", size=16, color="#22d3ee"),
                 ft.ListView(controls=[build_latest_job_row(job) for job in JobService.latest()], spacing=4,
                             height=320)])),  # 右下角：即将逾期任务关注列表
        ft.Container(expand=True, padding=16,
                     border=ft.Border(left=ft.BorderSide(1, "#22d3ee88"), right=ft.BorderSide(1, "#22d3ee88"),
                                      top=ft.BorderSide(1, "#22d3ee88"), bottom=ft.BorderSide(1, "#22d3ee88"), ),
                     border_radius=6, bgcolor="#111827", content=ft.Column(
                [ft.Text("即将逾期工作", size=16, color="#22d3ee"), ft.Row(
                    [ft.Text("名称", size=12, color="#94a3b8", width=160),
                     ft.Text("类型", size=12, color="#94a3b8", width=180),
                     ft.Text("优先级", size=12, color="#94a3b8", width=80),
                     ft.Text("结束时间", size=12, color="#94a3b8", width=140),
                     ft.Text("剩余时长", size=12, color="#94a3b8", width=100),
                     ft.Text("状态", size=12, color="#94a3b8", width=100), ft.Container(width=20), ]),
                 ft.ListView(controls=[build_expire_job(job) for job in JobService.expire()], spacing=6,
                             height=280)]))], spacing=16)
