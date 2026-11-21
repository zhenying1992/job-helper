import datetime

import flet as ft
from flet import TextAlign
from flet_charts import *

from common.util import datetime_2_date_str
from constant import *  # noqa: F403  枚举/日期格式/统计参数
from data.model import Job
from data.service import JobService, TaskService
from theme import (
    BG_CARD, BORDER, BORDER_ACCENT, MUTED, ACCENT, SLATE, TEXT_BRIGHT, TEXT,
    DANGER, SAFE, FS_BASE, FS_METRIC, FS_XL, FS_MD, FS_SM, glow, GLOW_SOFT,
    RADIUS_MD, FONT_MONO,
)


@ft.component
def overview():
    return ft.Column(
        [
            ft.Container(height=5),
            Top().build(),
            ft.Container(height=5),
            Center().build(),
            ft.Container(height=5),
            Bottom().build(),
        ],
        expand=True
    )


class Top:
    @staticmethod
    def _change_badge(change: int) -> ft.Control:
        """相比上周的变动徽标：↑增加(绿) / ↓减少(红) / —持平(灰)。"""
        if change > 0:
            text, color, icon = f"+{change} 较上周", SAFE, ft.Icons.TRENDING_UP
        elif change < 0:
            text, color, icon = f"{change} 较上周", DANGER, ft.Icons.TRENDING_DOWN
        else:
            text, color, icon = "与上周持平", SLATE, ft.Icons.REMOVE
        return ft.Row([
            ft.Icon(icon, size=FS_MD, color=color),
            ft.Text(text, size=FS_SM, color=color),
        ], spacing=0)

    @staticmethod
    def build_card(title, value, change: int = 0):
        return ft.Container(
            expand=True, height=124, padding=ft.Padding(18, 12, 18, 10),
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
                    ft.Row(
                        controls=[
                            ft.Text(
                                str(value),
                                size=FS_METRIC,
                                weight=ft.FontWeight.BOLD,
                                color=ACCENT,
                                font_family=FONT_MONO,
                            ),
                            ft.Container(
                                content=Top._change_badge(change),
                                padding=ft.Padding(left=0, top=0, right=0, bottom=10),  # 下沉量，按观感调
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.END,  # 关键：贴行底部
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
        )

    def build(self):
        total_job_c, _ = JobService.total()
        finish_job, _ = JobService.total(status=Status.FINISHED)
        total_task_c, _ = TaskService.total()
        finish_task, _ = TaskService.total(status=Status.FINISHED)

        # 相比上周：总数按创建/开始时间，已完成按完成时间
        job_change = JobService.week_change()
        finish_job_change = JobService.week_change(Status.FINISHED, 'end_time')
        task_change = TaskService.week_change()
        finish_task_change = TaskService.week_change(Status.FINISHED, 'end_time')

        return ft.Row([
            self.build_card("工作总数", total_job_c, job_change),
            self.build_card("已完成工作", finish_job, finish_job_change),
            self.build_card("任务总数", total_task_c, task_change),
            self.build_card("已完成任务", finish_task, finish_task_change),
        ], spacing=16)


class Center:
    """第二行：左饼图 + 右工作进展折线图。"""

    def build(self):
        return ft.Row([
            ft.Container(
                width=360, height=330, bgcolor=BG_CARD,
                border_radius=RADIUS_MD, padding=ft.Padding(18, 12, 18, 12),
                content=self.build_left(),
            ),
            ft.Container(
                expand=True, bgcolor=BG_PANEL, height=330,
                border_radius=BORDER_RADIUS, padding=ft.Padding(18, 12, 18, 12),
                content=self.build_right(),
            )
        ], spacing=16)

    # ---------------- 左：任务分布饼图 ----------------
    normal_radius = 84
    hover_radius = 94
    normal_title_style = ft.TextStyle(size=FS_BASE, color=TEXT_BRIGHT, weight=ft.FontWeight.BOLD)
    hover_title_style = ft.TextStyle(size=FS_MD, color=TEXT_BRIGHT, weight=ft.FontWeight.BOLD)

    @staticmethod
    def _pct(value: int, total: int) -> int:
        return round(value / total * 100) if total else 0

    @staticmethod
    def _pie_state(items, total, hovered):
        """按 hover 索引算出扇区标题 / 半径 / tooltip（纯函数，便于测试）。

        默认标题是状态名；悬浮某块时该块显示「数量 (占比)」，其余保持原样。
        """
        titles, radii = [], []
        for i, (status, value) in enumerate(items):
            active = i == hovered
            titles.append(f"{value} ({Center._pct(value, total)}%)" if active else status)
            radii.append(Center.hover_radius if active else Center.normal_radius)
        if hovered is not None and 0 <= hovered < len(items):
            status, value = items[hovered]
            tooltip = f"{status}：{value} 个（{Center._pct(value, total)}%）"
        else:
            tooltip = "悬浮查看各状态数量与占比"
        return titles, radii, tooltip

    @ft.component
    def build_left(self):
        # 声明式组件里控件构建后即被冻结，不能在回调里改属性 + update()。
        # 用 use_state 存 hover 扇区索引，回调只改状态，由组件自身重渲染。
        hovered, set_hovered = ft.use_state(None)
        data = JobService.ratio()
        total = sum(data.values())
        items = list(data.items())
        titles, radii, tooltip = self._pie_state(items, total, hovered)

        sections = [
            PieChartSection(
                value=value, title=titles[i], color=Status.color(status),
                radius=radii[i],
                title_style=self.hover_title_style if i == hovered else self.normal_title_style,
            )
            for i, (status, value) in enumerate(items)
        ]

        def on_hover(e):
            idx = e.section_index
            set_hovered(idx if idx is not None and 0 <= idx < len(items) else None)

        chart = PieChart(
            sections=sections,
            sections_space=2,
            center_space_radius=40,
            expand=True,
            tooltip=tooltip,
            on_event=on_hover,
        )
        return ft.Column([
            ft.Text("任务分布饼图", color=COLOR_PRIMARY, size=FS_XL, weight=ft.FontWeight.BOLD),
            chart,
        ])

    # ---------------- 右：工作进展折线图 ----------------
    def build_right(self):
        chart = LineChart(
            data_series=[self.get_right_job_data(), self.get_right_task_data()],
            left_axis=ChartAxis(labels=[], show_labels=True,
                                title=ft.Text("数量", size=FS_SM, color=MUTED), title_size=FS_SM),
            bottom_axis=ChartAxis(labels=self.get_right_labels(), label_size=FS_SM),
            min_x=0, max_x=TREND_DAY, min_y=0, max_y=max(4, self._peak()),
            horizontal_grid_lines=ChartGridLines(color=BORDER, width=1),
            # 注意：LineChart.tooltip 只接受 LineChartTooltip 类型，传字符串会导致
            # 序列化失败、整图渲染不出（露出灰底）。数据点的 tooltip 在各点上单独设置。
            bgcolor="#FF070D1B",
            expand=True,
        )
        legend = ft.Row([
            self._legend_dot(COLOR_JOB_FINISH, "完成工作"),
            self._legend_dot(COLOR_TASK_FINISH, "完成任务"),
        ], spacing=18)

        return ft.Column([
            ft.Row([
                ft.Text("工作进展", size=FS_XL, color=ACCENT),
                legend,
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER),
            chart,
        ], spacing=10, expand=True)

    def _peak(self) -> int:
        """两条累计曲线的最高峰值，用于动态设置 Y 轴上限。"""

        def cumulative_peak(trend: dict) -> int:
            running = peak = 0
            for v in trend.values():
                running += v
                peak = max(peak, running)
            return peak

        return max(cumulative_peak(JobService.finish_trend(TREND_DAY)),
                   cumulative_peak(TaskService.finish_trend(TREND_DAY)))

    @staticmethod
    def _legend_dot(color: str, label: str) -> ft.Control:
        return ft.Row([
            ft.Container(width=18, height=4, border_radius=2, bgcolor=color),
            ft.Text(label, size=FS_SM, color=TEXT),
        ], spacing=6)

    def _series(self, data: dict, color: str, label: str) -> LineChartData:
        # 累加为累计完成数，曲线更有趋势感；每个点带 tooltip
        points = []
        running = 0
        for idx, value in enumerate(data.values()):
            running += value
            points.append(LineChartDataPoint(
                idx, running,
                tooltip=f"{label} · {value} 个（累计 {running}）",
                show_tooltip=True,
            ))
        return LineChartData(
            points=points, color=color, stroke_width=3,
            point=True, selected_point=True, curved=True,
        )

    def get_right_job_data(self):
        return self._series(JobService.finish_trend(TREND_DAY), COLOR_JOB_FINISH, "完成工作")

    def get_right_task_data(self):
        return self._series(TaskService.finish_trend(TREND_DAY), COLOR_TASK_FINISH, "完成任务")

    def get_right_labels(self):
        labels = []
        data = JobService.finish_trend(days=TREND_DAY)
        # 标签过密时隔一个显示，避免拥挤
        for idx, day in enumerate(data.keys()):
            if idx % 2 and idx != len(data) - 1:
                continue
            d = day.split("-")[-1]
            labels.append(ChartAxisLabel(value=idx, label=ft.Text(d, color=MUTED, size=FS_SM)))
        return labels


class Bottom:
    # 两张卡片共用的描边样式，避免重复内联
    @staticmethod
    def _panel(content, expand=False, width=None):
        return ft.Container(
            width=width, expand=expand, height=270, padding=ft.Padding(16, 12, 16, 12),
            border=ft.Border(
                left=ft.BorderSide(1, BORDER_ACCENT),
                right=ft.BorderSide(1, BORDER_ACCENT),
                top=ft.BorderSide(1, BORDER_ACCENT),
                bottom=ft.BorderSide(1, BORDER_ACCENT),
            ),
            border_radius=RADIUS_MD,
            bgcolor=BG_CARD,
            content=content,
        )

    def build(self):
        return ft.Row([
            self._panel(self.build_left(), width=440),
            self._panel(self.build_right(), expand=True),
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

    # 即将逾期表格的列定义：(标题, flex)。名称占 3，其余按内容分配，末列图标固定。
    _COLS = (
        ("名称", 3), ("类型", 2), ("优先级", 1),
        ("结束时间", 2), ("剩余时长", 2), ("状态", 2),
    )
    _ICON_W = 28

    # 右边
    def build_right(self):
        header = ft.Row([
                            ft.Text(h, size=FS_MD, color=MUTED, text_align=TextAlign.CENTER, expand=f)
                            for h, f in self._COLS
                        ] + [ft.Container(width=self._ICON_W)], spacing=8)
        return ft.Column([
            ft.Text("即将逾期工作", size=FS_XL, color=ACCENT),
            header,
            ft.Divider(color=BORDER, height=1),
            ft.ListView(
                controls=[self.build_expire_job(job) for job in JobService.expire()],
                spacing=6, expand=True,
            )
        ], spacing=10, expand=True)

    def build_expire_job(self, job: Job):
        day = (job.end_time.date() - datetime.date.today()).days
        if day < 0:
            text, color = f"已逾期{-day}天", COLOR_DANGER
        elif day <= 3:
            text, color = str(day), COLOR_WARN
        else:
            text, color = str(day), COLOR_SAFE

        name = ft.Text(job.name, size=FS_MD, color=ACCENT,
                       max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        return ft.Row([
            ft.Container(
                expand=3, tooltip=job.name,
                on_click=lambda e: ft.context.page.navigate(f"/job/{job.id}"),
                content=name,
            ),
            ft.Text(job.type, size=FS_MD, color=COLOR_TEXT, text_align=TextAlign.CENTER, expand=2),
            ft.Text(job.priority, size=FS_MD, color=COLOR_TEXT, text_align=TextAlign.CENTER, expand=1),
            ft.Text(job.end_time.strftime("%Y-%m-%d"), size=FS_MD, color=COLOR_TEXT,
                    text_align=TextAlign.CENTER, expand=2),
            ft.Text(text, size=FS_MD, color=color, text_align=TextAlign.CENTER, expand=2),
            ft.Text(job.status, size=FS_MD, color=COLOR_TEXT, text_align=TextAlign.CENTER, expand=2),
            ft.Icon(ft.Icons.WARNING_AMBER, size=FS_BASE, color=COLOR_WARN,
                    width=self._ICON_W) if day < 3 else ft.Container(width=self._ICON_W),
        ], spacing=8)
