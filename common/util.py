from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from constant import DATE_FMT, NODE_W, NODE_H


def utc_2_naive_datetime(utc_dt: datetime) -> datetime:
    return utc_dt.astimezone(ZoneInfo(key='Asia/Shanghai')).replace(tzinfo=None)


def datetime_2_date_str(dt: datetime, fmt: str = DATE_FMT) -> str:
    return dt.strftime(fmt)


def can_access_dir(dir: Path) -> bool:
    try:
        test_file = dir / ".write_test.tmp"
        test_file.write_text("test")
        test_file.unlink()
        return True
    except Exception:
        return False


def cal_position(num: int) -> tuple[int, int]:
    # 计算第num个节点位置，一列5个
    x = num // 5
    y = num % 5
    x_padding, y_padding = 50, 50
    return x * NODE_W * 2 + x_padding, y * NODE_H * 2 + y_padding


def human_size(n: int) -> str:
    """字节数格式化成可读单位。"""
    size = float(n)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def created_time(p: Path) -> datetime:
    """跨平台取文件创建时间。

    macOS/BSD: st_birthtime 才是真正的创建时间，st_ctime 是元数据变更时间。
    Windows / Linux 兜底用 st_ctime。
    """
    st = p.stat()
    if hasattr(st, "st_birthtime"):
        return datetime.fromtimestamp(st.st_birthtime)
    return datetime.fromtimestamp(st.st_ctime)


def list_dir(path: str | Path = ".", recursive: bool = False):
    if type(path) == 'str':
        root = Path(path)
    else:
        root = path

    iterator = root.rglob("*") if recursive else root.iterdir()

    rows = []
    for p in iterator:
        if p.is_file():
            st = p.stat()
            rows.append(
                {
                    "name": p.name,
                    "size": st.st_size,
                    "size_h": human_size(st.st_size),
                    "created": created_time(p),
                    "path": str(p),
                }
            )

    rows.sort(key=lambda r: r["created"])  # 按创建时间升序
    return rows
