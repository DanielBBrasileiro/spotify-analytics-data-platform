"""AWS Lambda deployment exports for structured JSON telemetry."""

from spotify_data_platform.lambda_runtime import (
    JsonLogFormatter,
    LambdaEvent,
    LambdaTelemetryLogger,
    configure_lambda_logger,
)

__all__ = [
    "JsonLogFormatter",
    "LambdaEvent",
    "LambdaTelemetryLogger",
    "configure_lambda_logger",
]
