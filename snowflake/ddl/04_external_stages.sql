-- One stage rooted at the curated Silver prefix. Dataset-specific pipe paths are appended
-- below this root so the storage integration remains narrowly scoped.

CREATE STAGE IF NOT EXISTS SPOTIFY_ANALYTICS.LANDING.SILVER_STAGE
  URL = 's3://__S3_BUCKET__/silver/'
  STORAGE_INTEGRATION = SPOTIFY_S3_INTEGRATION
  DIRECTORY = (ENABLE = TRUE)
  COMMENT = 'Curated Silver Parquet root; cloud wiring deferred to M8';

GRANT USAGE ON STAGE SPOTIFY_ANALYTICS.LANDING.SILVER_STAGE TO ROLE SPOTIFY_LOADER;
