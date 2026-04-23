# Power BI Packet Layout

This is a starter layout for making the BI report feel like the app's print packet in [run_print.html](/c:/Users/reedc/OneDrive/Test%20App%20Lonza/plant_app/templates/run_print.html).

A starter report file is available at [bi/RunPacketPaginatedReport.rdl](/c:/Users/reedc/OneDrive/Test%20App%20Lonza/plant_app/bi/RunPacketPaginatedReport.rdl).

## Best Fit

If the goal is "looks like the printed data sheet," use Power BI Report Builder / paginated reports.

If the goal is "interactive but still familiar," use standard Power BI Desktop with a single run-detail page and one drill-through page.

## Recommended Paginated Report Build

### 1. Data Source

- SQL Server: `DESKTOP-8NEGE16`
- Database: `LonzaPlantOpsApp`
- Use [BI_REPORT_DATASET_QUERIES.sql](/c:/Users/reedc/OneDrive/Test%20App%20Lonza/plant_app/BI_REPORT_DATASET_QUERIES.sql) as the dataset source.

### 2. Report Parameter

- Create `RunId` as an integer parameter.
- Use the first query in `BI_REPORT_DATASET_QUERIES.sql` for available values.
- Label field: `run_label`
- Value field: `run_id`

### 3. Datasets

Create these datasets from the query file:

- `dsRunPicker`
- `dsHeader`
- `dsSections`
- `dsEvaporation`
- `dsEvaporationRows`
- `dsStageFields`
- `dsStageTableRows`
- `dsStageTableCells`

### 4. Page Setup

- Page size: Letter portrait
- Margins: `0.4in` left/right and `0.5in` top/bottom
- Body width: about `7.7in`

### 5. Report Layout

At the top of the report:

- Add a rectangle for the packet header using `dsHeader`.
- Show:
  `run_label`,
  `run_status`,
  `product_name`,
  `blend_number`,
  `split_batch_number`,
  `created_at`,
  `run_notes`

For evaporation:

- Add a rectangle that only shows when `CountRows("dsEvaporation") > 0`.
- Add a small 2-column field table for the evaporation summary.
- Add a tablix under it bound to `dsEvaporationRows`.
- Columns:
  `row_time`,
  `feed_rate`,
  `evap_temp`,
  `row_vacuum`,
  `row_concentrate_ri`

For generic stages:

- Add a List bound to `dsSections`.
- Filter the list to exclude `section_key = "evaporation"`.
- Group by `section_key`.
- Inside the list:
  add the section heading from `section_title`
  add a nested tablix for `dsStageFields`
  filter it by matching `section_key`
  sort by `field_order`

For generic stage tables:

- Add another nested tablix or matrix bound to `dsStageTableCells`
  filter by matching `section_key`
  row groups:
  `table_title`,
  `row_no`
  column group:
  `column_label`
  value:
  `cell_value`
- Sort tables by `table_order` and cells by `column_order`.

For notes:

- Add a text box under each section bound to `stage_notes`.
- Hide it when the value is blank.

### 6. Page Breaks

- Group the full packet by `run_id` if you ever expand this to multi-run reporting.
- Add a page break between run groups.

## Recommended Standard Power BI Layout

### Page 1: `Run Packet`

- Page size:
  custom portrait layout, roughly paper-like
- Slicer:
  `run_label`
- Header area:
  cards or multi-row card from `vw_bi_run_packet_header`
- Section navigator:
  table from `vw_bi_run_packet_sections`
- Generic field block:
  matrix using `stage_title` and `field_label`
- Generic table block:
  matrix using
  rows:
  `stage_title`, `table_title`, `row_no`
  columns:
  `column_label`
  values:
  `First(cell_value)`

### Page 2: `Run Packet Drillthrough`

- Drillthrough filter on `run_id`
- Same visual structure as page 1
- Add optional audit/change visuals later from `field_change_log`

## Visual Mapping

- Run header:
  `vw_bi_run_packet_header`
- Evaporation summary:
  `vw_bi_latest_evaporation`
- Evaporation table:
  `vw_bi_latest_evaporation_rows`
- Generic section headers:
  `vw_bi_stage_fields`
- Generic section tables:
  `vw_bi_stage_table_cells`

## Sorting Rules

Use these in every visual so the page matches the print order:

- section sort: `section_order`
- stage sort: `stage_order`
- field sort: `field_order`
- table sort: `table_order`
- row sort: `row_no`
- column sort: `column_order`

## First Build I'd Do

1. Create a single-run paginated report using `RunId`.
2. Match the existing print packet section order exactly.
3. Once that looks right, copy the same datasets into a Power BI Desktop file for interactive slicing.

That gives you one report that feels like the print sheet and one BI page that stays familiar for users.
