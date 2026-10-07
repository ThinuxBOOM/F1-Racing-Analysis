import os
from .base import DataSource


def get_source() -> DataSource:
    """Pick the data layer from DATA_SOURCE (default: mock). The API and analytics never
    import a concrete source, so swapping the data layer needs no change elsewhere."""
    kind = os.getenv("DATA_SOURCE", "mock").lower()
    if kind == "mock":
        from .mock import MockSource
        return MockSource()
    if kind == "postgres":
        from .postgres import PostgresSource
        return PostgresSource()
    raise ValueError(f"unknown DATA_SOURCE {kind!r}")
