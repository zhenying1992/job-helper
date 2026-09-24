import logging
from pathlib import Path

import flet as ft

from src.config import save_app_config, get_work_dir

logger = logging.getLogger(__name__)


def get_init_view(page):
    async def pick_dir_click(e):
        work_dir = await ft.FilePicker().get_directory_path()
        logger.info(f"用户选择目录{work_dir}")
        if not work_dir:
            return

        selected_dir = Path(work_dir)
        # 校验目录写入权限
        try:
            test_file = selected_dir / ".write_test.tmp"
            test_file.write_text("test")
            test_file.unlink()
        except Exception as ex:
            logger.error(f"目录不可写入：{ex}")
            page.show_dialog(
                ft.AlertDialog(
                    title=ft.Text("错误"),
                    content=ft.Text("所选目录没有写入权限，请更换文件夹"),
                    actions=[ft.TextButton("确定", on_click=lambda ev: page.pop_dialog())]
                )
            )
            return

        # 保存配置并刷新全局WORK_DIR
        save_app_config({"WORK_DIR": str(selected_dir)})
        logger.info(f"工作目录已设置: {get_work_dir()}")

        # 关闭首次引导弹窗
        page.pop_dialog()

    return ft.AlertDialog(
            modal=True,
            title=ft.Text("请选择数据存放目录"),
            content=ft.Text("选择文件夹用于存放sqlite数据库文件"),
            actions=[
                ft.Button(
                    "选择目录",
                    icon=ft.Icons.FOLDER_OPEN,
                    # 唤起目录选择窗口
                    on_click=pick_dir_click
                )
            ]
        )
