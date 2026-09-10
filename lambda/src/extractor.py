"""AWS Lambda deployment entrypoint for the Spotify Bronze extractor."""

from spotify_data_platform.lambda_runtime import lambda_handler

__all__ = ["lambda_handler"]
