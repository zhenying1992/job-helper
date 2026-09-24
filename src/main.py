import flet as ft

from src.data.db import init_db
from src.pages.urls import get_urls


@ft.component
def app():
    urls = get_urls()
    return ft.SafeArea(urls)

def main(page: ft.Page):
    page.padding=0
    page.margin=0
    page.bgcolor = "#0B1020"
    page.render(app)

if __name__ == "__main__":
    init_db()
    ft.run(main)
