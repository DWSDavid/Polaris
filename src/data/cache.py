"""Parquet cache keyed by source, dataset, and key."""

from pathlib import Path

import pandas as pd

CACHE_DIR = Path("data/cache")


def _path(source: str, dataset: str, key: str) -> Path:
    return CACHE_DIR / source / dataset / f"{key}.parquet"


def write(source: str, dataset: str, key: str, df: pd.DataFrame) -> None:
    path = _path(source, dataset, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def read(source: str, dataset: str, key: str):
    path = _path(source, dataset, key)
    return pd.read_parquet(path) if path.exists() else None


def exists(source: str, dataset: str, key: str) -> bool:
    return _path(source, dataset, key).exists()
