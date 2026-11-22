import flet as ft

from theme import (
    ACCENT_BRIGHT, BG_DIALOG, TEXT_TAB_ACTIVE, TEXT_TAB_INACTIVE, TEXT_TITLE,
    FS_TAB, FS_DISPLAY, glow,
)


def _active_key() -> str:
    """按当前路由推导高亮的 Tab key。"""
    route = ft.context.page.route
    if route == "/overview":
        return "overview"
    if route == "/jobs":
        return "jobs"
    for prefix, key in (("/job/", "job"), ("/setting", "setting"),
                        ("/calendar", "calendar")):
        if route.startswith(prefix):
            return key
    return "overview"


def _tab(label: str, route: str, key: str) -> ft.Control:
    """单个顶部导航 Tab：选中态文字加粗、下方显示霓虹指示条。"""
    is_active = _active_key() == key
    return ft.GestureDetector(
        on_tap=lambda: ft.context.page.navigate(route),
        content=ft.Container(
            padding=ft.Padding(16, 8, 16, 12),
            content=ft.Column(
                [
                    ft.Text(
                        label,
                        size=FS_TAB,
                        weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.W_400,
                        color=TEXT_TAB_ACTIVE if is_active else TEXT_TAB_INACTIVE,
                    ),
                    ft.Container(
                        width=72,
                        height=2,
                        bgcolor=ACCENT_BRIGHT,
                        border_radius=2,
                        visible=is_active,
                        shadow=glow(ACCENT_BRIGHT, blur=18),
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=2,
            ),
        ),
    )


TABS = (
    ("大盘概览", "/overview", "overview"),
    ("日历排期", "/calendar", "calendar"),
    ("工作列表", "/jobs", "jobs"),
    ("配置中心", "/setting", "setting"),
)


@ft.component
def Header():
    """顶部导航条：标题 + Tab，Tab 定义集中在 TABS。"""
    items = [ft.Text(
        "工作小助手", color=TEXT_TITLE, size=FS_DISPLAY,
        weight=ft.FontWeight.BOLD,
        style=ft.TextStyle(shadow=glow(ACCENT_BRIGHT, blur=12)),
    ), ft.Container(width=32)]
    for i, (label, route, key) in enumerate(TABS):
        if i:
            items.append(ft.Container(width=24))
        items.append(_tab(label, route, key))
    return ft.Container(
        bgcolor=BG_DIALOG,
        padding=ft.Padding(16, 10, 16, 10),
        content=ft.Row(
            items,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        ),
    )


@ft.component
def layout():
    outlet = ft.use_route_outlet()
    return ft.Column(
        [
            Header(),
            ft.Container(content=outlet, padding=15, expand=True),
        ],
        spacing=0,
        tight=True
    )
