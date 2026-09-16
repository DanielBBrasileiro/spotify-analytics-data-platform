"""CC0 Bronze -> Glue -> exact Landing readiness -> dbt -> serving data.

Tracks #23-#25, #27-#28. Manual schedule keeps cloud spending explicit.
"""

import os
from datetime import UTC, datetime, timedelta

from airflow.sdk import Param, PokeReturnValue, dag, get_current_context, task, task_group
from airflow.sdk.definitions.callback import SyncCallback
from airflow.sdk.definitions.deadline import DeadlineAlert, DeadlineReference


def _dag_failure_callback(context):
    """Lazy runtime import keeps DAG parsing independent from service credentials."""
    from spotify_tasks import dag_failure_callback

    return dag_failure_callback(context)


@dag(
    dag_id="spotify_daily_snapshot",
    start_date=datetime(2026, 9, 1, tzinfo=UTC),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    max_active_tasks=4,
    dagrun_timeout=timedelta(hours=2),
    deadline=DeadlineAlert(
        reference=DeadlineReference.DAGRUN_QUEUED_AT,
        interval=timedelta(hours=2),
        callback=SyncCallback("spotify_tasks.deadline_missed_callback"),
    ),
    on_failure_callback=_dag_failure_callback,
    default_args={
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
        "retry_exponential_backoff": True,
        "execution_timeout": timedelta(minutes=5),
    },
    params={
        "start_date": Param("2026-09-10", type="string", format="date"),
        "end_date": Param("2026-09-12", type="string", format="date"),
    },
    tags=["spotify", "cc0-demo", "synthetic", "serving"],
)
def spotify_daily_snapshot():
    @task
    def prepare():
        from spotify_tasks import write_report

        from spotify_data_platform.orchestration.contracts import plan_demo

        context = get_current_context()
        # Resolve settings inside task execution; never read secrets at DAG parse time.
        for setting in (
            "SPOTIFY_LAKE_BUCKET",
            "SPOTIFY_GLUE_JOB_NAME",
            "SNOWFLAKE_ACCOUNT",
            "SNOWFLAKE_USER",
        ):
            if not os.environ.get(setting):
                raise ValueError(f"Configure {setting} before triggering the DAG.")
        if not (
            os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH") or os.environ.get("SNOWFLAKE_PASSWORD")
        ):
            raise ValueError("Configure Snowflake authentication before triggering the DAG.")
        plan = plan_demo(
            os.environ.get("DEMO_MANIFEST_PATH", "/opt/airflow/demo/manifest.json"),
            context["params"]["start_date"],
            context["params"]["end_date"],
            context["run_id"],
        )
        plan["started_at"] = datetime.now(UTC).isoformat()
        write_report(context["run_id"], "plan.json", plan)
        return plan

    @task
    def records(plan):
        return plan["records"]

    @task_group
    def curate(record):
        @task
        def upload(record):
            from spotify_tasks import upload_bronze

            return upload_bronze(record, os.environ["SPOTIFY_LAKE_BUCKET"])

        @task(retries=0)
        def submit(record):
            from spotify_tasks import submit_glue, write_report

            job = submit_glue(
                record, os.environ["SPOTIFY_LAKE_BUCKET"], os.environ["SPOTIFY_GLUE_JOB_NAME"]
            )
            write_report(
                get_current_context()["run_id"], f"glue-{record['pipeline_run_id']}.json", job
            )
            return job

        @task.sensor(poke_interval=30, timeout=3600, mode="reschedule", retries=0)
        def await_glue(job):
            from spotify_tasks import glue_finished

            return PokeReturnValue(is_done=glue_finished(job), xcom_value=job)

        @task.sensor(poke_interval=30, timeout=900, mode="reschedule", retries=0)
        def await_landing(job):
            from spotify_tasks import check_landing

            ready = check_landing(
                job, os.environ["SPOTIFY_LAKE_BUCKET"], get_current_context()["run_id"]
            )
            return PokeReturnValue(is_done=ready, xcom_value=job["record"]["pipeline_run_id"])

        return await_landing(await_glue(submit(upload(record))))

    @task(retries=1, execution_timeout=timedelta(minutes=35))
    def transform(plan):
        from spotify_tasks import build_dbt

        return build_dbt(plan)

    @task(trigger_rule="all_done", retries=0)
    def report():
        from spotify_tasks import artifact_dir, write_report

        context = get_current_context()
        # Pull optional results here, rather than resolving failed task outputs as inputs.
        result = context["ti"].xcom_pull(task_ids="transform")
        plan = context["ti"].xcom_pull(task_ids="prepare")
        payload = {
            "airflow_run_id": context["run_id"],
            "status": "success" if result else "failed",
            "started_at": plan.get("started_at") if plan else None,
            "finished_at": datetime.now(UTC).isoformat(),
            "dbt": result,
            "evidence_files": sorted(
                p.name for p in artifact_dir(context["run_id"]).glob("*.json")
            ),
        }
        write_report(context["run_id"], "run-summary.json", payload)
        if not result:
            # An all_done leaf must not turn a failed upstream run green.
            raise ValueError("Pipeline incomplete; see task logs and run-summary.json.")
        return payload

    plan = prepare()
    ready = curate.expand(record=records(plan))
    built = transform(plan)
    ready >> built
    built >> report()


spotify_daily_snapshot()
