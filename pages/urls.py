import flet as ft

from pages import layout
from pages.job import job_view
from pages.overview import overview
from pages.jobs import jobs_view
from pages.setting import setting_view


def get_urls():
    return ft.Router([
        ft.Route(
            component=layout,
            outlet=True,
            children=[
                ft.Route(index=True, component=overview),
                ft.Route(path='overview', component=overview),
                ft.Route(path='jobs', component=jobs_view),
                ft.Route(path='job/:job_id', component=job_view),
                ft.Route(path='setting', component=setting_view),
            ]
        )]
    )

@ft.component
def app():
    urls = get_urls()
    return ft.SafeArea(urls)
