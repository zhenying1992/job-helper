import logging
from pathlib import Path

import flet as ft

from src.common.util import can_access_dir
from src.config import save_app_config, get_work_dir

logger = logging.getLogger(__name__)


class InitView:
    def __init__(self, page: ft.Page):
        self.page = page

    def __call__(self, *args, **kwargs):
        return ft.AlertDialog(
            modal=True,
            title=ft.Text("首次启动请选择数据存放目录"),
            actions=[
                ft.Button(
                    "选择目录",
                    icon=ft.Icons.FOLDER_OPEN,
                    on_click=self.pick_dir_click
                )
            ]
        )

    async def pick_dir_click(self, e):
        work_dir = await ft.FilePicker().get_directory_path()
        logger.info(f"用户选择目录: {work_dir}")
        if not work_dir:
            logger.info("用户取消选择目录")
            return

        selected_dir = Path(work_dir)
        # 校验目录写入权限
        can_write = can_access_dir(selected_dir)
        if not can_write:
            logger.error(f"目录不可写入: {selected_dir}")
            self.page.show_dialog(
                ft.AlertDialog(
                    title=ft.Text("错误"),
                    content=ft.Text("所选目录没有写入权限，请更换文件夹"),
                    actions=[ft.TextButton("确定", on_click=lambda ev: self.page.pop_dialog())]
                )
            )
            return

        # 保存配置
        save_app_config({"WORK_DIR": str(selected_dir)})
        logger.info(f"工作目录已设置: {get_work_dir()}")

        # 关闭首次引导弹窗
        self.page.pop_dialog()

        logger.info("开始启动")
        from src.data.db import init_db
        from src.pages.urls import app

        init_db()
        self.page.render(app)