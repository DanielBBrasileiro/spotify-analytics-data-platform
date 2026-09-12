-- Development cost fuse for COMPUTE_WH. This is a warehouse-credit guardrail, not a
-- dollar-denominated billing guarantee; account/region credit prices can vary.
-- Resource monitors require administrative deployment privileges and are never created
-- by application service roles.

CREATE RESOURCE MONITOR IF NOT EXISTS SPOTIFY_DEV_MONITOR WITH
  CREDIT_QUOTA = 2
  FREQUENCY = MONTHLY
  START_TIMESTAMP = IMMEDIATELY
  TRIGGERS
    ON 80 PERCENT DO NOTIFY
    ON 100 PERCENT DO SUSPEND_IMMEDIATE;

-- IF NOT EXISTS preserves the monitor's identity. Converge quota/actions safely on
-- repeat deployments without resetting the customized monthly schedule start date.
ALTER RESOURCE MONITOR IF EXISTS SPOTIFY_DEV_MONITOR
  SET CREDIT_QUOTA = 2
  TRIGGERS
    ON 80 PERCENT DO NOTIFY
    ON 100 PERCENT DO SUSPEND_IMMEDIATE;

ALTER WAREHOUSE COMPUTE_WH SET
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  STATEMENT_QUEUED_TIMEOUT_IN_SECONDS = 120
  STATEMENT_TIMEOUT_IN_SECONDS = 900
  RESOURCE_MONITOR = SPOTIFY_DEV_MONITOR;

-- Defensive final state for bootstrap sessions. Future workload queries may auto-resume.
ALTER WAREHOUSE COMPUTE_WH SUSPEND;
