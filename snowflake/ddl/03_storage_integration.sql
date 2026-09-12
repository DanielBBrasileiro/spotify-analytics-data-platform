-- Offline template only. Replace the quoted deployment placeholders before the later
-- cloud-validation phase. Never replace this integration in-place once stages depend on it.

CREATE STORAGE INTEGRATION IF NOT EXISTS SPOTIFY_S3_INTEGRATION
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = '__AWS_ROLE_ARN__'
  STORAGE_AWS_EXTERNAL_ID = '__AWS_EXTERNAL_ID__'
  STORAGE_ALLOWED_LOCATIONS = ('s3://__S3_BUCKET__/silver/')
  COMMENT = 'Least-privilege access to the curated Silver prefix only';

GRANT USAGE ON INTEGRATION SPOTIFY_S3_INTEGRATION TO ROLE SPOTIFY_LOADER;

-- During deployment, inspect Snowflake's generated identity and use it in the AWS role
-- trust policy. Do not store the resulting real ARN or account identifiers in Git.
-- DESC INTEGRATION SPOTIFY_S3_INTEGRATION;
