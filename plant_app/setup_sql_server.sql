/*
  Plant App SQL Server setup

  Run this script in SQL Server Management Studio.
  If you want a different database name, replace [LonzaPlantOpsApp] below.
*/

IF DB_ID(N'LonzaPlantOpsApp') IS NULL
BEGIN
    CREATE DATABASE [LonzaPlantOpsApp];
END
GO

USE [LonzaPlantOpsApp];
GO

IF OBJECT_ID(N'dbo.users', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.users (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        employee_number NVARCHAR(50) NOT NULL,
        full_name NVARCHAR(255) NULL,
        [password] NVARCHAR(255) NOT NULL,
        [role] NVARCHAR(50) NOT NULL CONSTRAINT DF_users_role DEFAULT (N'operator'),
        active BIT NOT NULL CONSTRAINT DF_users_active DEFAULT ((1)),
        created_at NVARCHAR(50) NOT NULL,
        initials NVARCHAR(20) NULL,
        theme_preference NVARCHAR(20) NOT NULL CONSTRAINT DF_users_theme DEFAULT (N'light'),
        font_scale_preference NVARCHAR(20) NOT NULL CONSTRAINT DF_users_font DEFAULT (N'1')
    );
END
GO

IF OBJECT_ID(N'dbo.production_runs', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.production_runs (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        batch_number NVARCHAR(100) NULL,
        split_batch_number NVARCHAR(100) NULL,
        blend_number NVARCHAR(100) NULL,
        run_number NVARCHAR(100) NULL,
        batch_type NVARCHAR(50) NOT NULL CONSTRAINT DF_production_runs_batch_type DEFAULT (N'standard'),
        reused_batch BIT NOT NULL CONSTRAINT DF_production_runs_reused_batch DEFAULT ((0)),
        product_name NVARCHAR(255) NULL,
        shift_name NVARCHAR(100) NULL,
        operator_id NVARCHAR(50) NULL,
        notes NVARCHAR(MAX) NULL,
        [status] NVARCHAR(50) NOT NULL CONSTRAINT DF_production_runs_status DEFAULT (N'Open'),
        created_at NVARCHAR(50) NOT NULL,
        updated_at NVARCHAR(50) NOT NULL,
        final_edit_initials NVARCHAR(20) NULL,
        final_edit_notes NVARCHAR(MAX) NULL,
        finalized_at NVARCHAR(50) NULL,
        finalized_by NVARCHAR(50) NULL
    );
END
GO

IF OBJECT_ID(N'dbo.extraction_entries', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.extraction_entries (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        run_id INT NULL,
        employee NVARCHAR(50) NOT NULL,
        operator_initials NVARCHAR(20) NULL,
        entry_date NVARCHAR(50) NULL,
        entry_time NVARCHAR(50) NULL,
        [location] NVARCHAR(50) NOT NULL CONSTRAINT DF_extraction_entries_location DEFAULT (N'Pile'),
        time_on_pile NVARCHAR(50) NULL,
        start_time NVARCHAR(50) NULL,
        stop_time NVARCHAR(50) NULL,
        psf1_speed NVARCHAR(50) NULL,
        psf1_load NVARCHAR(50) NULL,
        psf1_blowback NVARCHAR(50) NULL,
        psf2_speed NVARCHAR(50) NULL,
        psf2_load NVARCHAR(50) NULL,
        psf2_blowback NVARCHAR(50) NULL,
        press_speed NVARCHAR(50) NULL,
        press_load NVARCHAR(50) NULL,
        press_blowback NVARCHAR(50) NULL,
        pressate_ri NVARCHAR(50) NULL,
        chip_bin_steam NVARCHAR(50) NULL,
        chip_chute_temp NVARCHAR(50) NULL,
        comments NVARCHAR(MAX) NULL,
        photo_path NVARCHAR(500) NULL,
<<<<<<< HEAD
=======
        signature_data NVARCHAR(MAX) NULL,
        signature_signed_at NVARCHAR(100) NULL,
>>>>>>> a88012f75bfc1cca5291e758423dbf80f32e58cc
        version_no INT NOT NULL CONSTRAINT DF_extraction_entries_version_no DEFAULT ((1)),
        previous_entry_id INT NULL,
        created_at NVARCHAR(50) NOT NULL
    );
END
GO

IF OBJECT_ID(N'dbo.filtration_entries', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.filtration_entries (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        run_id INT NULL,
        employee NVARCHAR(50) NOT NULL,
        operator_initials NVARCHAR(20) NULL,
        entry_date NVARCHAR(50) NULL,
        cycle_volume_set_point NVARCHAR(100) NULL,
        clarification_sequential_no NVARCHAR(50) NULL,
        retentate_flow_set_point NVARCHAR(50) NULL,
        zero_refract NVARCHAR(50) NULL,
        startup_time NVARCHAR(50) NULL,
        shutdown_time NVARCHAR(50) NULL,
        start_time NVARCHAR(50) NULL,
        stop_time NVARCHAR(50) NULL,
        comments NVARCHAR(MAX) NULL,
        photo_path NVARCHAR(500) NULL,
<<<<<<< HEAD
=======
        signature_data NVARCHAR(MAX) NULL,
        signature_signed_at NVARCHAR(100) NULL,
>>>>>>> a88012f75bfc1cca5291e758423dbf80f32e58cc
        payload_json NVARCHAR(MAX) NULL,
        version_no INT NOT NULL CONSTRAINT DF_filtration_entries_version_no DEFAULT ((1)),
        previous_entry_id INT NULL,
        created_at NVARCHAR(50) NOT NULL
    );
END
GO

IF OBJECT_ID(N'dbo.filtration_rows', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.filtration_rows (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        filtration_entry_id INT NOT NULL,
        row_group NVARCHAR(50) NULL,
        row_no INT NULL,
        row_time NVARCHAR(50) NULL,
        operator_initials NVARCHAR(50) NULL,
        fic1_gpm NVARCHAR(50) NULL,
        tit1 NVARCHAR(50) NULL,
        tit2 NVARCHAR(50) NULL,
        dpt NVARCHAR(50) NULL,
        dpm NVARCHAR(50) NULL,
        perm_total NVARCHAR(50) NULL,
        f12_gpm NVARCHAR(50) NULL,
        feed_ri NVARCHAR(50) NULL,
        retentate_ri NVARCHAR(50) NULL,
        permeate_ri NVARCHAR(50) NULL,
        perm_flow_c NVARCHAR(50) NULL,
        perm_flow_d NVARCHAR(50) NULL,
        qic1_ntu_turbidity NVARCHAR(50) NULL,
        pressure_pt1 NVARCHAR(50) NULL,
        pressure_pt2 NVARCHAR(50) NULL,
        pressure_pt3 NVARCHAR(50) NULL
    );
END
GO

IF OBJECT_ID(N'dbo.evaporation_entries', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.evaporation_entries (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        run_id INT NULL,
        employee NVARCHAR(50) NOT NULL,
        operator_initials NVARCHAR(20) NULL,
        entry_date NVARCHAR(50) NULL,
        evaporator_no NVARCHAR(50) NULL,
        startup_time NVARCHAR(50) NULL,
        shutdown_time NVARCHAR(50) NULL,
        feed_ri NVARCHAR(50) NULL,
        concentrate_ri NVARCHAR(50) NULL,
        steam_pressure NVARCHAR(50) NULL,
        vacuum NVARCHAR(50) NULL,
        sump_level NVARCHAR(50) NULL,
        product_temp NVARCHAR(50) NULL,
        comments NVARCHAR(MAX) NULL,
        photo_path NVARCHAR(500) NULL,
<<<<<<< HEAD
=======
        signature_data NVARCHAR(MAX) NULL,
        signature_signed_at NVARCHAR(100) NULL,
>>>>>>> a88012f75bfc1cca5291e758423dbf80f32e58cc
        version_no INT NOT NULL CONSTRAINT DF_evaporation_entries_version_no DEFAULT ((1)),
        previous_entry_id INT NULL,
        created_at NVARCHAR(50) NOT NULL
    );
END
GO

IF OBJECT_ID(N'dbo.evaporation_rows', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.evaporation_rows (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        evaporation_entry_id INT NOT NULL,
        row_no INT NULL,
        row_time NVARCHAR(50) NULL,
        feed_rate NVARCHAR(50) NULL,
        evap_temp NVARCHAR(50) NULL,
        row_vacuum NVARCHAR(50) NULL,
        row_concentrate_ri NVARCHAR(50) NULL
    );
END
GO

IF OBJECT_ID(N'dbo.audit_log', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.audit_log (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        table_name NVARCHAR(100) NOT NULL,
        record_id INT NOT NULL,
        action_type NVARCHAR(50) NOT NULL,
        changed_by NVARCHAR(50) NULL,
        old_data NVARCHAR(MAX) NULL,
        new_data NVARCHAR(MAX) NULL,
        created_at NVARCHAR(50) NOT NULL
    );
END
GO

IF OBJECT_ID(N'dbo.sheet_entries', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.sheet_entries (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        run_id INT NULL,
        stage_key NVARCHAR(100) NOT NULL,
        stage_title NVARCHAR(255) NOT NULL,
        employee NVARCHAR(50) NOT NULL,
        operator_initials NVARCHAR(20) NULL,
        entry_date NVARCHAR(50) NULL,
        comments NVARCHAR(MAX) NULL,
<<<<<<< HEAD
=======
        signature_data NVARCHAR(MAX) NULL,
        signature_signed_at NVARCHAR(100) NULL,
>>>>>>> a88012f75bfc1cca5291e758423dbf80f32e58cc
        payload_json NVARCHAR(MAX) NOT NULL,
        version_no INT NOT NULL CONSTRAINT DF_sheet_entries_version_no DEFAULT ((1)),
        previous_entry_id INT NULL,
        created_at NVARCHAR(50) NOT NULL
    );
END
GO

IF OBJECT_ID(N'dbo.field_change_log', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.field_change_log (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        run_id INT NULL,
        entry_table NVARCHAR(100) NOT NULL,
        record_id INT NOT NULL,
        field_name NVARCHAR(255) NOT NULL,
        field_value NVARCHAR(MAX) NULL,
        change_initials NVARCHAR(20) NOT NULL,
        changed_by_employee NVARCHAR(50) NOT NULL,
        created_at NVARCHAR(50) NOT NULL,
        original_value NVARCHAR(MAX) NULL,
        corrected_value NVARCHAR(MAX) NULL,
        correction_reason NVARCHAR(MAX) NULL
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'idx_users_employee_number' AND object_id = OBJECT_ID(N'dbo.users'))
BEGIN
    CREATE UNIQUE INDEX idx_users_employee_number ON dbo.users(employee_number);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'idx_runs_updated_at' AND object_id = OBJECT_ID(N'dbo.production_runs'))
BEGIN
    CREATE INDEX idx_runs_updated_at ON dbo.production_runs(updated_at DESC);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'idx_runs_batch_number' AND object_id = OBJECT_ID(N'dbo.production_runs'))
BEGIN
    CREATE INDEX idx_runs_batch_number ON dbo.production_runs(batch_number);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'idx_extraction_run_created' AND object_id = OBJECT_ID(N'dbo.extraction_entries'))
BEGIN
    CREATE INDEX idx_extraction_run_created ON dbo.extraction_entries(run_id, created_at DESC);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'idx_extraction_created_at' AND object_id = OBJECT_ID(N'dbo.extraction_entries'))
BEGIN
    CREATE INDEX idx_extraction_created_at ON dbo.extraction_entries(created_at DESC);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'idx_filtration_run_created' AND object_id = OBJECT_ID(N'dbo.filtration_entries'))
BEGIN
    CREATE INDEX idx_filtration_run_created ON dbo.filtration_entries(run_id, created_at DESC);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'idx_filtration_created_at' AND object_id = OBJECT_ID(N'dbo.filtration_entries'))
BEGIN
    CREATE INDEX idx_filtration_created_at ON dbo.filtration_entries(created_at DESC);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'idx_filtration_rows_entry_row' AND object_id = OBJECT_ID(N'dbo.filtration_rows'))
BEGIN
    CREATE INDEX idx_filtration_rows_entry_row ON dbo.filtration_rows(filtration_entry_id, row_group, row_no);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'idx_evaporation_run_created' AND object_id = OBJECT_ID(N'dbo.evaporation_entries'))
BEGIN
    CREATE INDEX idx_evaporation_run_created ON dbo.evaporation_entries(run_id, created_at DESC);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'idx_evaporation_created_at' AND object_id = OBJECT_ID(N'dbo.evaporation_entries'))
BEGIN
    CREATE INDEX idx_evaporation_created_at ON dbo.evaporation_entries(created_at DESC);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'idx_evaporation_rows_entry_row' AND object_id = OBJECT_ID(N'dbo.evaporation_rows'))
BEGIN
    CREATE INDEX idx_evaporation_rows_entry_row ON dbo.evaporation_rows(evaporation_entry_id, row_no);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'idx_sheet_run_stage_created' AND object_id = OBJECT_ID(N'dbo.sheet_entries'))
BEGIN
    CREATE INDEX idx_sheet_run_stage_created ON dbo.sheet_entries(run_id, stage_key, created_at DESC);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'idx_sheet_created_at' AND object_id = OBJECT_ID(N'dbo.sheet_entries'))
BEGIN
    CREATE INDEX idx_sheet_created_at ON dbo.sheet_entries(created_at DESC);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'idx_audit_table_record_created' AND object_id = OBJECT_ID(N'dbo.audit_log'))
BEGIN
    CREATE INDEX idx_audit_table_record_created ON dbo.audit_log(table_name, record_id, created_at DESC);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'idx_audit_created_at' AND object_id = OBJECT_ID(N'dbo.audit_log'))
BEGIN
    CREATE INDEX idx_audit_created_at ON dbo.audit_log(created_at DESC);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'idx_field_change_run_created' AND object_id = OBJECT_ID(N'dbo.field_change_log'))
BEGIN
    CREATE INDEX idx_field_change_run_created ON dbo.field_change_log(run_id, created_at DESC);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'idx_field_change_created_at' AND object_id = OBJECT_ID(N'dbo.field_change_log'))
BEGIN
    CREATE INDEX idx_field_change_created_at ON dbo.field_change_log(created_at DESC);
END
GO

IF NOT EXISTS (SELECT 1 FROM dbo.users WHERE employee_number = N'1001')
BEGIN
    INSERT INTO dbo.users (
        employee_number,
        full_name,
        [password],
        [role],
        initials,
        active,
        created_at,
        theme_preference,
        font_scale_preference
    )
    VALUES (
        N'1001',
        N'Operator 1',
        N'1001',
        N'operator',
        N'OP',
        1,
        CONVERT(NVARCHAR(50), SYSDATETIME(), 126),
        N'light',
        N'1'
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM dbo.users WHERE employee_number = N'2001')
BEGIN
    INSERT INTO dbo.users (
        employee_number,
        full_name,
        [password],
        [role],
        initials,
        active,
        created_at,
        theme_preference,
        font_scale_preference
    )
    VALUES (
        N'2001',
        N'Supervisor 1',
        N'2001',
        N'supervisor',
        N'SU',
        1,
        CONVERT(NVARCHAR(50), SYSDATETIME(), 126),
        N'light',
        N'1'
    );
END
GO

SELECT
    DB_NAME() AS current_database,
    (SELECT COUNT(*) FROM dbo.users) AS users_count,
    (SELECT COUNT(*) FROM dbo.production_runs) AS runs_count;
GO
