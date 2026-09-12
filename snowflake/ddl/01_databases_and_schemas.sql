-- M4 warehouse topology contract. Execute only during the later cloud-validation phase.
-- Deployment is expected to run under a separately controlled administrative role.

CREATE DATABASE IF NOT EXISTS SPOTIFY_ANALYTICS
  COMMENT = 'Synthetic-first Spotify Analytics portfolio warehouse';

CREATE SCHEMA IF NOT EXISTS SPOTIFY_ANALYTICS.LANDING
  COMMENT = 'Typed 1:1 representation of curated Silver Parquet';
CREATE SCHEMA IF NOT EXISTS SPOTIFY_ANALYTICS.STAGING
  COMMENT = 'dbt staging views and source normalization';
CREATE SCHEMA IF NOT EXISTS SPOTIFY_ANALYTICS.CORE
  COMMENT = 'Kimball dimensions, bridge, and snapshot fact';
CREATE SCHEMA IF NOT EXISTS SPOTIFY_ANALYTICS.MARTS
  COMMENT = 'Curated analytical models consumed by BI';

-- Current Snowflake SQL spells the smallest standard warehouse size as XSMALL.
CREATE WAREHOUSE IF NOT EXISTS COMPUTE_WH
  WAREHOUSE_TYPE = STANDARD
  WAREHOUSE_SIZE = XSMALL
  MIN_CLUSTER_COUNT = 1
  MAX_CLUSTER_COUNT = 1
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Cost-bounded development warehouse for dbt and analytical validation';

-- Converge mutable settings when the warehouse already exists.
ALTER WAREHOUSE COMPUTE_WH SET
  WAREHOUSE_SIZE = XSMALL
  MIN_CLUSTER_COUNT = 1
  MAX_CLUSTER_COUNT = 1
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE;
