from pathlib import Path


def get_db_path():
    return Path(__file__).parent / 'db.sqlite3'

DEFAULT_JOB_END_DAY = 7
