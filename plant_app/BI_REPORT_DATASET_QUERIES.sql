/*
  Starter dataset queries for Power BI Report Builder or SQL-backed report pages.

  Expected parameter:
    @RunId INT

  Optional picker query included at the top for a run-selection parameter.
*/

/* Available values for a RunId parameter */
SELECT TOP (250)
    h.run_id,
    h.run_label,
    h.product_name,
    h.run_status,
    h.created_at,
    h.created_at_ts
FROM dbo.vw_bi_run_packet_header h
ORDER BY
    COALESCE(h.created_at_ts, CONVERT(datetime2(0), '1900-01-01T00:00:00', 126)) DESC,
    h.run_id DESC;


/* Main packet header */
SELECT
    h.run_id,
    h.run_label,
    h.batch_number,
    h.split_batch_number,
    h.blend_number,
    h.run_number,
    h.batch_type,
    h.product_name,
    h.shift_name,
    h.operator_id,
    h.run_notes,
    h.run_status,
    h.finalized_at,
    h.finalized_by,
    h.created_at,
    h.updated_at
FROM dbo.vw_bi_run_packet_header h
WHERE h.run_id = @RunId;


/* Section list in print order */
SELECT
    s.run_id,
    s.section_order,
    s.section_key,
    s.section_title,
    s.source_entry_id,
    s.entry_date,
    s.operator_initials,
    s.employee,
    s.stage_notes,
    s.created_at
FROM dbo.vw_bi_run_packet_sections s
WHERE s.run_id = @RunId
ORDER BY
    s.section_order,
    s.section_title;


/* Evaporation summary section */
SELECT
    e.run_id,
    e.run_label,
    e.evaporation_entry_id,
    e.employee,
    e.operator_initials,
    e.entry_date,
    e.evaporator_no,
    e.startup_time,
    e.shutdown_time,
    e.feed_ri,
    e.concentrate_ri,
    e.steam_pressure,
    e.vacuum,
    e.sump_level,
    e.product_temp,
    e.stage_notes,
    e.created_at
FROM dbo.vw_bi_latest_evaporation e
WHERE e.run_id = @RunId;


/* Evaporation hourly readings */
SELECT
    r.run_id,
    r.evaporation_entry_id,
    r.table_title,
    r.row_no,
    r.row_time,
    r.feed_rate,
    r.evap_temp,
    r.row_vacuum,
    r.row_concentrate_ri
FROM dbo.vw_bi_latest_evaporation_rows r
WHERE r.run_id = @RunId
ORDER BY
    r.row_no;


/* Generic stage header fields */
SELECT
    f.run_id,
    f.stage_order,
    f.stage_key,
    f.stage_title,
    f.sheet_name,
    f.sheet_entry_id,
    f.field_order,
    f.field_key,
    f.field_label,
    f.field_value,
    f.entry_date,
    f.operator_initials,
    f.employee,
    f.stage_notes,
    f.created_at
FROM dbo.vw_bi_stage_fields f
WHERE f.run_id = @RunId
ORDER BY
    f.stage_order,
    f.field_order;


/* Generic stage table rows */
SELECT
    r.run_id,
    r.stage_order,
    r.stage_key,
    r.stage_title,
    r.sheet_name,
    r.sheet_entry_id,
    r.table_order,
    r.table_key,
    r.table_title,
    r.row_no,
    r.row_key,
    r.populated_cell_count,
    r.entry_date,
    r.operator_initials,
    r.employee,
    r.stage_notes,
    r.created_at
FROM dbo.vw_bi_stage_table_rows r
WHERE r.run_id = @RunId
ORDER BY
    r.stage_order,
    r.table_order,
    r.row_no;


/* Generic stage table cells, ready for matrix/tablix rendering */
SELECT
    c.run_id,
    c.stage_order,
    c.stage_key,
    c.stage_title,
    c.sheet_name,
    c.sheet_entry_id,
    c.table_order,
    c.table_key,
    c.table_title,
    c.row_no,
    c.row_key,
    c.column_order,
    c.column_key,
    c.column_label,
    c.cell_value,
    c.entry_date,
    c.operator_initials,
    c.employee,
    c.stage_notes,
    c.created_at
FROM dbo.vw_bi_stage_table_cells c
WHERE c.run_id = @RunId
ORDER BY
    c.stage_order,
    c.table_order,
    c.row_no,
    c.column_order;
