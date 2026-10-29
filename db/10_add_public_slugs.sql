:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

/*
    Chạy một lần trong từng CSDL site QLTTNN_Q1, QLTTNN_Q7 và QLTTNN_TD.
    Slug thêm vào CoSo, MonHoc và KhoaHoc: danh mục công khai dùng trong trang/đường dẫn khóa học.
    Slug hiện có được giữ nguyên để không làm đổi URL đã phát hành.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_ID(DB_NAME()) <= 4
BEGIN
    ;THROW 51100, N'Hãy chọn một CSDL site, không chạy trong system database.', 1;
END;

IF OBJECT_ID(N'dbo.CoSo', N'U') IS NULL
   OR OBJECT_ID(N'dbo.MonHoc', N'U') IS NULL
   OR OBJECT_ID(N'dbo.KhoaHoc', N'U') IS NULL
BEGIN
    ;THROW 51101, N'Thiếu dbo.CoSo, dbo.MonHoc hoặc dbo.KhoaHoc.', 1;
END;

BEGIN TRY
    BEGIN TRANSACTION;

    IF COL_LENGTH(N'dbo.CoSo', N'slug') IS NULL
        ALTER TABLE dbo.CoSo ADD slug VARCHAR(120) NULL;

    IF COL_LENGTH(N'dbo.KhoaHoc', N'slug') IS NULL
        ALTER TABLE dbo.KhoaHoc ADD slug VARCHAR(160) NULL;

    IF COL_LENGTH(N'dbo.MonHoc', N'slug') IS NULL
        ALTER TABLE dbo.MonHoc ADD slug VARCHAR(120) NULL;

    /* Slug lấy từ tên các mục đã có; mã là fallback cho mục ngoài bộ dữ liệu khởi tạo. */
    EXEC sys.sp_executesql N'
        UPDATE dbo.CoSo
        SET slug = CASE ma_co_so
            WHEN ''Q1'' THEN ''co-so-quan-1''
            WHEN ''Q7'' THEN ''co-so-quan-7''
            WHEN ''TD'' THEN ''co-so-thu-duc''
            ELSE LOWER(REPLACE(ma_co_so, ''_'', ''-''))
        END
        WHERE slug IS NULL OR LTRIM(RTRIM(slug)) = '''';

        UPDATE dbo.KhoaHoc
        SET slug = CASE ma_khoa_hoc
            WHEN ''KH-IELTS-65'' THEN ''ielts-6-5''
            WHEN ''KH-JP-N5'' THEN ''tieng-nhat-n5''
            ELSE LOWER(REPLACE(ma_khoa_hoc, ''_'', ''-''))
        END
        WHERE slug IS NULL OR LTRIM(RTRIM(slug)) = '''';

        UPDATE dbo.MonHoc
        SET slug = CASE ma_mon
            WHEN ''MH-ENG'' THEN ''tieng-anh''
            WHEN ''MH-JPN'' THEN ''tieng-nhat''
            ELSE LOWER(REPLACE(ma_mon, ''_'', ''-''))
        END
        WHERE slug IS NULL OR LTRIM(RTRIM(slug)) = '''';

        IF EXISTS (SELECT 1 FROM dbo.CoSo WHERE slug IS NULL OR LTRIM(RTRIM(slug)) = '''')
           OR EXISTS (SELECT 1 FROM dbo.KhoaHoc WHERE slug IS NULL OR LTRIM(RTRIM(slug)) = '''')
           OR EXISTS (SELECT 1 FROM dbo.MonHoc WHERE slug IS NULL OR LTRIM(RTRIM(slug)) = '''')
            THROW 51102, N''Có cơ sở, môn học hoặc khóa học chưa được gán slug.'', 1;

        IF EXISTS (SELECT slug FROM dbo.CoSo GROUP BY slug HAVING COUNT_BIG(*) > 1)
           OR EXISTS (SELECT slug FROM dbo.KhoaHoc GROUP BY slug HAVING COUNT_BIG(*) > 1)
           OR EXISTS (SELECT slug FROM dbo.MonHoc GROUP BY slug HAVING COUNT_BIG(*) > 1)
            THROW 51103, N''Có slug bị trùng; hãy chỉnh slug để duy nhất trước khi tiếp tục.'', 1;';

    IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'dbo.CoSo') AND name = N'slug' AND is_nullable = 1)
        EXEC(N'ALTER TABLE dbo.CoSo ALTER COLUMN slug VARCHAR(120) NOT NULL;');

    IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'dbo.KhoaHoc') AND name = N'slug' AND is_nullable = 1)
        EXEC(N'ALTER TABLE dbo.KhoaHoc ALTER COLUMN slug VARCHAR(160) NOT NULL;');

    IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'dbo.MonHoc') AND name = N'slug' AND is_nullable = 1)
        EXEC(N'ALTER TABLE dbo.MonHoc ALTER COLUMN slug VARCHAR(120) NOT NULL;');

    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.CoSo') AND name = N'UQ_CoSo_slug' AND is_unique = 1)
        EXEC(N'ALTER TABLE dbo.CoSo ADD CONSTRAINT UQ_CoSo_slug UNIQUE (slug);');

    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.KhoaHoc') AND name = N'UQ_KhoaHoc_slug' AND is_unique = 1)
        EXEC(N'ALTER TABLE dbo.KhoaHoc ADD CONSTRAINT UQ_KhoaHoc_slug UNIQUE (slug);');

    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.MonHoc') AND name = N'UQ_MonHoc_slug' AND is_unique = 1)
        EXEC(N'ALTER TABLE dbo.MonHoc ADD CONSTRAINT UQ_MonHoc_slug UNIQUE (slug);');

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;

EXEC(N'
    SELECT DB_NAME() AS database_da_cap_nhat, N''CoSo'' AS ten_bang, ma_co_so AS ma_ban_ghi,
           slug, ten_co_so AS ten_hien_thi
    FROM dbo.CoSo
    UNION ALL
    SELECT DB_NAME(), N''KhoaHoc'', ma_khoa_hoc, slug, ten_khoa_hoc
    FROM dbo.KhoaHoc
    UNION ALL
    SELECT DB_NAME(), N''MonHoc'', ma_mon, slug, ten_mon
    FROM dbo.MonHoc
    ORDER BY ten_bang, ma_ban_ghi;');
GO
