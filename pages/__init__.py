import flet as ft


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
                            size=15,
                            weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.W_400,
                            color="#F5FAFF" if is_active else "#54739E",
                        ),
                        ft.Container(
                            width=72,
                            height=2,
                            bgcolor="#40C9FF",
                            border_radius=2,
                            visible=is_active,
                            shadow=ft.BoxShadow(
                                spread_radius=1,
                                blur_radius=18,
                                color="#40C9FF",
                            ),
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
            bgcolor="#111834",
            padding=ft.Padding(16, 10, 16, 10),
            content=ft.Row(
                [
                    # 左侧标题
                    ft.Text("工作小助手", color="#CFD8FF", size=26, weight=ft.FontWeight.BOLD),
                    ft.Container(width=32),  # 标题和tab之间留白
                    self.build_tab("大盘概览", "/overview", "overview"),
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
            ft.Container(content=outlet, padding=20),
            ft.Text("Footer - (c) 2026", text_align=ft.TextAlign.CENTER),
        ],
        spacing=0,
        tight=True
    )
