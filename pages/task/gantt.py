import datetime
from typing import Callable
import flet as ft

from flet_charts import ChartAxisLabel, LineChartData, LineChartDataPoint, LineChart, ChartAxis

from constant import DATE_FMT, COLOR_TEXT
from data.model import Job
from data.service import TaskService



class TaskGantt:
    def __init__(self, job: Job, refresh_flag: bool, set_refresh_flag: Callable):
        self.job = job
        self.refresh_flag = refresh_flag
        self.set_refresh_flag = set_refresh_flag
        self.tasks = TaskService.query(job.id)

    # 甘特图
    def get_labels(self):
        labels = []
        for i in range(7):
            day = datetime.date.today() + datetime.timedelta(days=i)
            l = ChartAxisLabel(value=i, label=ft.Text(day.strftime(DATE_FMT), color=COLOR_TEXT, size=11))
            labels.append(l)

        return labels

    def get_data(self):
        data = []

        for idx, task in enumerate(self.tasks):
            s = (task.start_time.date() - datetime.datetime.today().date()).days
            e = (task.end_time.date() - datetime.datetime.today().date()).days
            data.append(
                LineChartData(
                    points=[
                        LineChartDataPoint(s, idx, tooltip=task.name),
                        LineChartDataPoint(e, idx, tooltip=task.name),
                    ],
                    color="#22c55e",
                    stroke_width=3,
                    point=True,
                )
            )
        return data

    def build(self):
        return LineChart(
            data_series=self.get_data(),
            left_axis=ChartAxis(labels=[], show_labels=False),
            bottom_axis=ChartAxis(
                labels=self.get_labels(),
            ),
            min_x=0,
            max_x=7,
            bgcolor="#0b1224",
            # border=ft.border.all(1, "#254b80"),
            height=300
        )
