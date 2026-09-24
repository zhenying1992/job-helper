import flet as ft

from src.pages import layout
from src.pages.overview import overview
from src.pages.job import job_view
from src.pages.jobs import jobs_view


def get_urls():
    return ft.Router([
        ft.Route(
            component=layout,
            outlet=True,
            children=[
                ft.Route(index=True, component=overview),
                ft.Route(path='overview', component=overview),
                ft.Route(path='jobs', component=jobs_view),
                ft.Route(path='job/:job_id', component=job_view)
            ]
        )]
    )
