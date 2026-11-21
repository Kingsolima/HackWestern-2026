-- Tiger Data schema (ARCHITECTURE §4). Runs on Tiger Cloud or the local timescaledb container.
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- One row per TinyFish agent run. Evidence that the agents hold up on live sites.
CREATE TABLE IF NOT EXISTS agent_runs (
  time        TIMESTAMPTZ NOT NULL DEFAULT now(),
  run_id      TEXT        NOT NULL,
  site        TEXT        NOT NULL,
  product     TEXT,
  status      TEXT        NOT NULL,  -- success | blocked | not_found | auth_required | incomplete
  duration_s  DOUBLE PRECISION,
  steps       INTEGER
);
SELECT create_hypertable('agent_runs', by_range('time'), if_not_exists => TRUE);

CREATE MATERIALIZED VIEW IF NOT EXISTS site_success_hourly
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 hour', time) AS bucket,
       site,
       count(*)                                   AS runs,
       count(*) FILTER (WHERE status = 'success') AS successes
FROM agent_runs
GROUP BY bucket, site
WITH NO DATA;

SELECT add_continuous_aggregate_policy('site_success_hourly',
  start_offset => INTERVAL '1 day', end_offset => NULL,
  schedule_interval => INTERVAL '5 minutes', if_not_exists => TRUE);

-- Price/lead-time history from repeated runs and TinyMonitor events.
CREATE TABLE IF NOT EXISTS price_observations (
  time            TIMESTAMPTZ NOT NULL DEFAULT now(),
  part_number     TEXT        NOT NULL,
  supplier        TEXT        NOT NULL,
  price_usd       NUMERIC(12,2),
  lead_time_days  DOUBLE PRECISION,
  origin          TEXT,
  run_id          TEXT
);
SELECT create_hypertable('price_observations', by_range('time'), if_not_exists => TRUE);

-- Audit trail behind each Pass / Review / Rejected.
CREATE TABLE IF NOT EXISTS check_results (
  time       TIMESTAMPTZ NOT NULL DEFAULT now(),
  design_id  TEXT        NOT NULL,
  candidate  TEXT        NOT NULL,
  "check"    TEXT        NOT NULL,
  value      DOUBLE PRECISION,
  threshold  DOUBLE PRECISION,
  pass       BOOLEAN
);
SELECT create_hypertable('check_results', by_range('time'), if_not_exists => TRUE);

-- Relational table alongside the hypertables.
CREATE TABLE IF NOT EXISTS design_variants (
  design_id     TEXT PRIMARY KEY,
  objective     TEXT NOT NULL CHECK (objective IN ('cost', 'performance', 'us_first')),
  motor         TEXT NOT NULL,
  cost_usd      NUMERIC(12,2) NOT NULL,
  domestic_pct  DOUBLE PRECISION NOT NULL,
  glb_url       TEXT,
  step_url      TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
