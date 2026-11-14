/* Run once per site database; preserves existing course durations. */
SET XACT_ABORT ON;
BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.KhoaHoc', N'U') IS NULL
    BEGIN
        ;THROW 51334, N'Thiếu bảng dbo.KhoaHoc; hãy tạo schema trước.', 1;
    END;

    IF EXISTS (
        SELECT 1 FROM sys.check_constraints
        WHERE parent_object_id = OBJECT_ID(N'dbo.KhoaHoc')
          AND name = N'CK_KhoaHoc_thoi_luong'
    )
        ALTER TABLE dbo.KhoaHoc DROP CONSTRAINT CK_KhoaHoc_thoi_luong;

    IF COL_LENGTH(N'dbo.KhoaHoc', N'thoi_luong_so') IS NULL
        ALTER TABLE dbo.KhoaHoc ADD thoi_luong_so DECIMAL(7,2) NULL;
    ELSE
        ALTER TABLE dbo.KhoaHoc ALTER COLUMN thoi_luong_so DECIMAL(7,2) NULL;

    IF COL_LENGTH(N'dbo.KhoaHoc', N'thoi_luong_don_vi') IS NULL
        ALTER TABLE dbo.KhoaHoc ADD thoi_luong_don_vi VARCHAR(10) NULL;

    ALTER TABLE dbo.KhoaHoc ADD CONSTRAINT CK_KhoaHoc_thoi_luong CHECK (
        (thoi_luong_so IS NULL AND thoi_luong_don_vi IS NULL)
        OR (thoi_luong_so IS NOT NULL AND thoi_luong_so > 0
            AND thoi_luong_don_vi IS NOT NULL
            AND thoi_luong_don_vi IN ('thang', 'ngay')
            AND (thoi_luong_don_vi <> 'ngay'
                 OR thoi_luong_so = FLOOR(thoi_luong_so)))
    );

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;

SELECT DB_NAME() AS database_name,
       DATA_TYPE,
       NUMERIC_PRECISION,
       NUMERIC_SCALE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = N'dbo'
  AND TABLE_NAME = N'KhoaHoc'
  AND COLUMN_NAME = N'thoi_luong_so';
