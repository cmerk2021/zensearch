"""Shared pagination helpers."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

MAX_PAGE_SIZE = 100


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=25, ge=1, le=MAX_PAGE_SIZE)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int

    @property
    def pages(self) -> int:
        return max(1, -(-self.total // self.size))
