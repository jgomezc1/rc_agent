"""
memory.py
---------
Lightweight persistence / loader utilities.

Key change: switched from beam‑level `shop_drawings.json` to the
summary‑level `rs_summaries.json`.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import List, Dict, Any

DEFAULT_JSON = Path("../data/rs_summaries.json")


@lru_cache(maxsize=1)
def load_rs_summaries(file_path: str | os.PathLike = DEFAULT_JSON) -> List[Dict[str, Any]]:
    """
    Read the RS‑level summary file and return a **list of dicts**.

    Each dict contains:
        id, steel_tonnage, concrete_volume, steel_cost, concrete_cost,
        manhours, duration_days, co2_tonnes, constructibility_index,
        bar_geometries
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(path)

    with path.open(encoding="utf-8") as f:
        raw = json.load(f)

    # Flatten {id: metrics_dict} → list[dict]
    return [{"id": rs_id, **metrics} for rs_id, metrics in raw.items()]


# ------------------------------------------------------------------ #
# Legacy alias so older calls keep working until fully refactored
# ------------------------------------------------------------------ #
def load_shop_drawings(file_path: str | os.PathLike = DEFAULT_JSON) -> List[Dict[str, Any]]:  # noqa
    """Alias for backward compatibility."""
    return load_rs_summaries(file_path)