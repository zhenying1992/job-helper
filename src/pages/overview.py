import flet as ft


@ft.component
def overview():
    return ft.Column([
        ft.Container(height=16),
        kpi_row,
        ft.Container(height=16),
        chart_row,
        ft.Container(height=16),
        bottom_row
    ], expand=True)

def tech_card(title, value, sub_text):
    return ft.Container(
        width=360,
        height=220,
        padding=20,
        border_radius=12,
        # 四边边框，0.86.5 兼容写法
        border=ft.Border(
            top=ft.BorderSide(1, "#4488FF33"),
            bottom=ft.BorderSide(1, "#4488FF33"),
            left=ft.BorderSide(1, "#4488FF33"),
            right=ft.BorderSide(1, "#4488FF33"),
        ),
        gradient=ft.LinearGradient(
            # begin=ft.Alignment.top_left,
            # end=ft.Alignment.bottom_right,
            colors=["#0f1933", "#081022"]
        ),
        shadow=ft.BoxShadow(
            blur_radius=20,
            spread_radius=1,
            color="#2178FF40"
        ),
        content=ft.Column([
            ft.Text(title, size=16, color="#96b8e8"),
            ft.Text(
                value,
                size=42,
                weight=ft.FontWeight.BOLD,
                color="#ffffff",
                # shadow=ft.BoxShadow(blur_radius=8, color="#4488FF")
            ),
            ft.Text(sub_text, size=13, color="#6989b9"),
        ], spacing=12)
    )


# todo
# 任务趋势图
# 高中低优先级任务占比

# ---------------------- 模拟数据 ----------------------
# KPI数据
kpi_data = [
    {"title": "工作总数", "value": 28},
    {"title": "任务总数", "value": 186},
    {"title": "未完成任务", "value": 74},
    {"title": "进行中工作", "value": 11},
]

# 最新更新任务（支持点击跳转）
latest_tasks = [
    {"job_name": "税务风险核查", "task_name": "资料归集", "update_time": "09-15 08:20", "action": "状态更新",
     "status": "进行中", "status_color": "#22d3ee"},
    {"job_name": "案例整理", "task_name": "报表导出", "update_time": "09-14 16:10", "action": "新建任务",
     "status": "待开始", "status_color": "#f97316"},
    {"job_name": "数据筛查", "task_name": "交叉比对", "update_time": "09-14 10:05", "action": "优先级调整",
     "status": "进行中", "status_color": "#22d3ee"},
    {"job_name": "高收入分析", "task_name": "流水核验", "update_time": "09-13 19:30", "action": "任务完成",
     "status": "已完成", "status_color": "#10b981"},
]

# 即将逾期任务列表
expire_tasks = [
    {"job": "税务风险核查", "task": "资料归集", "priority": "高", "end_time": "09-16 09:00", "remain": "18小时",
     "status": "进行中", "warn": True},
    {"job": "案例整理", "task": "报表导出", "priority": "中", "end_time": "09-18 17:00", "remain": "3天",
     "status": "待开始", "warn": False},
    {"job": "数据筛查", "task": "交叉比对", "priority": "高", "end_time": "09-15 14:00", "remain": "已超时",
     "status": "进行中", "warn": True},
]


# ---------------------- 点击跳转事件 ----------------------
def task_click(e):
    # e.control.data 存放任务信息，后续可打开弹窗/跳转到详情页
    task_info = e.control.data
    page.dialog = ft.AlertDialog(
        title=ft.Text("任务详情", color="#22d3ee"),
        content=ft.Text(
            f"所属工作：{task_info['job_name']}\n任务名称：{task_info['task_name']}\n状态：{task_info['status']}"),
    )
    page.dialog.open = True
    page.update()


# ---------------------- 组件构建函数 ----------------------
# KPI卡片
def build_kpi_card(title, value):
    return ft.Container(
        width=220,
        height=120,
        padding=16,
        border=ft.Border(
            left=ft.BorderSide(1, "#22d3ee88"),
            right=ft.BorderSide(1, "#22d3ee88"),
            top=ft.BorderSide(1, "#22d3ee88"),
            bottom=ft.BorderSide(1, "#22d3ee88"),
        ),
        border_radius=6,
        bgcolor="#111827",
        content=ft.Column([
            ft.Text(title, size=14, color="#94a3b8"),
            ft.Text(str(value), size=40, weight=ft.FontWeight.BOLD, color="#22d3ee"),
        ], alignment=ft.MainAxisAlignment.CENTER),
    )


# 最新更新任务条目（可点击跳转）
def build_latest_task_row(item):
    return ft.Container(
        data=item,
        on_click=task_click,
        padding=10,
        border_radius=4,
        # hover_color="#1e293b",
        content=ft.Row([
            ft.Container(width=10, height=10, bgcolor=item["status_color"], border_radius=99),
            ft.Container(width=10),
            ft.Column([
                ft.Text(item["task_name"], color="#22d3ee", size=14, weight=ft.FontWeight.W_500),
                ft.Text(f"{item['job_name']} | {item['update_time']} | {item['action']}", size=11, color="#94a3b8"),
            ], expand=True),
            ft.Text(item["status"], size=12, color=item["status_color"]),
            ft.Icon(ft.Icons.ARROW_FORWARD_IOS, size=14, color="#64748b"),
        ]),
    )


# 即将逾期任务行
def build_expire_row(item):
    warn_color = "#ef4444" if item["warn"] else "#f97316"
    return ft.Row([
        ft.Text(item["job"], size=12, color="#cbd5e1", width=180),
        ft.Text(item["task"], size=12, color="#cbd5e1", width=160),
        ft.Text(item["priority"], size=12, color="#cbd5e1", width=80),
        ft.Text(item["end_time"], size=12, color="#cbd5e1", width=140),
        ft.Text(item["remain"], size=12, color=warn_color, width=100),
        ft.Text(item["status"], size=12, color="#cbd5e1", width=100),
        ft.Icon(ft.Icons.WARNING_AMBER, size=14, color=warn_color) if item["warn"] else ft.Container(width=20),
    ])


# ---------------------- 页面组装 ----------------------
# 顶部标题栏

# KPI 行
kpi_row = ft.Row([build_kpi_card(i["title"], i["value"]) for i in kpi_data], spacing=16)

# 中间区域：左【任务状态环形图】 + 右【完成趋势图】
chart_row = ft.Row([
    # 任务状态分布卡片（替换PieChart，纯文本图例面板）
    ft.Container(
        width=420,
        padding=16,
        border=ft.Border(
            left=ft.BorderSide(1, "#22d3ee88"),
            right=ft.BorderSide(1, "#22d3ee88"),
            top=ft.BorderSide(1, "#22d3ee88"),
            bottom=ft.BorderSide(1, "#22d3ee88"),
        ),
        border_radius=6,
        bgcolor="#111827",
        content=ft.Column([
            ft.Text("任务状态分布", size=16, color="#22d3ee"),
            ft.Container(height=30),  # 占位,
            ft.Row([
                ft.Container(width=16, height=16, bgcolor="#22d3ee", border_radius=3),
                ft.Container(width=8),
                ft.Text("进行中：40", color="#cbd5e1"),
            ]),
            ft.Container(height=10),
            ft.Row([
                ft.Container(width=16, height=16, bgcolor="#22d3ee", border_radius=3),
                ft.Container(width=8),
                ft.Text("待开始：25", color="#cbd5e1"),
            ]),
            ft.Container(height=10),
            ft.Row([
                ft.Container(width=16, height=16, bgcolor="#22d3ee", border_radius=3),
                ft.Container(width=8),
                ft.Text("异常：10", color="#cbd5e1"),
            ]),
            ft.Container(height=10),
            ft.Row([
                ft.Container(width=16, height=16, bgcolor="#22d3ee", border_radius=3),
                ft.Container(width=8),
                ft.Text("已完成：111", color="#cbd5e1"),
            ]),
        ])
    ),
    # 完成任务趋势【静态文本面板，删掉LineChart】
    ft.Container(
        expand=True,
        padding=16,
        border=ft.Border(
            left=ft.BorderSide(1, "#22d3ee88"),
            right=ft.BorderSide(1, "#22d3ee88"),
            top=ft.BorderSide(1, "#22d3ee88"),
            bottom=ft.BorderSide(1, "#22d3ee88"),
        ),
        border_radius=6,
        bgcolor="#111827",
        content=ft.Column([
            ft.Text("完成任务趋势", size=16, color="#22d3ee"),
            ft.Container(height=20),
            ft.Text("第0天：30", color="#cbd5e1"),
            ft.Text("第1天：70", color="#cbd5e1"),
            ft.Text("第2天：40", color="#cbd5e1"),
            ft.Text("第3天：120", color="#cbd5e1"),
            ft.Text("第4天：40", color="#cbd5e1"),
            ft.Text("第5天：140", color="#cbd5e1"),
            ft.Text("第6天：240", color="#cbd5e1"),
        ], expand=True)
    )
], spacing=16)

# 底部区域：左【最新更新任务（可点击跳转）】 + 右【即将逾期任务关注列表】
bottom_row = ft.Row([
    # 左下角：最新更新工作任务
    ft.Container(
        width=420,
        padding=16,
        border=ft.Border(
            left=ft.BorderSide(1, "#22d3ee88"),
            right=ft.BorderSide(1, "#22d3ee88"),
            top=ft.BorderSide(1, "#22d3ee88"),
            bottom=ft.BorderSide(1, "#22d3ee88"),
        ),
        border_radius=6,
        bgcolor="#111827",
        content=ft.Column([
            ft.Text("最新更新的工作任务", size=16, color="#22d3ee"),
            ft.ListView(
                controls=[build_latest_task_row(item) for item in latest_tasks],
                spacing=4,
                height=320
            )
        ])
    ),
    # 右下角：即将逾期任务关注列表
    ft.Container(
        expand=True,
        padding=16,
        border=ft.Border(
            left=ft.BorderSide(1, "#22d3ee88"),
            right=ft.BorderSide(1, "#22d3ee88"),
            top=ft.BorderSide(1, "#22d3ee88"),
            bottom=ft.BorderSide(1, "#22d3ee88"),
        ),
        border_radius=6,
        bgcolor="#111827",
        content=ft.Column([
            ft.Text("即将逾期任务关注列表", size=16, color="#22d3ee"),
            ft.Row([
                ft.Text("所属工作", size=12, color="#94a3b8", width=180),
                ft.Text("任务名称", size=12, color="#94a3b8", width=160),
                ft.Text("优先级", size=12, color="#94a3b8", width=80),
                ft.Text("结束时间", size=12, color="#94a3b8", width=140),
                ft.Text("剩余时长", size=12, color="#94a3b8", width=100),
                ft.Text("状态", size=12, color="#94a3b8", width=100),
                ft.Container(width=20),
            ]),
            ft.ListView(
                controls=[build_expire_row(item) for item in expire_tasks],
                spacing=6,
                height=280
            )
        ])
    )
], spacing=16)
