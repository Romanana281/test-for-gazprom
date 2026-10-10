from collections.abc import Sequence
from statistics import median

from app.models import Metric


def calculate(metrics: Sequence[Metric]) -> dict:
    return {
        "x": _calculate([m.x for m in metrics]),
        "y": _calculate([m.y for m in metrics]),
        "z": _calculate([m.z for m in metrics]),
    }


def _calculate(values: list[float]) -> dict:
    if not values:
        return {"min": None, "max": None, "count": 0, "sum": 0.0, "median": None}

    return {
        "min": min(values),
        "max": max(values),
        "count": len(values),
        "sum": sum(values),
        "median": median(values),
    }
