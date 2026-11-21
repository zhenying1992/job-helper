"""插件运行时宿主：把"只做静态校验的空壳插件"接成真正可渲染的扩展。

设计约定（插件文件必须声明）：
    PLUGIN_NAME: str
    PLUGIN_VERSION: int
    PLUGIN_DESCRIPTION: str
    def build(job): ...   # 接收 data.model.Job，返回一个 Flet 控件

信任边界：
- 安装时：setting.py 用 AST 静态解析元信息，不执行插件代码；
- 运行时：仅当某工作的 type 命中已安装插件时，才 importlib 加载并执行 build；
  这等价于"用户主动安装即信任"，与浏览器扩展一致；
- 加载失败/插件异常不会拖垮主程序，返回可阅读的错误控件。
"""

import importlib.util
import logging
from pathlib import Path

import flet as ft

from config import get_plugin_path
from data.model import Plugin
from theme import DANGER, TEXT, FS_MD

logger = logging.getLogger(__name__)

# file_path -> (mtime, module)，插件文件变更后自动重载
_CACHE: dict[str, tuple[float, object]] = {}


def load_module(plugin: Plugin):
    """从插件文件加载 Python 模块，带 mtime 缓存。失败则返回 None 并记录日志。"""
    path: Path = get_plugin_path() / plugin.file_name
    if not path.exists():
        logger.warning('插件文件不存在：%s', path)
        return None
    try:
        mtime = path.stat().st_mtime
        cached = _CACHE.get(str(path))
        if cached and cached[0] == mtime:
            return cached[1]
        spec = importlib.util.spec_from_file_location(f'jh_plugin_{plugin.id}', path)
        if spec is None or spec.loader is None:
            raise ImportError('无法创建模块加载器')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _CACHE[str(path)] = (mtime, module)
        logger.info('插件已加载：%s', plugin.name)
        return module
    except Exception:
        logger.exception('插件加载失败：%s', plugin.name)
        return None


def find_for_type(job_type: str) -> Plugin | None:
    """按工作类型名查找已安装插件（工作类型下拉里的插件名与此一致）。"""
    from data.service import PluginService
    for plugin in PluginService.list():
        if plugin.name == job_type:
            return plugin
    return None


def build_view(plugin: Plugin, job) -> ft.Control:
    """调用插件 build(job) 生成控件；任何异常都转成可阅读的错误视图。"""
    module = load_module(plugin)
    if module is None:
        return _error(f'插件「{plugin.name}」加载失败，请检查文件格式或重新安装')
    builder = getattr(module, 'build', None)
    if not callable(builder):
        return _error(f'插件「{plugin.name}」缺少 build(job) 方法')
    try:
        control = builder(job)
        if not isinstance(control, ft.Control):
            return _error(f'插件「{plugin.name}」的 build 未返回 Flet 控件')
        return control
    except Exception as ex:
        logger.exception('插件 build 执行失败：%s', plugin.name)
        return _error(f'插件「{plugin.name}」运行出错：{ex}')


def _error(message: str) -> ft.Control:
    return ft.Container(
        content=ft.Column([
            ft.Icon(ft.Icons.BUG_REPORT, color=DANGER, size=32),
            ft.Text(message, color=TEXT, size=FS_MD),
        ], alignment=ft.MainAxisAlignment.CENTER,
           horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        alignment=ft.Alignment.CENTER,
        expand=True,
        padding=20,
    )
