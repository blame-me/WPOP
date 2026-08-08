"""Check discovery. Any concrete subclass of Check defined inside
wpop/checks (its submodules) is auto-registered; no wiring needed."""
from __future__ import annotations

import importlib
import pkgutil
from typing import List, Type

from wpop.core.models import Check


def discover(package_name: str = "wpop.checks") -> List[Type[Check]]:
    package = importlib.import_module(package_name)
    classes: List[Type[Check]] = []
    seen: set[str] = set()

    for module_info in pkgutil.iter_modules(package.__path__, package_name + "."):
        try:
            module = importlib.import_module(module_info.name)
        except Exception:
            continue
        for _, obj in vars(module).items():
            if (
                isinstance(obj, type)
                and issubclass(obj, Check)
                and obj is not Check
                and obj.__module__ == module_info.name
                and obj.__name__ not in seen
            ):
                classes.append(obj)
                seen.add(obj.__name__)

    classes.sort(key=lambda c: (c.category.value, c.__name__))
    return classes


def instantiate_all(package_name: str = "wpop.checks") -> List[Check]:
    return [cls() for cls in discover(package_name)]


def index(checks: List[Check]) -> Dict[str, Check]:
    return {c.id: c for c in checks}