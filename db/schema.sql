-- F1 Performance Analytics: core schema (Phase 1)
-- Raw layer: events, sessions, entries, laps, weather, telemetry
-- Derived layer: lap_features, stint_metrics, driver_session_pace, teammate_deltas

CREATE TABLE teams (
  team_id      SERIAL PRIMARY KEY,
  name         TEXT NOT NULL,
  season       INT  NOT NULL,
  UNIQUE (name, season)
);

CREATE TABLE drivers (
  driver_id    SERIAL PRIMARY KEY,
  code         CHAR(3) NOT NULL UNIQUE,
  full_name    TEXT NOT NULL,
  number       INT
);

CREATE TABLE events (
  event_id     SERIAL PRIMARY KEY,
  season       INT  NOT NULL,
  round        INT  NOT NULL,
  name         TEXT NOT NULL,
  circuit      TEXT NOT NULL,
  country      TEXT,
  event_date   DATE,
  format       TEXT,
  UNIQUE (season, round)
);

CREATE TABLE sessions (
  session_id   SERIAL PRIMARY KEY,
  event_id     INT NOT NULL REFERENCES events ON DELETE CASCADE,
  kind         TEXT NOT NULL CHECK (kind IN ('FP1','FP2','FP3','Q','SQ','S','R')),
  start_utc    TIMESTAMPTZ,
  total_laps   INT,
  UNIQUE (event_id, kind)
);

CREATE TABLE entries (
  entry_id     SERIAL PRIMARY KEY,
  session_id   INT NOT NULL REFERENCES sessions ON DELETE CASCADE,
  driver_id    INT NOT NULL REFERENCES drivers,
  team_id      INT NOT NULL REFERENCES teams,
  grid_pos     INT,
  finish_pos   INT,
  status       TEXT,
  points       NUMERIC(4,1),
  UNIQUE (session_id, driver_id)
);

CREATE TABLE laps (
  lap_id         BIGSERIAL PRIMARY KEY,
  entry_id       INT NOT NULL REFERENCES entries ON DELETE CASCADE,
  lap_number     INT NOT NULL,
  lap_time_s     NUMERIC(8,3),
  s1_s           NUMERIC(8,3),
  s2_s           NUMERIC(8,3),
  s3_s           NUMERIC(8,3),
  speed_i1       NUMERIC(6,1),
  speed_i2       NUMERIC(6,1),
  speed_fl       NUMERIC(6,1),
  speed_st       NUMERIC(6,1),
  compound       TEXT,
  tyre_age       INT,
  fresh_tyre     BOOLEAN,
  stint_number   INT,
  position       INT,
  pit_in         BOOLEAN DEFAULT FALSE,
  pit_out        BOOLEAN DEFAULT FALSE,
  track_status   TEXT,
  is_accurate    BOOLEAN,
  deleted        BOOLEAN DEFAULT FALSE,
  UNIQUE (entry_id, lap_number)
);
CREATE INDEX laps_entry_idx ON laps (entry_id);

CREATE TABLE weather (
  session_id   INT NOT NULL REFERENCES sessions ON DELETE CASCADE,
  minute       INT NOT NULL,
  air_temp_c   NUMERIC(4,1),
  track_temp_c NUMERIC(4,1),
  humidity     NUMERIC(4,1),
  pressure_hpa NUMERIC(6,1),
  wind_speed   NUMERIC(4,1),
  wind_dir     INT,
  rainfall     BOOLEAN,
  PRIMARY KEY (session_id, minute)
);

CREATE TABLE telemetry (
  lap_id       BIGINT NOT NULL REFERENCES laps ON DELETE CASCADE,
  distance_m   NUMERIC(8,1) NOT NULL,
  speed        NUMERIC(6,1),
  throttle     NUMERIC(5,1),
  brake        BOOLEAN,
  gear         SMALLINT,
  rpm          INT,
  drs          SMALLINT,
  x            NUMERIC(9,1),
  y            NUMERIC(9,1),
  PRIMARY KEY (lap_id, distance_m)
);

-- Derived layer
CREATE TABLE lap_features (
  lap_id           BIGINT PRIMARY KEY REFERENCES laps ON DELETE CASCADE,
  is_clean         BOOLEAN NOT NULL,
  exclude_reason   TEXT,
  fuel_corr_time_s NUMERIC(8,3),
  model_version    TEXT NOT NULL
);

CREATE TABLE stint_metrics (
  entry_id        INT NOT NULL REFERENCES entries ON DELETE CASCADE,
  stint_number    INT NOT NULL,
  compound        TEXT,
  n_laps          INT,
  n_clean         INT,
  mean_pace_s     NUMERIC(8,3),
  deg_s_per_lap   NUMERIC(7,4),
  deg_se          NUMERIC(7,4),
  consistency_sd  NUMERIC(7,4),
  PRIMARY KEY (entry_id, stint_number)
);

CREATE TABLE driver_session_pace (
  entry_id       INT PRIMARY KEY REFERENCES entries ON DELETE CASCADE,
  median_pace_s  NUMERIC(8,3),
  n_clean        INT,
  best_lap_s     NUMERIC(8,3),
  consistency_sd NUMERIC(7,4)
);

CREATE TABLE teammate_deltas (
  session_id   INT NOT NULL REFERENCES sessions ON DELETE CASCADE,
  driver_a     INT NOT NULL REFERENCES drivers,
  driver_b     INT NOT NULL REFERENCES drivers,
  metric       TEXT NOT NULL,
  delta_s      NUMERIC(8,4),
  ci_low       NUMERIC(8,4),
  ci_high      NUMERIC(8,4),
  n_a INT, n_b INT,
  PRIMARY KEY (session_id, driver_a, driver_b, metric)
);
