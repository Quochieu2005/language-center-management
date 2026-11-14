/* Add calendar duration to the existing shared KhoaHoc table at every site. */
SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF OBJECT_ID(N'dbo.KhoaHoc', N'U') IS NULL
    THROW 51330, N'Thiếu bảng dbo.KhoaHoc; hãy tạo schema hiện có trước.', 1;

IF COL_LENGTH(N'dbo.KhoaHoc', N'thoi_luong_so') IS NULL
    ALTER TABLE dbo.KhoaHoc ADD thoi_luong_so SMALLINT NULL;

IF COL_LENGTH(N'dbo.KhoaHoc', N'thoi_luong_don_vi') IS NULL
    ALTER TABLE dbo.KhoaHoc ADD thoi_luong_don_vi VARCHAR(10) NULL;

IF NOT EXISTS (
    SELECT 1 FROM sys.check_constraints
    WHERE parent_object_id = OBJECT_ID(N'dbo.KhoaHoc')
      AND name = N'CK_KhoaHoc_thoi_luong'
)
    EXEC(N'
        ALTER TABLE dbo.KhoaHoc ADD CONSTRAINT CK_KhoaHoc_thoi_luong CHECK (
            (thoi_luong_so IS NULL AND thoi_luong_don_vi IS NULL)
            OR (thoi_luong_so IS NOT NULL AND thoi_luong_so > 0
                AND thoi_luong_don_vi IS NOT NULL
                AND thoi_luong_don_vi IN (''thang'', ''ngay''))
        );
    ');

COMMIT TRANSACTION;

SELECT DB_NAME() AS database_name,
       COL_LENGTH(N'dbo.KhoaHoc', N'thoi_luong_so') AS thoi_luong_so_bytes,
       COL_LENGTH(N'dbo.KhoaHoc', N'thoi_luong_don_vi') AS thoi_luong_don_vi_bytes;
