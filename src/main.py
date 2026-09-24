
import flet as ft

from src.config import get_work_dir
from src.pages.init import get_init_view
import logging


logger = logging.getLogger(__name__)

def main(page: ft.Page):
    page.padding=0
    page.margin=0
    page.bgcolor = "#0B1020"

    if not get_work_dir():
        logger.warning("首次启动，缺少工作目录配置")
        page.show_dialog(get_init_view(page))
    else:
        logger.info("非首次启动，跳过目录配置")
        from src.data.db import init_db
        init_db()
        from src.pages.urls import app
        page.render(app)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    ft.run(main)
