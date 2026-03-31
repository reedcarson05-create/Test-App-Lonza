# Plant App Codebase Guide

This guide explains what each active file does, what to change when requirements move, and which file owns each part of the app.

## Core Python Files

### `app.py`
- Purpose: FastAPI entry point. Owns routes, session checks, form-to-payload mapping, dashboard shaping, and correction-flow validation.
- Change this file when:
- You need a new page or route.
- You need to change how form fields are mapped before saving.
- You need to adjust login, session, redirect, or correction rules.
- Main sections:
- Imports and app setup: change middleware, startup behavior, static/template paths here.
- Helper functions: change shared logic like date formatting, active-run lookup, correction validation, or dashboard shaping here.
- Route handlers: change page behavior, save behavior, validation messages, or redirects here.
- Safe edit notes:
- If you add a new template, wire it here with a route and `render_page(...)`.
- If you add new form fields, update the matching payload builder and the edit-flow `old_values` dictionary.
- If you add a new saved sheet type, also update dashboard builders and change-history display labels.

### `db.py`
- Purpose: SQLite schema creation, migrations, CRUD helpers, audit logging, and dashboard queries.
- Change this file when:
- You add or rename columns.
- You add a new table or child-row table.
- You need different query results for dashboards or review screens.
- Main sections:
- `init_db()`: schema creation and lightweight migration logic.
- Insert/update helpers: one helper per saved entry type.
- Read helpers: fetch single entries, latest run-linked entries, and dashboard history.
- Safe edit notes:
- Add new columns in table creation SQL and with `ensure_column(...)` for existing databases.
- Keep insert and update helpers aligned with the payloads built in `app.py`.
- If a table has repeating rows, update both the parent-table helper and the child-row helper/query.
- Avoid hand-editing `plant.db`; let schema changes happen through `init_db()`.

### `stage_defs.py`
- Purpose: Configuration for all generic batch-pack sheets and their navigation links.
- Change this file when:
- You want to add a new generic stage.
- You want to change labels, field types, table shapes, or navigation text.
- Main sections:
- `GENERIC_STAGE_DEFS`: full stage metadata.
- `STAGE_LINKS`: links shown on the batch stage picker.
- `PROCESS_STAGE_LINKS`: links shown on the standalone process dashboard.
- Safe edit notes:
- Add a stage by creating a new dictionary entry with `title`, `sheet_name`, `headers`, and `tables`.
- Header field types must match what `generic_sheet.html` expects: `text`, `date`, `time`, or `select`.
- If you want a stage to appear in the UI, also add it to the correct link list.

## Static Files

### `static/style.css`
- Purpose: Shared styling for every HTML template.
- Change this file when:
- You want to change colors, spacing, table styling, buttons, or layout behavior.
- Safe edit notes:
- Start with the `:root` variables when changing the overall look.
- Reuse existing utility classes before creating new one-off selectors.
- Test both data-entry pages and dashboards after layout changes because they share classes heavily.

### `static/form_corrections.js`
- Purpose: Adds inline correction helpers on edit pages, including initials boxes and original-value fields.
- Change this file when:
- You want a different correction UX.
- You add fields that should be skipped or handled specially during corrections.
- Safe edit notes:
- The script runs on edit pages only.
- Hidden inputs and internal `__change__...` fields are intentionally skipped; preserve that pattern.

### `static/logo.png`
- Purpose: Brand image shown in the navbar/header area.
- Change this file when:
- Branding changes.
- Safe edit notes:
- Keep a similar size/aspect ratio unless you also adjust `.logo` in `style.css`.

## Templates

### `templates/login.html`
- Purpose: Operator sign-in page.
- Change this file when:
- You need different login wording, fields, or branding.

### `templates/home.html`
- Purpose: Main landing page after login.
- Change this file when:
- You want to change the available next actions or home-page messaging.

### `templates/run_select.html`
- Purpose: Create a new batch/run or reopen a recent one.
- Change this file when:
- Batch header requirements change.
- Safe edit notes:
- If you add or rename a field here, update the matching `run_select(...)` route in `app.py` and the run queries in `db.py`.

### `templates/batch_edit.html`
- Purpose: Edit the current run header details.
- Change this file when:
- Final review initials/notes or batch metadata fields change.
- Safe edit notes:
- Keep field names aligned with `batch_edit_submit(...)` in `app.py`.

### `templates/process_dashboard.html`
- Purpose: Dashboard for extraction and filtration work plus edit links.
- Change this file when:
- You want different dashboard columns, labels, or quick links.

### `templates/stages.html`
- Purpose: Batch stage selection page for run-linked sheets.
- Change this file when:
- You want different wording or presentation of the stage navigation.
- Safe edit notes:
- The actual link list comes from `STAGE_LINKS` in `stage_defs.py`.

### `templates/batch_review.html`
- Purpose: Final batch-pack review page before completion.
- Change this file when:
- Review requirements or sign-off messaging change.
- Safe edit notes:
- The data shape comes from `build_batch_review(...)` in `app.py`.

### `templates/extraction.html`
- Purpose: Extraction create/edit form.
- Change this file when:
- Extraction fields or instructions change.
- Safe edit notes:
- Field names must stay aligned with `build_extraction_payload(...)` and extraction correction logic in `app.py`.

### `templates/filtration.html`
- Purpose: Filtration create/edit form.
- Change this file when:
- Filtration header fields or timed row fields change.
- Safe edit notes:
- Keep row naming consistent with `build_filtration_rows(...)`.

### `templates/evaporation.html`
- Purpose: Evaporation create/view/edit form for run-linked work.
- Change this file when:
- Evaporation fields, timed row layout, or read-only behavior change.
- Safe edit notes:
- Keep row names aligned with `build_evaporation_rows(...)`.

### `templates/generic_sheet.html`
- Purpose: Shared template for every stage defined in `stage_defs.py`.
- Change this file when:
- You want to change how generic stage headers, tables, comments, or correction behavior render.
- Safe edit notes:
- Most content changes belong in `stage_defs.py`; only change this template when the rendering logic itself needs to change.

### `templates/dashboard.html`
- Purpose: Batch-pack dashboard grouped by batch number.
- Change this file when:
- You want different group summaries, columns, or correction links.
- Safe edit notes:
- The grouped data comes from `dashboard_batch_packs()` in `app.py`.

### `templates/change_history.html`
- Purpose: Full correction history page.
- Change this file when:
- You need more audit/correction detail visible to operators or supervisors.
- Safe edit notes:
- The data comes from `get_field_change_history(...)` and `display_sheet_name(...)`.

## Data and Dependency Files

### `plant.db`
- Purpose: Local SQLite database file used by the app.
- Change this file when:
- Normally, do not edit it directly.
- Safe edit notes:
- Make schema changes in `db.py`, then let `init_db()` apply them.
- If you need to reset sample data, back up the file first.

### `requirements.txt`
- Purpose: Python dependencies required by the app.
- Change this file when:
- You add or remove a library.
- Safe edit notes:
- If a dependency is only needed for development, note that separately rather than mixing it into runtime requirements by accident.

## Fastest Way To Make Common Changes

### Add a new generic stage
- Update `GENERIC_STAGE_DEFS` in `stage_defs.py`.
- Add the new stage to `STAGE_LINKS` if operators should see it.
- No new template is needed unless the shared generic layout no longer fits.

### Add a new field to extraction, filtration, or evaporation
- Add the input to the matching template.
- Add the field to the matching payload builder in `app.py`.
- Add the column and persistence logic in `db.py`.
- Add the field to the correction `old_values` map in the matching edit route so change logging still works.

### Change dashboard content
- Adjust the query in `db.py` if the raw data shape needs to change.
- Adjust the shaping helper in `app.py` if display-only grouping or links need to change.
- Adjust the matching template to render the new fields.

### Change correction rules
- Update `collect_field_changes(...)` in `app.py` for shared validation behavior.
- Update `static/form_corrections.js` if the edit-page UI also needs to change.
