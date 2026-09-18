from dataclasses import dataclass, field
from typing import TypeVar, Generic, Optional

T = TypeVar("T")

@dataclass
class Pagination(Generic[T]):
    current: int
    page_size: int
    total: int = 0
    data: list[T] = field(default_factory=list)
    order: Optional[str] = None
    sort: Optional[str] = None

    @property
    def total_page(self) -> int:
        return self.total // self.page_size
