import functools
import logging

import flet as ft

from theme import DANGER, TEXT

logger = logging.getLogger(__name__)


def catch_error(func):
    """装饰 Flet 组件：异常时记录日志并在页面内显示错误，避免静默返回 None。"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as ex:
            logger.exception("组件 %s 渲染失败", func.__name__)
            return ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.ERROR_OUTLINE, color=DANGER, size=32),
                    ft.Text("页面加载失败", color=DANGER, size=16,
                            weight=ft.FontWeight.BOLD),
                    ft.Text(str(ex), color=TEXT, size=12),
                ], alignment=ft.MainAxisAlignment.CENTER,
                   horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                alignment=ft.Alignment.CENTER,
                expand=True,
                padding=20,
            )

    return wrapper
