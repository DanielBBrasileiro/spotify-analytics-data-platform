.PHONY: help setup lint format format-check test spark-test check check-quality clean airflow-up airflow-down airflow-test

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
	@echo "make check-quality - Run cross-tier data-quality contract gates"
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

check-quality:
	$(BIN)/pytest tests/unit/test_orchestration_contracts.py -q
	AIRFLOW_HOME=$(CURDIR)/tmp/airflow-quality AIRFLOW__CORE__LOAD_EXAMPLES=false \
		.venv-airflow/bin/pytest tests/orchestration -q
	@test -n "$$JAVA_HOME" || (echo "JAVA_HOME must point to a Java 17 installation" && exit 1)
	SPARK_LOCAL_IP=127.0.0.1 PYSPARK_PYTHON=$(CURDIR)/.venv-spark/bin/python \
		.venv-spark/bin/pytest tests/spark -q
	DBT_SEND_ANONYMOUS_USAGE_STATS=false .venv-dbt/bin/dbt parse --no-partial-parse \
		--project-dir dbt --profiles-dir tests/dbt_profile
	.venv-dbt/bin/pytest tests/dbt -q


airflow-up:
	mkdir -p airflow/logs airflow/artifacts airflow/secrets
	docker compose -f airflow/docker-compose.yml up --build -d

airflow-down:
	docker compose -f airflow/docker-compose.yml down

airflow-test:
	AIRFLOW_HOME=$(CURDIR)/tmp/airflow-test AIRFLOW__CORE__LOAD_EXAMPLES=false \
		.venv-airflow/bin/pytest tests/orchestration -q

clean:
	rm -rf build/ dist/ *.egg-info .eggs/
	rm -rf .pytest_cache/ .ruff_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
