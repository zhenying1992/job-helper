from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from constant import DATE_FMT


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
    except Exception as ex:
        return False
