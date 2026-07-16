from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar


TestMethod = TypeVar("TestMethod", bound=Callable)


def covers_adversarial(*case_ids: str) -> Callable[[TestMethod], TestMethod]:
    """Bind an executable regression test to adversarial case IDs."""
    def decorate(method: TestMethod) -> TestMethod:
        setattr(method, "adversarial_case_ids", frozenset(case_ids))
        return method
    return decorate
