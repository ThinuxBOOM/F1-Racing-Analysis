-- Extension to the Phase 1 schema, covering the full data model in the brief.
-- Every session records where its data came from, so demo data can never be mistaken for real data.

CREATE TABLE seasons (
  season       INT PRIMARY KEY,
  notes        TEXT
);

CREATE TABLE circuits (
  circuit_id       SERIAL PRIMARY KEY,
  name             TEXT NOT NULL UNIQUE,
  country          TEXT,
  length_km        NUMERIC(5,3),
  number_of_laps   INT,
  -- Data-derived characteristics (see methodology). NULL until computed; never hand-labelled.
  avg_speed_kmh    NUMERIC(6,1),
  full_throttle_pct NUMERIC(5,1),
  braking_zones    INT,
  mean_deg_s_per_lap NUMERIC(6,4),
  overtake_index   NUMERIC(6,3)
);

ALTER TABLE events   ADD COLUMN circuit_id INT REFERENCES circuits;
ALTER TABLE events   ADD CONSTRAINT events_season_fk FOREIGN KEY (season) REFERENCES seasons;
ALTER TABLE sessions ADD COLUMN data_source TEXT NOT NULL DEFAULT 'fastf1'
  CHECK (data_source IN ('fastf1','openf1','ergast','mock'));
ALTER TABLE sessions ADD COLUMN is_mock BOOLEAN GENERATED ALWAYS AS (data_source = 'mock') STORED;

ALTER TABLE teams ADD COLUMN constructor TEXT;
ALTER TABLE drivers ADD COLUMN nationality TEXT;

CREATE TABLE cars (
  car_id       SERIAL PRIMARY KEY,
  team_id      INT NOT NULL REFERENCES teams,
  chassis      TEXT,
  power_unit   TEXT,
  UNIQUE (team_id)
);

ALTER TABLE entries ADD COLUMN laps_completed INT;
ALTER TABLE entries ADD COLUMN fastest_lap BOOLEAN DEFAULT FALSE;

CREATE TABLE stints (
  stint_id       SERIAL PRIMARY KEY,
  entry_id       INT NOT NULL REFERENCES entries ON DELETE CASCADE,
  stint_number   INT NOT NULL,
  compound       TEXT,
  start_lap      INT,
  end_lap        INT,
  start_tyre_age INT,
  UNIQUE (entry_id, stint_number)
);

CREATE TABLE pit_stops (
  pit_id          SERIAL PRIMARY KEY,
  entry_id        INT NOT NULL REFERENCES entries ON DELETE CASCADE,
  lap             INT NOT NULL,
  duration_s      NUMERIC(6,3),      -- pit-lane time; stationary time is not in public timing data
  position_before INT,
  position_after  INT
);

CREATE TABLE incidents (
  incident_id  SERIAL PRIMARY KEY,
  session_id   INT NOT NULL REFERENCES sessions ON DELETE CASCADE,
  lap          INT,
  entry_id     INT REFERENCES entries,
  type         TEXT NOT NULL,         -- safety_car | vsc | red_flag | collision | retirement ...
  severity     TEXT
);

-- Output of the data-quality detector (one row per entry per session)
CREATE TABLE data_quality (
  entry_id          INT PRIMARY KEY REFERENCES entries ON DELETE CASCADE,
  laps_expected     INT,
  laps_present      INT,
  laps_missing_time INT,
  laps_pit          INT,
  laps_neutralised  INT,
  laps_outlier      INT,
  laps_clean        INT,
  completeness      NUMERIC(5,3)     -- laps_clean / laps_present
);
