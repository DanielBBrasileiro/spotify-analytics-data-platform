{% macro snapshot_window_predicate(column_name) -%}
  {%- set snapshot_date = var('snapshot_date', none) -%}
  {%- set start_date = var('start_date', none) -%}
  {%- set end_date = var('end_date', none) -%}

  {%- if execute -%}
    {%- if snapshot_date and (start_date or end_date) -%}
      {{ exceptions.raise_compiler_error(
          "Use either snapshot_date or start_date/end_date, never both."
      ) }}
    {%- endif -%}
    {%- if (start_date and not end_date) or (end_date and not start_date) -%}
      {{ exceptions.raise_compiler_error(
          "Historical backfills require both start_date and end_date."
      ) }}
    {%- endif -%}
    {%- if not snapshot_date and not (start_date and end_date) -%}
      {{ exceptions.raise_compiler_error(
          "Set snapshot_date for a daily run or start_date/end_date for a backfill."
      ) }}
    {%- endif -%}
    {%- if start_date and end_date and start_date > end_date -%}
      {{ exceptions.raise_compiler_error("start_date must not be after end_date.") }}
    {%- endif -%}
  {%- endif -%}

  {%- if snapshot_date -%}
    {{ column_name }} = to_date('{{ snapshot_date | replace("'", "''") }}')
  {%- elif start_date and end_date -%}
    {{ column_name }} between
      to_date('{{ start_date | replace("'", "''") }}')
      and to_date('{{ end_date | replace("'", "''") }}')
  {%- else -%}
    1 = 1
  {%- endif -%}
{%- endmacro %}

