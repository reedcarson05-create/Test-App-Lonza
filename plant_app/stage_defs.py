"""Central stage metadata used to build the batch-pack navigation and generic sheets."""

# Shared temperature label reused across multiple stage tables.
DEG_F = "\u00B0F"

def header(field_name: str, label: str, field_type: str):
    """Build a header tuple for a top-of-form field in a generic stage sheet."""
    return (field_name, label, field_type)


def column(field_name: str, label: str):
    """Build a table column tuple for a repeating row in a generic stage sheet."""
    return (field_name, label)


def table(title: str, prefix: str, rows: int, columns: list[tuple[str, str]]):
    """Build a table definition consumed by the generic stage template."""
    return {"title": title, "prefix": prefix, "rows": rows, "columns": columns}


# Full configuration for every batch-pack stage rendered through `generic_sheet.html`.
GENERIC_STAGE_DEFS = {
    # Three repeated filtration cycle tables captured as a generic batch-pack sheet.
    "filtration_cycles": {
        "title": "Filtration Cycles",
        "sheet_name": "Filtration",
        "headers": [
            header("entry_date", "Date", "date"),
            header("cycle_volume_set_point", "Cycle Volume Set Point (gal)", "text"),
            header("zero_refract", "Zero Refract", "select"),
            header("operator_initials", "Operator Initials", "text"),
        ],
        "tables": [
            table("Cycle 1", "cycle1", 4, [
                column("time", "Time"),
                column("operator_initials", "Initials"),
                column("fic1_gpm", "FIC1 (gpm)"),
                column("tit1", f"TIT1 ({DEG_F})"),
                column("tit2", f"TIT2 ({DEG_F})"),
                column("dpt", "DPT (psi)"),
                column("dpm", "DPM (psi)"),
                column("perm_total", "Perm Total (gal)"),
                column("f12_gpm", "F12 (gpm)"),
                column("permeate_ri", "Perm RI (%)"),
                column("retentate_ri", "Retentate RI (%)"),
            ]),
            table("Cycle 2", "cycle2", 4, [
                column("time", "Time"),
                column("operator_initials", "Initials"),
                column("fic1_gpm", "FIC1 (gpm)"),
                column("tit1", f"TIT1 ({DEG_F})"),
                column("tit2", f"TIT2 ({DEG_F})"),
                column("dpt", "DPT (psi)"),
                column("dpm", "DPM (psi)"),
                column("perm_total", "Perm Total (gal)"),
                column("f12_gpm", "F12 (gpm)"),
                column("permeate_ri", "Perm RI (%)"),
                column("retentate_ri", "Retentate RI (%)"),
            ]),
            table("Cycle 3", "cycle3", 4, [
                column("time", "Time"),
                column("operator_initials", "Initials"),
                column("fic1_gpm", "FIC1 (gpm)"),
                column("tit1", f"TIT1 ({DEG_F})"),
                column("tit2", f"TIT2 ({DEG_F})"),
                column("dpt", "DPT (psi)"),
                column("dpm", "DPM (psi)"),
                column("perm_total", "Perm Total (gal)"),
                column("f12_gpm", "F12 (gpm)"),
                column("permeate_ri", "Perm RI (%)"),
                column("retentate_ri", "Retentate RI (%)"),
            ]),
        ],
    },
    # Clarifier combines a filtration section and a diafiltration section in one stage.
    "clarifier": {
        "title": "Clarifier",
        "sheet_name": "Data Sheet - Clarifier",
        "headers": [
            header("entry_date", "Date", "date"),
            header("clarification_sequential_no", "Clarification Sequential No.", "text"),
            header("retentate_flow_set_point", "Retentate Flow Set Point (gpm)", "text"),
            header("zero_refract", "Zero Refract", "select"),
            header("startup_time", "Start-up Time", "time"),
            header("shutdown_time", "Shut-down Time", "time"),
            header("operator_initials", "Operator Initials", "text"),
        ],
        "tables": [
            table("Filtration", "clarifier_filtration", 8, [
                column("time", "Time"),
                column("operator_initials", "Initials"),
                column("feed_tank_level", "Feed Tank Level (%)"),
                column("feed_pressure", "Feed Pressure (psi)"),
                column("permeate_flow_c", "Perm C (gpm)"),
                column("permeate_flow_d", "Perm D (gpm)"),
                column("feed_ri", "Feed RI (%)"),
                column("retentate_ri", "Retentate RI (%)"),
                column("permeate_ri", "Permeate RI (%)"),
            ]),
            table("Diafiltration", "clarifier_dia", 6, [
                column("time", "Time"),
                column("operator_initials", "Initials"),
                column("feed_tank_level", "Feed Tank Level (%)"),
                column("feed_pressure", "Feed Pressure (psi)"),
                column("feed_ri", "Feed RI (%)"),
                column("retentate_ri", "Retentate RI (%)"),
                column("permeate_ri", "Permeate RI (%)"),
            ]),
        ],
    },
    # Concentration tracks one operating run with timed readings from a multistage evaporator.
    "concentration": {
        "title": "Concentration",
        "sheet_name": "Data Sheet - Concentration",
        "headers": [
            header("entry_date", "Date", "date"),
            header("run_number", "Run #", "text"),
            header("product_tank", "Product Tank", "text"),
            header("cooler_isolated", "Cooler Isolated", "select"),
            header("startup_time", "Start-up Time", "time"),
            header("start_saving_product_at", "Start Saving Product At", "time"),
            header("shutdown_time", "Shut Down Time", "time"),
            header("operator_initials", "Initials", "text"),
        ],
        "tables": [
            table("Timed Readings", "concentration", 8, [
                column("time", "Time"),
                column("product_ri", "Product RI (%)"),
                column("first_effect_temp", f"1st Effect Temp ({DEG_F})"),
                column("second_effect_temp", f"2nd Effect Temp ({DEG_F})"),
                column("third_effect_temp", f"3rd Effect Temp ({DEG_F})"),
                column("condenser_temp", f"Condenser Temp ({DEG_F})"),
                column("system_pressure", "System Pressure (in Hg)"),
                column("gcv", "GCV"),
            ]),
        ],
    },
    # Reconcentration mirrors concentration with a slightly different chemistry-focused column set.
    "reconcentration": {
        "title": "Reconcentration",
        "sheet_name": "Data Sheet - Reconcentration",
        "headers": [
            header("entry_date", "Date", "date"),
            header("run_number", "Run No.", "text"),
            header("product_tank", "Product Tank", "text"),
            header("startup_time", "Start-up Time", "time"),
            header("start_saving_product_at", "Start Saving Product At", "time"),
            header("shutdown_time", "Shut-down Time", "time"),
            header("operator_initials", "Operator Initials", "text"),
        ],
        "tables": [
            table("Timed Readings", "reconcentration", 8, [
                column("time", "Time"),
                column("product_ri", "Product RI (%)"),
                column("product_color", "Product Color"),
                column("first_effect_temp", f"1st Effect Temp ({DEG_F})"),
                column("second_effect_temp", f"2nd Effect Temp ({DEG_F})"),
                column("third_effect_temp", f"3rd Effect Temp ({DEG_F})"),
                column("system_pressure", "System Pressure (in Hg)"),
                column("h2o2_ppm", "H2O2 (ppm)"),
                column("gcv", "GCV"),
            ]),
        ],
    },
    # KOH decolorizing captures peroxide and caustic additions with operator checks.
    "h2o2_koh_decolorizing": {
        "title": "H2O2 - KOH Decolorizing",
        "sheet_name": "Data Sheet - H2O2 - KOH Decolorizing",
        "headers": [
            header("entry_date", "Date", "date"),
            header("tank_number", "Tank #", "text"),
            header("production_number", "Production #", "text"),
            header("retain_sample_taken", "Retain Sample Taken", "select"),
            header("retain_sample_logged", "Retain Sample Logged", "select"),
            header("dry_lag_weight", "Dry LAG Wt (lb)", "text"),
            header("operator_initials", "Operator Initials", "text"),
        ],
        "tables": [
            table("Bulk H2O2 Additions", "koh_h2o2", 10, [
                column("time", "Time"),
                column("initials", "Initials"),
                column("totalizer", "Totalizer (gal)"),
                column("net_add", "Net Add (gal)"),
                column("pump_status", "Pump Status"),
                column("temp", f"Temp ({DEG_F})"),
                column("tank_level", "Tank Level (%)"),
            ]),
            table("Potassium Hydroxide Additions", "koh_additions", 10, [
                column("time", "Time"),
                column("initials", "Initials"),
                column("pump_status", "Pump Status"),
                column("flow", "Flow (gpm)"),
                column("net_add_gallons", "Net Add (gal)"),
                column("tank_temp", f"Tank Temp ({DEG_F})"),
                column("tank_level", "Tank Level (%)"),
                column("ph_before", "pH Before"),
                column("comments", "Comments"),
            ]),
        ],
    },
    # Calcium decolorizing is similar to KOH but uses different additive tables and labels.
    "h2o2_calcium_decolorizing": {
        "title": "H2O2 - Calcium Decolorizing",
        "sheet_name": "Data Sheet - H2O2 - Calcium Decolorizing",
        "headers": [
            header("entry_date", "Date", "date"),
            header("tank_number", "Tank #", "text"),
            header("run_blend_number", "Run / Blend #", "text"),
            header("retain_sample_taken", "Retain Sample Taken", "select"),
            header("retain_sample_logged", "Retain Sample Logged", "select"),
            header("dry_lag_weight", "Dry LAG Wt (lb)", "text"),
            header("operator_initials", "Operator Initials", "text"),
        ],
        "tables": [
            table("Bulk H2O2 Additions", "calcium_h2o2", 8, [
                column("time", "Time"),
                column("initials", "Initials"),
                column("totalizer", "Totalizer (gal)"),
                column("net_add", "Net Add (gal)"),
            ]),
            table("Calcium Hydroxide Additions", "calcium_additions", 12, [
                column("time", "Time"),
                column("operator_initials", "Initials"),
                column("scale_before", "Scale Before (lb)"),
                column("scale_after", "Scale After (lb)"),
                column("net_add_liquid_lb", "Net Add (lb)"),
                column("tank_temp", f"Tank Temp ({DEG_F})"),
                column("tank_level", "Tank Level (%)"),
                column("ph_before", "pH Before"),
                column("comments", "Comments"),
            ]),
        ],
    },
    # Centrifuge is a smaller log-oriented stage with one repeated operating table.
    "centrifuge": {
        "title": "Centrifuge",
        "sheet_name": "Data Sheet - Centrifuge",
        "headers": [
            header("entry_date", "Date", "date"),
            header("production_number", "Production Number", "text"),
            header("starting_peroxide_level", "Starting Peroxide Level (ppm)", "text"),
            header("feed_ri", "Feed RI (%)", "text"),
            header("turbidity_range", "Turbidity Range (NTU)", "text"),
            header("shot_setup", "Shot Set-up", "text"),
            header("operator_initials", "Operator Initials", "text"),
        ],
        "tables": [
            table("Operating Log", "centrifuge", 10, [
                column("initials", "Initials"),
                column("time", "Time"),
                column("h2o2_added", "H2O2 Added (ppm)"),
                column("back_pressure", "Back Pressure (psi)"),
                column("saving", "Saving Y/N"),
            ]),
        ],
    },
    # Anion exchange tracks product transfer through a selected resin bed.
    "anion_exchange": {
        "title": "Anion Exchange",
        "sheet_name": "Data Sheet - Anion Exchange",
        "headers": [
            header("entry_date", "Date", "date"),
            header("operator_initials", "Initials", "text"),
            header("bed", "Bed", "select"),
            header("start_color", "Start Color", "text"),
            header("run_blend_number", "Run or Blend #", "text"),
            header("pass_number", "Pass #", "text"),
            header("product_to_tank_start_time", "Product to Tank Start Time", "time"),
            header("ri_of_extract_to_be_exchanged", "RI of Extract to be Exchanged (%)", "text"),
        ],
        "tables": [
            table("Exchange Log", "anion_exchange", 10, [
                column("time", "Time"),
                column("initials", "Initials"),
                column("product_ri", "Product RI (%)"),
                column("input_color_400nm", "Input Color (400 nm)"),
                column("input_h2o2", "Input H2O2 (ppm)"),
                column("output_color_400nm", "Output Color (400 nm)"),
                column("output_ri", "Output RI (%)"),
            ]),
        ],
    },
    # ResistAid exchange uses a dedicated transfer log with bed-loading totals.
    "resistaid_anion_exchange": {
        "title": "ResistAid Anion Exchange",
        "sheet_name": "Data Sheet - ResistAid Anion Exchange",
        "headers": [
            header("run_blend_number", "Run or Blend #", "text"),
            header("transfer_path", "Transfer Path", "text"),
            header("entry_date", "Date", "date"),
            header("operator_initials", "Operator Initials", "text"),
        ],
        "tables": [
            table("Transfer Log", "resistaid", 16, [
                column("date", "Date"),
                column("time", "Time"),
                column("initials", "Initials"),
                column("product_ri", "Product RI (%)"),
                column("inches_to_top", "Inches to Top (in)"),
                column("t561_gallons", "T-561 Gallons (gal)"),
                column("lag_lb_transferred", "LAG Transferred (lb)"),
                column("current_bed", "Current Bed"),
                column("total_lb_transferred", "Total on Bed (lb)"),
            ]),
        ],
    },
    # Carbon treatment combines usage records and ongoing vessel monitoring.
    "carbon_treatment": {
        "title": "Carbon Treatment",
        "sheet_name": "Data Sheet - Carbon Treatment",
        "headers": [
            header("production_number", "Production #", "text"),
            header("startup_date", "Start Up Date", "date"),
            header("startup_time", "Start Up Time", "time"),
            header("operator_initials", "Initials", "text"),
        ],
        "tables": [
            table("Carbon Usage", "carbon_usage", 5, [
                column("vessel", "Vessel"),
                column("date", "Date"),
                column("time", "Time"),
                column("weight", "WT (lb)"),
                column("name", "Name"),
                column("lot_number", "Lot Number"),
                column("flushed", "Flushed?"),
            ]),
            table("Vessel Monitoring", "carbon_monitoring", 10, [
                column("date", "Date"),
                column("time", "Time"),
                column("initials", "Initials"),
                column("order", "Order"),
                column("vessel_a_flavor", "Vessel A Flavor"),
                column("vessel_a_odor", "Vessel A Odor"),
                column("vessel_a_ri", "Vessel A RI (%)"),
                column("vessel_b_flavor", "Vessel B Flavor"),
                column("vessel_b_odor", "Vessel B Odor"),
                column("vessel_b_ri", "Vessel B RI (%)"),
                column("vessel_c_flavor", "Vessel C Flavor"),
                column("vessel_c_odor", "Vessel C Odor"),
                column("vessel_c_ri", "Vessel C RI (%)"),
                column("temperature", f"Temp ({DEG_F})"),
            ]),
        ],
    },
}

# Navigation used on the batch stage selection screen.
STAGE_LINKS = [
    # Evaporation uses its own dedicated template instead of the generic sheet renderer.
    {"title": "Evaporation", "href": "/stage/evaporation"},
    {"title": "Filtration Cycles", "href": "/stage/generic/filtration_cycles"},
    {"title": "Clarifier", "href": "/stage/generic/clarifier"},
    {"title": "Concentration", "href": "/stage/generic/concentration"},
    {"title": "Reconcentration", "href": "/stage/generic/reconcentration"},
    {"title": "H2O2 - KOH Decolorizing", "href": "/stage/generic/h2o2_koh_decolorizing"},
    {"title": "H2O2 - Calcium Decolorizing", "href": "/stage/generic/h2o2_calcium_decolorizing"},
    {"title": "Centrifuge", "href": "/stage/generic/centrifuge"},
    {"title": "Anion Exchange", "href": "/stage/generic/anion_exchange"},
    {"title": "ResistAid Anion Exchange", "href": "/stage/generic/resistaid_anion_exchange"},
    {"title": "Carbon Treatment", "href": "/stage/generic/carbon_treatment"},
]

# Navigation used on the standalone process dashboard.
PROCESS_STAGE_LINKS = [
    # Extraction and filtration are the only standalone process sheets in the current UI.
    {"title": "Extraction", "href": "/stage/extraction"},
    {"title": "Filtration", "href": "/stage/filtration"},
]
