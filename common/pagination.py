import math
from dataclasses import dataclass, field
from typing import TypeVar, Generic

T = TypeVar("T")

@dataclass
class Pagination(Generic[T]):
    current: int
    page_size: int
    total: int = 0
    data: list[T] = field(default_factory=list)

    @property
    def total_page(self) -> int:
        return math.ceil(self.total/self.page_size)
