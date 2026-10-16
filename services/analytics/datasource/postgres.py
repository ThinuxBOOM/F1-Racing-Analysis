"""PostgreSQL-backed source (data loaded by services/ingest). Same frames as the mock source.
NOTE: not yet exercised against a live database."""
from __future__ import annotations
import os
import pandas as pd
import psycopg

LAPS_Q = """SELECT ev.season, ev.round, s.kind, d.code AS driver, t.name AS team,
  l.lap_number, l.lap_time_s, l.s1_s, l.s2_s, l.s3_s, l.speed_st, l.compound, l.tyre_age,
  l.stint_number, l.position, l.pit_in, l.pit_out, l.track_status, l.deleted
  FROM laps l JOIN entries e ON e.entry_id=l.entry_id JOIN drivers d ON d.driver_id=e.driver_id
  JOIN teams t ON t.team_id=e.team_id JOIN sessions s ON s.session_id=e.session_id
  JOIN events ev ON ev.event_id=s.event_id
  WHERE ev.season=%s AND ev.round=%s AND s.kind=%s ORDER BY d.code, l.lap_number"""

RESULTS_Q = """SELECT ev.season, ev.round, s.kind, d.code AS driver, t.name AS team,
  e.grid_pos, e.finish_pos, e.status, e.points, e.laps_completed
  FROM entries e JOIN drivers d ON d.driver_id=e.driver_id JOIN teams t ON t.team_id=e.team_id
  JOIN sessions s ON s.session_id=e.session_id JOIN events ev ON ev.event_id=s.event_id
  WHERE ev.season=%s AND ev.round=%s AND s.kind=%s"""

EVENTS_Q = """SELECT ev.season, ev.round, ev.name, ev.circuit, ev.country,
  (SELECT MAX(total_laps) FROM sessions s WHERE s.event_id=ev.event_id) AS total_laps,
  c.length_km FROM events ev LEFT JOIN circuits c ON c.circuit_id=ev.circuit_id
  WHERE ev.season=%s ORDER BY ev.round"""

PITS_Q = """SELECT ev.season, ev.round, d.code AS driver, p.lap, p.duration_s,
  p.position_before, p.position_after
  FROM pit_stops p JOIN entries e ON e.entry_id=p.entry_id JOIN drivers d ON d.driver_id=e.driver_id
  JOIN sessions s ON s.session_id=e.session_id JOIN events ev ON ev.event_id=s.event_id
  WHERE ev.season=%s AND ev.round=%s"""


class PostgresSource:
    name = "postgres"

    def __init__(self):
        self.dsn = os.environ["DATABASE_URL"]

    @property
    def is_mock(self) -> bool:
        with psycopg.connect(self.dsn) as c, c.cursor() as cur:
            cur.execute("SELECT COALESCE(bool_or(is_mock), FALSE) FROM sessions")
            return bool(cur.fetchone()[0])

    def _q(self, sql, params):
        with psycopg.connect(self.dsn) as c:
            return pd.read_sql(sql, c, params=params)

    def seasons(self): return [int(x) for x in self._q("SELECT season FROM seasons ORDER BY season", None)["season"]]
    def events(self, season): return self._q(EVENTS_Q, (season,))
    def laps(self, season, rnd, kind):
        df = self._q(LAPS_Q, (season, rnd, kind))
        for c in ("lap_time_s", "s1_s", "s2_s", "s3_s", "speed_st"):
            df[c] = df[c].astype(float)
        return df
    def results(self, season, rnd, kind): return self._q(RESULTS_Q, (season, rnd, kind))
    def pit_stops(self, season, rnd): return self._q(PITS_Q, (season, rnd))

    def telemetry(self, season, rnd, kind, driver, lap_number):
        sql = """SELECT t.distance_m, t.speed, t.throttle, t.brake, t.gear, t.drs, t.x, t.y
          FROM telemetry t JOIN laps l ON l.lap_id=t.lap_id
          JOIN entries e ON e.entry_id=l.entry_id JOIN drivers d ON d.driver_id=e.driver_id
          JOIN sessions s ON s.session_id=e.session_id JOIN events ev ON ev.event_id=s.event_id
          WHERE ev.season=%s AND ev.round=%s AND s.kind=%s AND d.code=%s AND l.lap_number=%s
          ORDER BY t.distance_m"""
        return self._q(sql, (season, rnd, kind, driver, int(lap_number)))

    def weather(self, season, rnd, kind="R"):
        sql = """SELECT w.minute, w.air_temp_c, w.track_temp_c, w.humidity,
          w.pressure_hpa, w.wind_speed, w.wind_dir, w.rainfall
          FROM weather w JOIN sessions s ON s.session_id=w.session_id
          JOIN events ev ON ev.event_id=s.event_id
          WHERE ev.season=%s AND ev.round=%s AND s.kind=%s ORDER BY w.minute"""
        try:
            return self._q(sql, (season, rnd, kind))
        except Exception:
            return __import__("pandas").DataFrame()
