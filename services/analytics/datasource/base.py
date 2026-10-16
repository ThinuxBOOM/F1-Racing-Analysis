"""The contract every data layer must satisfy.

All frames use the same column names whether they come from the mock generator, PostgreSQL
(populated from FastF1) or any future source. Analytics code only ever sees these frames.
"""
from __future__ import annotations
from typing import Protocol
import pandas as pd

LAP_COLUMNS = ["season", "round", "kind", "driver", "team", "lap_number", "lap_time_s",
               "s1_s", "s2_s", "s3_s", "speed_st", "compound", "tyre_age", "stint_number",
               "position", "pit_in", "pit_out", "track_status", "deleted"]
RESULT_COLUMNS = ["season", "round", "kind", "driver", "team", "grid_pos", "finish_pos",
                  "status", "points", "laps_completed"]
PIT_COLUMNS = ["season", "round", "driver", "lap", "duration_s", "position_before", "position_after"]
EVENT_COLUMNS = ["season", "round", "name", "circuit", "country", "total_laps", "length_km"]
TELEMETRY_COLUMNS = ["distance_m", "speed", "throttle", "brake", "gear", "drs", "x", "y"]


class DataSource(Protocol):
    name: str          # e.g. "mock", "fastf1-postgres"
    is_mock: bool      # surfaced to the UI so demo data is always labelled

    def events(self, season: int) -> pd.DataFrame: ...
    def laps(self, season: int, rnd: int, kind: str) -> pd.DataFrame: ...
    def results(self, season: int, rnd: int, kind: str) -> pd.DataFrame: ...
    def pit_stops(self, season: int, rnd: int) -> pd.DataFrame: ...
    def seasons(self) -> list[int]: ...
    def weather(self, season: int, rnd: int, kind: str = "R") -> pd.DataFrame: ...
    def telemetry(self, season: int, rnd: int, kind: str, driver: str, lap_number: int) -> pd.DataFrame: ...
