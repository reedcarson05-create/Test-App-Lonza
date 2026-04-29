# BI Reporting Guide

Run [setup_sql_bi_views.sql](/c:/Users/reedc/OneDrive/Test%20App%20Lonza/plant_app/setup_sql_bi_views.sql) after [setup_sql_server.sql](/c:/Users/reedc/OneDrive/Test%20App%20Lonza/plant_app/setup_sql_server.sql). The BI script creates a reporting layer that mirrors the packet shape used by the app's `/runs/print` page.

Starter assets:

- [bi/RunPacketPaginatedReport.rdl](/c:/Users/reedc/OneDrive/Test%20App%20Lonza/plant_app/bi/RunPacketPaginatedReport.rdl)
  A starter paginated Power BI Report Builder file already wired to the SQL reporting views.

- [BI_REPORT_DATASET_QUERIES.sql](/c:/Users/reedc/OneDrive/Test%20App%20Lonza/plant_app/BI_REPORT_DATASET_QUERIES.sql)
  Parameterized dataset queries for a `RunId`-driven report.

- [POWER_BI_PACKET_LAYOUT.md](/c:/Users/reedc/OneDrive/Test%20App%20Lonza/plant_app/POWER_BI_PACKET_LAYOUT.md)
  A starter paginated-report and Power BI page layout that matches the print packet structure.

## Core Views

- `dbo.vw_bi_run_packet_header`
  One row per production run with the same `run_label` logic the app uses in print preview.

- `dbo.vw_bi_run_packet_sections`
  One row per printed section for the latest packet view of each run.

- `dbo.vw_bi_latest_evaporation`
  The latest evaporation sheet saved for each run.

- `dbo.vw_bi_latest_evaporation_rows`
  The hourly reading rows for the latest evaporation sheet.

- `dbo.vw_bi_latest_stage_entries`
  The latest generic stage sheet saved for each run and stage.

- `dbo.vw_bi_stage_fields`
  Header-style field rows for each latest generic stage sheet, already labeled and ordered for reporting.

- `dbo.vw_bi_stage_table_rows`
  Populated logical rows for each latest generic stage table.

- `dbo.vw_bi_stage_table_cells`
  Populated table cell values for each latest generic stage table row.

## Metadata Views

- `dbo.vw_bi_stage_catalog`
- `dbo.vw_bi_stage_field_catalog`
- `dbo.vw_bi_stage_table_catalog`
- `dbo.vw_bi_stage_table_column_catalog`

These mirror the app metadata in [stage_defs.py](/c:/Users/reedc/OneDrive/Test%20App%20Lonza/plant_app/stage_defs.py) so Power BI does not need to hard-code labels or ordering.

## Recommended Power BI Model

- Use `vw_bi_run_packet_header` as the main run dimension.
- Relate `vw_bi_run_packet_header.run_id` to:
  `vw_bi_run_packet_sections.run_id`,
  `vw_bi_latest_evaporation.run_id`,
  `vw_bi_latest_stage_entries.run_id`.
- Relate `vw_bi_latest_stage_entries.sheet_entry_id` to:
  `vw_bi_stage_fields.sheet_entry_id`,
  `vw_bi_stage_table_rows.sheet_entry_id`,
  `vw_bi_stage_table_cells.sheet_entry_id`.
- Relate `vw_bi_stage_table_rows.row_key` to `vw_bi_stage_table_cells.row_key` if you want row-level drill-down visuals.

## Recommended Report Layout

- Use a run slicer based on `run_label`.
- Use cards or a multi-row card for the header view.
- Use a small section navigator or stacked table based on `vw_bi_run_packet_sections`.
- Render generic stage headers from `vw_bi_stage_fields`.
- Render stage tables from `vw_bi_stage_table_cells` in a matrix visual or in a paginated report table grouped by:
  `stage_title`,
  `table_title`,
  `row_no`.

If you want the output to look almost identical to the paper packet, build it in Power BI Report Builder / paginated reports instead of a standard dashboard canvas.
