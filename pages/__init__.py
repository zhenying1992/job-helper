import flet as ft

from theme import (
    ACCENT_BRIGHT, BG_DIALOG, TEXT_TAB_ACTIVE, TEXT_TAB_INACTIVE, TEXT_TITLE,
    FS_TAB, FS_DISPLAY, glow, GLOW_SOFT,
)


class Header:
    def get_active_key(self):
        current_route = ft.context.page.route

        if current_route == "/overview":
            active_key = "overview"
        elif current_route == "/jobs":
            active_key = "jobs"
        elif current_route.startswith("/job/"):
            active_key = "job"
        elif current_route.startswith("/setting"):
            active_key = "setting"
        elif current_route.startswith("/calendar"):
            active_key = "calendar"
        else:
            active_key = "overview"

        return active_key

    def build_tab(self, label, route, key):
        is_active = self.get_active_key() == key

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
                    spacing=6,
                ),
            ),
        )


    def build(self):
        return ft.Container(
            bgcolor=BG_DIALOG,
            padding=ft.Padding(16, 10, 16, 10),
            content=ft.Row(
                [
                    # 左侧标题
                    ft.Text(
                        "工作小助手", color=TEXT_TITLE, size=FS_DISPLAY,
                        weight=ft.FontWeight.BOLD,
                        style=ft.TextStyle(shadow=glow(ACCENT_BRIGHT, blur=12)),
                    ),
                    ft.Container(width=32),  # 标题和tab之间留白
                    self.build_tab("大盘概览", "/overview", "overview"),
                    ft.Container(width=24),
                    self.build_tab("日历排期", "/calendar", "calendar"),
                    ft.Container(width=24),
                    self.build_tab("工作列表", "/jobs", "jobs"),
                    ft.Container(width=24),
                    self.build_tab("配置中心", "/setting", "setting"),
                    # self.build_tab("工作详情", "/job/0", "job"),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
        )

@ft.component
def layout():
    outlet = ft.use_route_outlet()
    return ft.Column(
        [
            Header().build(),
            ft.Container(content=outlet, padding=20, expand=True),
        ],
        spacing=0,
        tight=True
    )
