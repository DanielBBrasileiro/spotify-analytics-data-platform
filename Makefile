.PHONY: help setup lint format format-check test spark-test check clean

PYTHON ?= python3
VENV ?= .venv
BIN ?= $(VENV)/bin

help:
	@echo "Spotify Analytics Data Platform - Development Tasks"
	@echo "==================================================="
	@echo "make setup        - Initialize virtualenv and install dev dependencies"
	@echo "make lint         - Run Ruff linter"
	@echo "make format       - Format code with Ruff"
	@echo "make format-check - Check formatting with Ruff"
	@echo "make test         - Run unit tests with pytest"
	@echo "make spark-test   - Run Glue 5.1 parity tests (requires Python 3.11 + Java 17)"
	@echo "make check        - Run all static checks and tests (lint + format-check + test)"
	@echo "make clean        - Remove Python caches and temporary build files"

setup:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e ".[dev]"

lint:
	$(BIN)/ruff check .

format:
	$(BIN)/ruff format .

format-check:
	$(BIN)/ruff format --check .

test:
	$(BIN)/coverage run -m pytest
	$(BIN)/coverage report

spark-test:
	@test -n "$$JAVA_HOME" || (echo "JAVA_HOME must point to a Java 17 installation" && exit 1)
	SPARK_LOCAL_IP=127.0.0.1 PYSPARK_PYTHON=$(CURDIR)/.venv-spark/bin/python \
		.venv-spark/bin/pytest tests/spark

check: lint format-check test

clean:
	rm -rf build/ dist/ *.egg-info .eggs/
	rm -rf .pytest_cache/ .ruff_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
