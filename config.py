import json
from pathlib import Path
from typing import Optional

APP_CONF_PATH = Path.home() / '.job_helper' / 'config.json'

_config: Optional[dict] = None


def load_app_config() -> dict:
    global _config
    if _config is None:
        if APP_CONF_PATH.exists():
            with open(APP_CONF_PATH, "r", encoding="utf-8") as f:
                _config = json.load(f)
        else:
            _config = {}
    return _config


def save_app_config(cfg: dict):
    global _config
    APP_CONF_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(APP_CONF_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    _config = cfg


def get_work_dir() -> Optional[Path]:
    value = load_app_config().get('WORK_DIR')
    return Path(value) if value else None


def _require_work_dir() -> Path:
    work_dir = get_work_dir()
    if work_dir is None:
        raise RuntimeError('尚未配置工作目录，请先完成首次启动设置')
    return work_dir


def get_db_path() -> Path:
    return _require_work_dir() / 'sqlite.db'


def get_plugin_path() -> Path:
    path = _require_work_dir() / 'plugins'
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_backup_path() -> Path:
    """数据库备份目录。"""
    path = _require_work_dir() / 'backups'
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_attachment_path(job_id: int) -> Path:
    """某个工作的附件目录，按工作 id 分文件夹，避免重名冲突。"""
    path = _require_work_dir() / 'attachments' / str(job_id)
    path.mkdir(parents=True, exist_ok=True)
    return path
