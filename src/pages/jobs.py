import flet as ft



@ft.component
def jobs():
    return main_content

# 顶部筛选操作栏
action_bar = ft.Container(
    padding=ft.Padding(left=24, right=24, top=16, bottom=16),
    content=ft.Row(
        controls=[
            # ft.Container(width=3),
            ft.TextField(
                hint_text="输入工作名称搜索",
                width=320,
                height=40,
                border_radius=8,
                bgcolor="#161d34",
                text_size=14
            ),
            ft.Dropdown(
                label="工作类型",
                width=240,
                options=[
                    ft.dropdown.Option("全部"),
                    ft.dropdown.Option("稽查"),
                    ft.dropdown.Option("纳税评估"),
                    ft.dropdown.Option("风险核查")
                ],
                value="全部"
            ),
            ft.Dropdown(
                label="任务状态",
                width=140,
                options=[
                    ft.dropdown.Option("全部"),
                    ft.dropdown.Option("待处理"),
                    ft.dropdown.Option("进行中"),
                    ft.dropdown.Option("已办结"),
                    ft.dropdown.Option("暂停")
                ],
                value="全部"
            ),
            ft.Container(expand=True),
            ft.ElevatedButton(
                "+ 新增任务",
                bgcolor="#2563eb",
                color=ft.Colors.WHITE,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
            )
        ],
    )
)

# 表格定义
task_table = ft.DataTable(
    border_radius=10,
    bgcolor="#12182e",
    heading_row_color="#1b2442",
    columns=[
        ft.DataColumn(ft.Text("ID", color="#cbd5e1")),
        # ft.DataColumn(ft.Text("名称", color="#cbd5e1")),
        # ft.DataColumn(ft.Text("类型", color="#cbd5e1")),
        # ft.DataColumn(ft.Text("状态", color="#cbd5e1")),
        # ft.DataColumn(ft.Text("进度", color="#cbd5e1")),
        # ft.DataColumn(ft.Text("开始时间", color="#cbd5e1")),
        # ft.DataColumn(ft.Text("结束时间", color="#cbd5e1")),
        # ft.DataColumn(ft.Text("操作", color="#cbd5e1")),
    ],
    rows=[
        ft.DataRow(cells=[
            ft.DataCell(ft.Text("001")),
            # ft.DataCell(ft.Text("高收入人群涉税风险核查")),
            # ft.DataCell(ft.Text("风险核查")),
            # ft.DataCell(ft.Container(ft.Text("待处理", size=12), bgcolor="#f97316", padding=3, border_radius=4)),
            # ft.DataCell(ft.Text("张三")),
            # ft.DataCell(ft.Text("2026-09-01 09:20")),
            # ft.DataCell(ft.Row([
            #     ft.TextButton("查看"),
            #     ft.TextButton("编辑"),
            # ]))
        ]),
        # ft.DataRow(cells=[
        #     ft.DataCell(ft.Text("002")),
        #     ft.DataCell(ft.Text("某企业纳税评估案件")),
        #     ft.DataCell(ft.Text("纳税评估")),
        #     ft.DataCell(ft.Container(ft.Text("进行中", size=12), bgcolor="#3b82f6", padding=3, border_radius=4)),
        #     ft.DataCell(ft.Text("李四")),
        #     ft.DataCell(ft.Text("2026-09-03 14:10")),
        #     ft.DataCell(ft.Row([
        #         ft.TextButton("查看"),
        #         ft.TextButton("编辑"),
        #     ]))
        # ]),
        # ft.DataRow(cells=[
        #     ft.DataCell(ft.Text("003")),
        #     ft.DataCell(ft.Text("虚开发票专项稽查")),
        #     ft.DataCell(ft.Text("稽查")),
        #     ft.DataCell(ft.Container(ft.Text("已办结", size=12), bgcolor="#22c55e", padding=3, border_radius=4)),
        #     ft.DataCell(ft.Text("王五")),
        #     ft.DataCell(ft.Text("2026-08-15 11:30")),
        #     ft.DataCell(ft.Row([
        #         ft.TextButton("查看"),
        #         ft.TextButton("编辑"),
        #     ]))
        # ]),
    ]
)

# 分页控件
pagination_bar = ft.Container(
    padding=ft.Padding(left=24, right=24, top=16, bottom=16),
    content=ft.Row([
        ft.Text("共 3 条记录", color="#94a3b8"),
        ft.Container(expand=True),
        ft.Dropdown(
            label="每页条数",
            width=100,
            options=[ft.dropdown.Option("10"), ft.dropdown.Option("20"), ft.dropdown.Option("50")],
            value="10"
        ),
        ft.Container(width=10),
        ft.ElevatedButton("上一页", disabled=False),
        ft.Text("第 1 / 1 页"),
        ft.ElevatedButton("下一页", disabled=False),
    ])
)

# 主体容器：放表格+分页
main_content = ft.Container(
    padding=ft.Padding(left=24, right=24),
    content=ft.Column(
        controls=[
            action_bar,
            task_table,
            pagination_bar
        ],
        spacing=20
    )
)
