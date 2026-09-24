from datetime import datetime
from zoneinfo import ZoneInfo

from src.constant import DATE_FMT


def utc_2_naive_datetime(utc_dt: datetime) -> datetime:
    return utc_dt.astimezone(ZoneInfo(key='Asia/Shanghai')).replace(tzinfo=None)


def datetime_2_date_str(dt: datetime, fmt: str = DATE_FMT) -> str:
    return dt.strftime(fmt)
