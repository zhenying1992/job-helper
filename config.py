import json
from pathlib import Path
from typing import Optional

APP_CONF_PATH = Path.home() / '.job_helper' / 'config.json'

def load_app_config() -> dict:
    if not APP_CONF_PATH.exists():
        return {}

    with open(APP_CONF_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_app_config(cfg: dict):
    APP_CONF_PATH.parent.mkdir(exist_ok=True)
    with open(APP_CONF_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def get_work_dir() -> Optional[Path]:
    c = load_app_config()
    if 'WORK_DIR' not in c:
        return None

    return Path(c['WORK_DIR'])

def get_db_path() -> Path:
    work_dir = get_work_dir()
    db_path = work_dir / 'sqlite.db'
    return db_path

def get_plugin_path() -> Path:
    work_dir = get_work_dir()
    plugin_path = work_dir / 'plugins'
    plugin_path.mkdir(parents=True, exist_ok=True)
    return plugin_path

DEFAULT_JOB_END_DAY = 7
