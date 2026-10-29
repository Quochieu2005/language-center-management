/*
    Run once on every site database: QLTTNN_Q1, QLTTNN_Q7 and QLTTNN_TD.
    TaiKhoan remains a replicated account table. HocVien.slug and ma_tai_khoan
    are local to each site; the account foreign key points only to that site's
    local replica. This script does not create a central business database.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.TaiKhoan', N'U') IS NULL
   OR OBJECT_ID(N'dbo.HocVien', N'U') IS NULL
   OR OBJECT_ID(N'dbo.DangKy', N'U') IS NULL
    THROW 51191, N'Thiếu TaiKhoan, HocVien hoặc DangKy; hãy cài schema trước.', 1;
GO

BEGIN TRY
    BEGIN TRANSACTION;

    IF COL_LENGTH(N'dbo.HocVien', N'slug') IS NULL
        EXEC sys.sp_executesql N'ALTER TABLE dbo.HocVien ADD slug VARCHAR(160) NULL;';

    IF COL_LENGTH(N'dbo.HocVien', N'ma_tai_khoan') IS NULL
        EXEC sys.sp_executesql N'ALTER TABLE dbo.HocVien ADD ma_tai_khoan VARCHAR(24) NULL;';

    EXEC sys.sp_executesql N'
        UPDATE dbo.HocVien
        SET slug = LOWER(REPLACE(ma_hoc_vien, ''_'', ''-''))
        WHERE slug IS NULL OR LTRIM(RTRIM(slug)) = '''';

        IF EXISTS (SELECT slug FROM dbo.HocVien GROUP BY slug HAVING COUNT_BIG(*) > 1)
            THROW 51192, N''Slug học viên bị trùng trong site; hãy xử lý trùng trước khi chạy lại.'', 1;';

    IF EXISTS
       (SELECT 1 FROM sys.columns
        WHERE object_id = OBJECT_ID(N'dbo.HocVien') AND name = N'slug' AND is_nullable = 1)
        EXEC sys.sp_executesql N'ALTER TABLE dbo.HocVien ALTER COLUMN slug VARCHAR(160) NOT NULL;';

    IF EXISTS
       (SELECT 1 FROM sys.check_constraints
        WHERE parent_object_id = OBJECT_ID(N'dbo.TaiKhoan') AND name = N'CK_TaiKhoan_vai_tro')
        ALTER TABLE dbo.TaiKhoan DROP CONSTRAINT CK_TaiKhoan_vai_tro;

    ALTER TABLE dbo.TaiKhoan WITH CHECK ADD CONSTRAINT CK_TaiKhoan_vai_tro
        CHECK (vai_tro IN ('admin_big', 'nhan_vien', 'giao_vien', 'hoc_vien'));

    IF NOT EXISTS
       (SELECT 1 FROM sys.indexes
        WHERE object_id = OBJECT_ID(N'dbo.HocVien') AND name = N'UQ_HocVien_slug' AND is_unique = 1)
        EXEC sys.sp_executesql N'ALTER TABLE dbo.HocVien ADD CONSTRAINT UQ_HocVien_slug UNIQUE (slug);';

    IF NOT EXISTS
       (SELECT 1 FROM sys.foreign_keys
        WHERE parent_object_id = OBJECT_ID(N'dbo.HocVien') AND name = N'FK_HocVien_TaiKhoan')
        EXEC sys.sp_executesql N'ALTER TABLE dbo.HocVien WITH CHECK ADD CONSTRAINT FK_HocVien_TaiKhoan
            FOREIGN KEY (ma_tai_khoan) REFERENCES dbo.TaiKhoan(ma_tai_khoan);';

    IF NOT EXISTS
       (SELECT 1 FROM sys.indexes
        WHERE object_id = OBJECT_ID(N'dbo.HocVien') AND name = N'UX_HocVien_ma_tai_khoan')
        EXEC sys.sp_executesql N'CREATE UNIQUE INDEX UX_HocVien_ma_tai_khoan
            ON dbo.HocVien (ma_tai_khoan)
            WHERE ma_tai_khoan IS NOT NULL;';

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

SELECT DB_NAME() AS database_da_cap_nhat,
       COL_LENGTH(N'dbo.HocVien', N'slug') AS do_dai_cot_slug,
       COL_LENGTH(N'dbo.HocVien', N'ma_tai_khoan') AS do_dai_cot_ma_tai_khoan;
GO
