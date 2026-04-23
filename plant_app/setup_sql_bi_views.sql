/*
  Plant App BI/reporting views

  Run this after setup_sql_server.sql.
  These views mirror the latest-per-run packet used by /runs/print so Power BI
  or paginated reports can render the same sections without re-implementing the
  FastAPI packet-building logic in the report layer.
*/

USE [LonzaPlantOpsApp];
GO

CREATE OR ALTER VIEW dbo.vw_bi_stage_catalog AS
SELECT
    stage_order,
    stage_key,
    stage_title,
    sheet_name
FROM (
    VALUES
        (1, N'clarifier', N'Clarifier', N'Data Sheet - Clarifier'),
        (2, N'concentration', N'Concentration', N'Data Sheet - Concentration'),
        (3, N'reconcentration', N'Reconcentration', N'Data Sheet - Reconcentration'),
        (4, N'h2o2_koh_decolorizing', N'H2O2 - KOH Decolorizing', N'Data Sheet - H2O2 - KOH Decolorizing'),
        (5, N'h2o2_calcium_decolorizing', N'H2O2 - Calcium Decolorizing', N'Data Sheet - H2O2 - Calcium Decolorizing'),
        (6, N'centrifuge', N'Centrifuge', N'Data Sheet - Centrifuge'),
        (7, N'anion_exchange', N'Anion Exchange', N'Data Sheet - Anion Exchange'),
        (8, N'resistaid_anion_exchange', N'ResistAid Anion Exchange', N'Data Sheet - ResistAid Anion Exchange'),
        (9, N'carbon_treatment', N'Carbon Treatment', N'Data Sheet - Carbon Treatment')
) AS catalog(stage_order, stage_key, stage_title, sheet_name);
GO

CREATE OR ALTER VIEW dbo.vw_bi_stage_field_catalog AS
SELECT
    stage_key,
    field_order,
    field_key,
    field_label
FROM (
    VALUES
        (N'clarifier', 1, N'entry_date', N'Date'),
        (N'clarifier', 2, N'clarification_sequential_no', N'Clarification Sequential No.'),
        (N'clarifier', 3, N'retentate_flow_set_point', N'Retentate Flow Set Point (gpm)'),
        (N'clarifier', 4, N'zero_refract', N'Zero Refract'),
        (N'clarifier', 5, N'startup_time', N'Start-up Time'),
        (N'clarifier', 6, N'shutdown_time', N'Shut-down Time'),
        (N'clarifier', 7, N'operator_initials', N'Operator Initials'),

        (N'concentration', 1, N'entry_date', N'Date'),
        (N'concentration', 2, N'run_number', N'Run #'),
        (N'concentration', 3, N'product_tank', N'Product Tank'),
        (N'concentration', 4, N'cooler_isolated', N'Cooler Isolated'),
        (N'concentration', 5, N'startup_time', N'Start-up Time'),
        (N'concentration', 6, N'start_saving_product_at', N'Start Saving Product At'),
        (N'concentration', 7, N'shutdown_time', N'Shut Down Time'),
        (N'concentration', 8, N'operator_initials', N'Initials'),

        (N'reconcentration', 1, N'entry_date', N'Date'),
        (N'reconcentration', 2, N'run_number', N'Run No.'),
        (N'reconcentration', 3, N'product_tank', N'Product Tank'),
        (N'reconcentration', 4, N'startup_time', N'Start-up Time'),
        (N'reconcentration', 5, N'start_saving_product_at', N'Start Saving Product At'),
        (N'reconcentration', 6, N'shutdown_time', N'Shut-down Time'),
        (N'reconcentration', 7, N'operator_initials', N'Operator Initials'),

        (N'h2o2_koh_decolorizing', 1, N'entry_date', N'Date'),
        (N'h2o2_koh_decolorizing', 2, N'tank_number', N'Tank #'),
        (N'h2o2_koh_decolorizing', 3, N'production_number', N'Production #'),
        (N'h2o2_koh_decolorizing', 4, N'retain_sample_taken', N'Retain Sample Taken'),
        (N'h2o2_koh_decolorizing', 5, N'retain_sample_logged', N'Retain Sample Logged'),
        (N'h2o2_koh_decolorizing', 6, N'dry_lag_weight', N'Dry LAG Wt (lb)'),
        (N'h2o2_koh_decolorizing', 7, N'h2o2_target_vs_lag_weight', N'Hydrogen Peroxide Target vs LAG Wt (%)'),
        (N'h2o2_koh_decolorizing', 8, N'h2o2_target_total_gallons', N'Hydrogen Peroxide Target Total Addition (gal)'),
        (N'h2o2_koh_decolorizing', 9, N'h2o2_target_total_lbs', N'Hydrogen Peroxide Target Total Addition (lb)'),
        (N'h2o2_koh_decolorizing', 10, N'h2o2_density', N'Hydrogen Peroxide Density'),
        (N'h2o2_koh_decolorizing', 11, N'koh_target_vs_lag_weight', N'Potassium Hydroxide Target vs LAG Wt (%)'),
        (N'h2o2_koh_decolorizing', 12, N'koh_target_total_liquid_lbs', N'Potassium Hydroxide Target Total Addition - Liquid (lb)'),
        (N'h2o2_koh_decolorizing', 13, N'koh_target_total_dry_lbs', N'Potassium Hydroxide Target Total Addition - Dry (lb)'),
        (N'h2o2_koh_decolorizing', 14, N'koh_density', N'Potassium Hydroxide Density'),
        (N'h2o2_koh_decolorizing', 15, N'koh_target_gallons', N'Potassium Hydroxide Target (gal)'),
        (N'h2o2_koh_decolorizing', 16, N'operator_initials', N'Operator Initials'),

        (N'h2o2_calcium_decolorizing', 1, N'entry_date', N'Date'),
        (N'h2o2_calcium_decolorizing', 2, N'tank_number', N'Tank #'),
        (N'h2o2_calcium_decolorizing', 3, N'run_blend_number', N'Run / Blend #'),
        (N'h2o2_calcium_decolorizing', 4, N'retain_sample_taken', N'Retain Sample Taken'),
        (N'h2o2_calcium_decolorizing', 5, N'retain_sample_logged', N'Retain Sample Logged'),
        (N'h2o2_calcium_decolorizing', 6, N'dry_lag_weight', N'Dry LAG Wt (lb)'),
        (N'h2o2_calcium_decolorizing', 7, N'h2o2_target_vs_lag_weight', N'Hydrogen Peroxide Target vs LAG Wt (%)'),
        (N'h2o2_calcium_decolorizing', 8, N'h2o2_target_total_gallons', N'Hydrogen Peroxide Target Total Addition (gal)'),
        (N'h2o2_calcium_decolorizing', 9, N'calcium_target_vs_lag_weight', N'Calcium Hydroxide Target vs LAG Wt (%)'),
        (N'h2o2_calcium_decolorizing', 10, N'calcium_target_total_liquid_lbs', N'Calcium Hydroxide Target Total Addition - Liquid (lb)'),
        (N'h2o2_calcium_decolorizing', 11, N'operator_initials', N'Operator Initials'),

        (N'centrifuge', 1, N'entry_date', N'Date'),
        (N'centrifuge', 2, N'production_number', N'Production Number'),
        (N'centrifuge', 3, N'starting_peroxide_level', N'Starting Peroxide Level (ppm)'),
        (N'centrifuge', 4, N'feed_ri', N'Feed RI (%)'),
        (N'centrifuge', 5, N'turbidity_range', N'Turbidity Range (NTU)'),
        (N'centrifuge', 6, N'shot_setup', N'Shot Set-up'),
        (N'centrifuge', 7, N'operator_initials', N'Operator Initials'),

        (N'anion_exchange', 1, N'entry_date', N'Date'),
        (N'anion_exchange', 2, N'operator_initials', N'Initials'),
        (N'anion_exchange', 3, N'bed', N'Bed'),
        (N'anion_exchange', 4, N'start_color', N'Start Color'),
        (N'anion_exchange', 5, N'run_blend_number', N'Run or Blend #'),
        (N'anion_exchange', 6, N'pass_number', N'Pass #'),
        (N'anion_exchange', 7, N'product_to_tank_start_time', N'Product to Tank Start Time'),
        (N'anion_exchange', 8, N'ri_of_extract_to_be_exchanged', N'RI of Extract to be Exchanged (%)'),
        (N'anion_exchange', 9, N'started_transfer_to_tank', N'Started Transfer to Tank'),
        (N'anion_exchange', 10, N'transfer_to_tank_number', N'Transfer to Tank #'),
        (N'anion_exchange', 11, N'done_in_a_loop', N'Done in A Loop'),
        (N'anion_exchange', 12, N'completion_date', N'Completion Date'),
        (N'anion_exchange', 13, N'completion_time', N'Completion Time'),
        (N'anion_exchange', 14, N'completion_initials', N'Completion Initials'),

        (N'resistaid_anion_exchange', 1, N'run_blend_number', N'Run or Blend #'),
        (N'resistaid_anion_exchange', 2, N'transfer_path', N'Transfer Path'),
        (N'resistaid_anion_exchange', 3, N'entry_date', N'Date'),
        (N'resistaid_anion_exchange', 4, N'operator_initials', N'Operator Initials'),

        (N'carbon_treatment', 1, N'production_number', N'Production #'),
        (N'carbon_treatment', 2, N'startup_date', N'Start Up Date'),
        (N'carbon_treatment', 3, N'startup_time', N'Start Up Time'),
        (N'carbon_treatment', 4, N'operator_initials', N'Initials')
) AS catalog(stage_key, field_order, field_key, field_label);
GO

CREATE OR ALTER VIEW dbo.vw_bi_stage_table_catalog AS
SELECT
    stage_key,
    table_order,
    table_key,
    table_title,
    row_limit
FROM (
    VALUES
        (N'clarifier', 1, N'clarifier_filtration', N'Filtration', 8),
        (N'clarifier', 2, N'clarifier_dia', N'Diafiltration', 6),

        (N'concentration', 1, N'concentration', N'Timed Readings', 8),

        (N'reconcentration', 1, N'reconcentration', N'Timed Readings', 8),

        (N'h2o2_koh_decolorizing', 1, N'koh_h2o2', N'Bulk H2O2 Additions', 10),
        (N'h2o2_koh_decolorizing', 2, N'koh_additions', N'Potassium Hydroxide Additions', 10),

        (N'h2o2_calcium_decolorizing', 1, N'calcium_h2o2', N'Bulk H2O2 Additions', 8),
        (N'h2o2_calcium_decolorizing', 2, N'calcium_additions', N'Calcium Hydroxide Additions', 12),

        (N'centrifuge', 1, N'centrifuge', N'Operating Log', 10),

        (N'anion_exchange', 1, N'anion_exchange', N'Exchange Log', 10),

        (N'resistaid_anion_exchange', 1, N'resistaid', N'Transfer Log', 16),

        (N'carbon_treatment', 1, N'carbon_usage', N'Carbon Usage', 5),
        (N'carbon_treatment', 2, N'carbon_monitoring', N'Vessel Monitoring', 10)
) AS catalog(stage_key, table_order, table_key, table_title, row_limit);
GO

CREATE OR ALTER VIEW dbo.vw_bi_stage_table_column_catalog AS
SELECT
    stage_key,
    table_key,
    column_order,
    column_key,
    column_label
FROM (
    VALUES
        (N'clarifier', N'clarifier_filtration', 1, N'time', N'Time'),
        (N'clarifier', N'clarifier_filtration', 2, N'operator_initials', N'Initials'),
        (N'clarifier', N'clarifier_filtration', 3, N'feed_tank_level', N'Feed Tank Level (%)'),
        (N'clarifier', N'clarifier_filtration', 4, N'feed_pressure', N'Feed Pressure (psi)'),
        (N'clarifier', N'clarifier_filtration', 5, N'permeate_flow_c', N'Perm C (gpm)'),
        (N'clarifier', N'clarifier_filtration', 6, N'permeate_flow_d', N'Perm D (gpm)'),
        (N'clarifier', N'clarifier_filtration', 7, N'feed_ri', N'Feed RI (%)'),
        (N'clarifier', N'clarifier_filtration', 8, N'retentate_ri', N'Retentate RI (%)'),
        (N'clarifier', N'clarifier_filtration', 9, N'permeate_ri', N'Permeate RI (%)'),

        (N'clarifier', N'clarifier_dia', 1, N'time', N'Time'),
        (N'clarifier', N'clarifier_dia', 2, N'operator_initials', N'Initials'),
        (N'clarifier', N'clarifier_dia', 3, N'feed_tank_level', N'Feed Tank Level (%)'),
        (N'clarifier', N'clarifier_dia', 4, N'feed_pressure', N'Feed Pressure (psi)'),
        (N'clarifier', N'clarifier_dia', 5, N'feed_ri', N'Feed RI (%)'),
        (N'clarifier', N'clarifier_dia', 6, N'retentate_ri', N'Retentate RI (%)'),
        (N'clarifier', N'clarifier_dia', 7, N'permeate_ri', N'Permeate RI (%)'),

        (N'concentration', N'concentration', 1, N'time', N'Time'),
        (N'concentration', N'concentration', 2, N'product_ri', N'Product RI (%)'),
        (N'concentration', N'concentration', 3, N'first_effect_temp', N'1st Effect Temp (deg F)'),
        (N'concentration', N'concentration', 4, N'second_effect_temp', N'2nd Effect Temp (deg F)'),
        (N'concentration', N'concentration', 5, N'third_effect_temp', N'3rd Effect Temp (deg F)'),
        (N'concentration', N'concentration', 6, N'condenser_temp', N'Condenser Temp (deg F)'),
        (N'concentration', N'concentration', 7, N'system_pressure', N'System Pressure (in Hg)'),
        (N'concentration', N'concentration', 8, N'gcv', N'GCV'),

        (N'reconcentration', N'reconcentration', 1, N'time', N'Time'),
        (N'reconcentration', N'reconcentration', 2, N'product_ri', N'Product RI (%)'),
        (N'reconcentration', N'reconcentration', 3, N'product_color', N'Product Color'),
        (N'reconcentration', N'reconcentration', 4, N'first_effect_temp', N'1st Effect Temp (deg F)'),
        (N'reconcentration', N'reconcentration', 5, N'second_effect_temp', N'2nd Effect Temp (deg F)'),
        (N'reconcentration', N'reconcentration', 6, N'third_effect_temp', N'3rd Effect Temp (deg F)'),
        (N'reconcentration', N'reconcentration', 7, N'condenser_temp', N'Condenser Temp (deg F)'),
        (N'reconcentration', N'reconcentration', 8, N'system_pressure', N'System Pressure (in Hg)'),
        (N'reconcentration', N'reconcentration', 9, N'h2o2_ppm', N'H2O2 (ppm)'),
        (N'reconcentration', N'reconcentration', 10, N'gcv', N'GCV'),

        (N'h2o2_koh_decolorizing', N'koh_h2o2', 1, N'time', N'Time'),
        (N'h2o2_koh_decolorizing', N'koh_h2o2', 2, N'initials', N'Initials'),
        (N'h2o2_koh_decolorizing', N'koh_h2o2', 3, N'totalizer', N'Totalizer (gal)'),
        (N'h2o2_koh_decolorizing', N'koh_h2o2', 4, N'net_add', N'Net Add (gal)'),
        (N'h2o2_koh_decolorizing', N'koh_h2o2', 5, N'pump_status', N'Pump Status'),

        (N'h2o2_koh_decolorizing', N'koh_additions', 1, N'time', N'Time'),
        (N'h2o2_koh_decolorizing', N'koh_additions', 2, N'initials', N'Initials'),
        (N'h2o2_koh_decolorizing', N'koh_additions', 3, N'pump_status', N'Pump Status'),
        (N'h2o2_koh_decolorizing', N'koh_additions', 4, N'net_add_gallons', N'Net Add (gal)'),
        (N'h2o2_koh_decolorizing', N'koh_additions', 5, N'comments', N'Comments'),

        (N'h2o2_calcium_decolorizing', N'calcium_h2o2', 1, N'time', N'Time'),
        (N'h2o2_calcium_decolorizing', N'calcium_h2o2', 2, N'initials', N'Initials'),
        (N'h2o2_calcium_decolorizing', N'calcium_h2o2', 3, N'totalizer', N'Totalizer (gal)'),
        (N'h2o2_calcium_decolorizing', N'calcium_h2o2', 4, N'net_add', N'Net Add (gal)'),

        (N'h2o2_calcium_decolorizing', N'calcium_additions', 1, N'time', N'Time'),
        (N'h2o2_calcium_decolorizing', N'calcium_additions', 2, N'operator_initials', N'Initials'),
        (N'h2o2_calcium_decolorizing', N'calcium_additions', 3, N'scale_before', N'Scale Before (lb)'),
        (N'h2o2_calcium_decolorizing', N'calcium_additions', 4, N'scale_after', N'Scale After (lb)'),
        (N'h2o2_calcium_decolorizing', N'calcium_additions', 5, N'net_add_liquid_lb', N'Net Add - Liquid (lb)'),
        (N'h2o2_calcium_decolorizing', N'calcium_additions', 6, N'comments', N'Comments'),

        (N'centrifuge', N'centrifuge', 1, N'initials', N'Initials'),
        (N'centrifuge', N'centrifuge', 2, N'time', N'Time'),
        (N'centrifuge', N'centrifuge', 3, N'h2o2_added', N'H2O2 Added (ppm)'),
        (N'centrifuge', N'centrifuge', 4, N'back_pressure', N'Back Pressure (psi)'),
        (N'centrifuge', N'centrifuge', 5, N'saving', N'Saving Y/N'),

        (N'anion_exchange', N'anion_exchange', 1, N'time', N'Time'),
        (N'anion_exchange', N'anion_exchange', 2, N'initials', N'Initials'),
        (N'anion_exchange', N'anion_exchange', 3, N'product_ri', N'Product RI (%)'),
        (N'anion_exchange', N'anion_exchange', 4, N'input_color_400nm', N'Input Color (400 nm)'),
        (N'anion_exchange', N'anion_exchange', 5, N'input_h2o2', N'Input H2O2 (ppm)'),
        (N'anion_exchange', N'anion_exchange', 6, N'output_color_400nm', N'Output Color (400 nm)'),
        (N'anion_exchange', N'anion_exchange', 7, N'output_ri', N'Output RI (%)'),

        (N'resistaid_anion_exchange', N'resistaid', 1, N'date', N'Date'),
        (N'resistaid_anion_exchange', N'resistaid', 2, N'time', N'Time'),
        (N'resistaid_anion_exchange', N'resistaid', 3, N'initials', N'Initials'),
        (N'resistaid_anion_exchange', N'resistaid', 4, N'product_ri', N'Product RI (%)'),
        (N'resistaid_anion_exchange', N'resistaid', 5, N'inches_to_top', N'Inches to Top (in)'),
        (N'resistaid_anion_exchange', N'resistaid', 6, N't561_gallons', N'T-561 Gallons (gal)'),
        (N'resistaid_anion_exchange', N'resistaid', 7, N'lag_lb_transferred', N'LAG Transferred (lb)'),
        (N'resistaid_anion_exchange', N'resistaid', 8, N'current_bed', N'Current Bed'),
        (N'resistaid_anion_exchange', N'resistaid', 9, N'total_lb_transferred', N'Total on Bed (lb)'),

        (N'carbon_treatment', N'carbon_usage', 1, N'vessel', N'Vessel'),
        (N'carbon_treatment', N'carbon_usage', 2, N'date', N'Date'),
        (N'carbon_treatment', N'carbon_usage', 3, N'time', N'Time'),
        (N'carbon_treatment', N'carbon_usage', 4, N'weight', N'WT (lb)'),
        (N'carbon_treatment', N'carbon_usage', 5, N'name', N'Name'),
        (N'carbon_treatment', N'carbon_usage', 6, N'lot_number', N'Lot Number'),
        (N'carbon_treatment', N'carbon_usage', 7, N'flushed', N'Flushed?'),

        (N'carbon_treatment', N'carbon_monitoring', 1, N'date', N'Date'),
        (N'carbon_treatment', N'carbon_monitoring', 2, N'time', N'Time'),
        (N'carbon_treatment', N'carbon_monitoring', 3, N'initials', N'Initials'),
        (N'carbon_treatment', N'carbon_monitoring', 4, N'order', N'Order'),
        (N'carbon_treatment', N'carbon_monitoring', 5, N'vessel_a_flavor', N'Vessel A Flavor'),
        (N'carbon_treatment', N'carbon_monitoring', 6, N'vessel_a_odor', N'Vessel A Odor'),
        (N'carbon_treatment', N'carbon_monitoring', 7, N'vessel_a_ri', N'Vessel A RI (%)'),
        (N'carbon_treatment', N'carbon_monitoring', 8, N'vessel_b_flavor', N'Vessel B Flavor'),
        (N'carbon_treatment', N'carbon_monitoring', 9, N'vessel_b_odor', N'Vessel B Odor'),
        (N'carbon_treatment', N'carbon_monitoring', 10, N'vessel_b_ri', N'Vessel B RI (%)'),
        (N'carbon_treatment', N'carbon_monitoring', 11, N'vessel_c_flavor', N'Vessel C Flavor'),
        (N'carbon_treatment', N'carbon_monitoring', 12, N'vessel_c_odor', N'Vessel C Odor'),
        (N'carbon_treatment', N'carbon_monitoring', 13, N'vessel_c_ri', N'Vessel C RI (%)')
) AS catalog(stage_key, table_key, column_order, column_key, column_label);
GO

CREATE OR ALTER VIEW dbo.vw_bi_run_packet_header AS
SELECT
    r.id AS run_id,
    COALESCE(
        NULLIF(LTRIM(RTRIM(r.run_number)), N''),
        NULLIF(LTRIM(RTRIM(r.batch_number)), N''),
        CONVERT(NVARCHAR(50), r.id)
    ) AS run_label,
    r.batch_number,
    r.split_batch_number,
    r.blend_number,
    r.run_number,
    r.batch_type,
    r.reused_batch,
    r.product_name,
    r.shift_name,
    r.operator_id,
    r.notes AS run_notes,
    r.status AS run_status,
    r.final_edit_initials,
    r.final_edit_notes,
    r.created_at,
    TRY_CONVERT(datetime2(0), NULLIF(r.created_at, N''), 126) AS created_at_ts,
    r.updated_at,
    TRY_CONVERT(datetime2(0), NULLIF(r.updated_at, N''), 126) AS updated_at_ts,
    r.finalized_at,
    TRY_CONVERT(datetime2(0), NULLIF(r.finalized_at, N''), 126) AS finalized_at_ts,
    r.finalized_by
FROM dbo.production_runs r;
GO

CREATE OR ALTER VIEW dbo.vw_bi_latest_evaporation AS
WITH ranked AS (
    SELECT
        e.*,
        ROW_NUMBER() OVER (
            PARTITION BY e.run_id
            ORDER BY e.id DESC
        ) AS rn
    FROM dbo.evaporation_entries e
    WHERE e.run_id IS NOT NULL
)
SELECT
    h.run_id,
    h.run_label,
    h.run_status,
    ranked.id AS evaporation_entry_id,
    ranked.employee,
    ranked.operator_initials,
    ranked.entry_date,
    ranked.evaporator_no,
    ranked.startup_time,
    ranked.shutdown_time,
    ranked.feed_ri,
    ranked.concentrate_ri,
    ranked.steam_pressure,
    ranked.vacuum,
    ranked.sump_level,
    ranked.product_temp,
    ranked.comments AS stage_notes,
    ranked.photo_path,
    ranked.version_no,
    ranked.previous_entry_id,
    ranked.created_at,
    TRY_CONVERT(datetime2(0), NULLIF(ranked.created_at, N''), 126) AS created_at_ts
FROM ranked
INNER JOIN dbo.vw_bi_run_packet_header h
    ON h.run_id = ranked.run_id
WHERE ranked.rn = 1;
GO

CREATE OR ALTER VIEW dbo.vw_bi_latest_evaporation_rows AS
SELECT
    e.run_id,
    e.run_label,
    e.run_status,
    CAST(0 AS INT) AS section_order,
    N'evaporation' AS section_key,
    N'Evaporation' AS section_title,
    e.evaporation_entry_id,
    N'Hourly Readings' AS table_title,
    rows.row_no,
    rows.row_time,
    rows.feed_rate,
    rows.evap_temp,
    rows.row_vacuum,
    rows.row_concentrate_ri,
    e.created_at,
    e.created_at_ts
FROM dbo.vw_bi_latest_evaporation e
INNER JOIN dbo.evaporation_rows rows
    ON rows.evaporation_entry_id = e.evaporation_entry_id;
GO

CREATE OR ALTER VIEW dbo.vw_bi_latest_stage_entries AS
WITH ranked AS (
    SELECT
        s.*,
        ROW_NUMBER() OVER (
            PARTITION BY s.run_id, s.stage_key
            ORDER BY s.id DESC
        ) AS rn
    FROM dbo.sheet_entries s
    WHERE s.run_id IS NOT NULL
)
SELECT
    h.run_id,
    h.run_label,
    h.run_status,
    stage.stage_order,
    ranked.stage_key,
    COALESCE(NULLIF(LTRIM(RTRIM(ranked.stage_title)), N''), stage.stage_title) AS stage_title,
    stage.sheet_name,
    ranked.id AS sheet_entry_id,
    ranked.employee,
    ranked.operator_initials,
    ranked.entry_date,
    ranked.comments AS stage_notes,
    ranked.payload_json,
    ranked.version_no,
    ranked.previous_entry_id,
    ranked.created_at,
    TRY_CONVERT(datetime2(0), NULLIF(ranked.created_at, N''), 126) AS created_at_ts
FROM ranked
INNER JOIN dbo.vw_bi_run_packet_header h
    ON h.run_id = ranked.run_id
INNER JOIN dbo.vw_bi_stage_catalog stage
    ON stage.stage_key = ranked.stage_key
WHERE ranked.rn = 1;
GO

CREATE OR ALTER VIEW dbo.vw_bi_run_packet_sections AS
SELECT
    e.run_id,
    e.run_label,
    e.run_status,
    CAST(0 AS INT) AS section_order,
    N'evaporation' AS section_key,
    N'Evaporation' AS section_title,
    e.evaporation_entry_id AS source_entry_id,
    e.entry_date,
    e.operator_initials,
    e.employee,
    e.stage_notes,
    e.created_at,
    e.created_at_ts
FROM dbo.vw_bi_latest_evaporation e

UNION ALL

SELECT
    s.run_id,
    s.run_label,
    s.run_status,
    s.stage_order,
    s.stage_key AS section_key,
    s.stage_title AS section_title,
    s.sheet_entry_id AS source_entry_id,
    s.entry_date,
    s.operator_initials,
    s.employee,
    s.stage_notes,
    s.created_at,
    s.created_at_ts
FROM dbo.vw_bi_latest_stage_entries s;
GO

CREATE OR ALTER VIEW dbo.vw_bi_stage_fields AS
SELECT
    s.run_id,
    s.run_label,
    s.run_status,
    s.stage_order,
    s.stage_key,
    s.stage_title,
    s.sheet_name,
    s.sheet_entry_id,
    fields.field_order,
    fields.field_key,
    fields.field_label,
    CASE
        WHEN fields.field_key = N'entry_date'
            THEN COALESCE(NULLIF(LTRIM(RTRIM(s.entry_date)), N''), payload.json_value)
        WHEN fields.field_key = N'operator_initials'
            THEN COALESCE(NULLIF(LTRIM(RTRIM(s.operator_initials)), N''), payload.json_value)
        ELSE payload.json_value
    END AS field_value,
    s.entry_date,
    s.operator_initials,
    s.employee,
    s.stage_notes,
    s.created_at,
    s.created_at_ts
FROM dbo.vw_bi_latest_stage_entries s
INNER JOIN dbo.vw_bi_stage_field_catalog fields
    ON fields.stage_key = s.stage_key
OUTER APPLY (
    SELECT TOP (1)
        NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(MAX), j.[value]))), N'') AS json_value
    FROM OPENJSON(COALESCE(s.payload_json, N'{}')) j
    WHERE j.[key] COLLATE DATABASE_DEFAULT = fields.field_key
) AS payload;
GO

CREATE OR ALTER VIEW dbo.vw_bi_stage_table_cells AS
WITH row_numbers AS (
    SELECT row_no
    FROM (
        VALUES
            (1), (2), (3), (4), (5), (6), (7), (8),
            (9), (10), (11), (12), (13), (14), (15), (16)
    ) AS rows(row_no)
)
SELECT
    s.run_id,
    s.run_label,
    s.run_status,
    s.stage_order,
    s.stage_key,
    s.stage_title,
    s.sheet_name,
    s.sheet_entry_id,
    tables.table_order,
    tables.table_key,
    tables.table_title,
    row_numbers.row_no,
    CONCAT(tables.table_key, N'_', CONVERT(NVARCHAR(10), row_numbers.row_no)) AS row_key,
    columns.column_order,
    columns.column_key,
    columns.column_label,
    payload.cell_value,
    s.entry_date,
    s.operator_initials,
    s.employee,
    s.stage_notes,
    s.created_at,
    s.created_at_ts
FROM dbo.vw_bi_latest_stage_entries s
INNER JOIN dbo.vw_bi_stage_table_catalog tables
    ON tables.stage_key = s.stage_key
INNER JOIN row_numbers
    ON row_numbers.row_no <= tables.row_limit
INNER JOIN dbo.vw_bi_stage_table_column_catalog columns
    ON columns.stage_key = tables.stage_key
   AND columns.table_key = tables.table_key
OUTER APPLY (
    SELECT TOP (1)
        NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(MAX), j.[value]))), N'') AS cell_value
    FROM OPENJSON(COALESCE(s.payload_json, N'{}')) j
    WHERE j.[key] COLLATE DATABASE_DEFAULT = CONCAT(
        tables.table_key,
        N'_',
        CONVERT(NVARCHAR(10), row_numbers.row_no),
        N'_',
        columns.column_key
    )
) AS payload
WHERE payload.cell_value IS NOT NULL;
GO

CREATE OR ALTER VIEW dbo.vw_bi_stage_table_rows AS
SELECT
    cells.run_id,
    cells.run_label,
    cells.run_status,
    cells.stage_order,
    cells.stage_key,
    cells.stage_title,
    cells.sheet_name,
    cells.sheet_entry_id,
    cells.table_order,
    cells.table_key,
    cells.table_title,
    cells.row_no,
    cells.row_key,
    COUNT(*) AS populated_cell_count,
    cells.entry_date,
    cells.operator_initials,
    cells.employee,
    cells.stage_notes,
    cells.created_at,
    cells.created_at_ts
FROM dbo.vw_bi_stage_table_cells cells
GROUP BY
    cells.run_id,
    cells.run_label,
    cells.run_status,
    cells.stage_order,
    cells.stage_key,
    cells.stage_title,
    cells.sheet_name,
    cells.sheet_entry_id,
    cells.table_order,
    cells.table_key,
    cells.table_title,
    cells.row_no,
    cells.row_key,
    cells.entry_date,
    cells.operator_initials,
    cells.employee,
    cells.stage_notes,
    cells.created_at,
    cells.created_at_ts;
GO
