import os
from typing import Any


class FileUtil:
    @staticmethod
    def is_file_exist(file: str) -> bool:
        return os.path.isfile(file)

    @staticmethod
    def new_dir(path: str):
        raise

    @staticmethod
    def new_file(file: str):
        FileUtil.new_dir(os.path.dirname(file))
        raise

    @staticmethod
    def write(file: str, content: Any):
        FileUtil.new_file(file)
        raise

    @staticmethod
    def read(file: str) -> Any:
        raise