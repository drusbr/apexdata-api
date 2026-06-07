"""Utilities to turn pandas/numpy objects into JSON-safe plain Python types."""
import math
import numpy as np
import pandas as pd
from typing import Any


def _scalar(val: Any) -> Any:
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(val, np.bool_):
        return bool(val)
    if isinstance(val, pd.Timedelta):
        total = val.total_seconds()
        return None if math.isnan(total) else total
    if isinstance(val, pd.Timestamp):
        return val.isoformat() if not pd.isnull(val) else None
    if val is pd.NaT:
        return None
    return val


def serialize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [serialize(v) for v in obj]
    if isinstance(obj, pd.DataFrame):
        return [serialize(row) for row in obj.to_dict(orient="records")]
    if isinstance(obj, pd.Series):
        return serialize(obj.to_dict())
    return _scalar(obj)


def dataframe_to_records(df: pd.DataFrame) -> list[dict]:
    return serialize(df)
