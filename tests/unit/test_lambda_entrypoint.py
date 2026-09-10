"""Deployment entrypoint wiring for AWS Lambda zip/container packaging."""

import importlib.util
from pathlib import Path

from spotify_data_platform.lambda_runtime import lambda_handler


def test_lambda_extractor_entrypoint_reexports_runtime_handler():
    path = Path(__file__).parents[2] / "lambda" / "src" / "extractor.py"
    spec = importlib.util.spec_from_file_location("lambda_extractor_entrypoint", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.lambda_handler is lambda_handler
