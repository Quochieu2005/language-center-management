:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

/*
    Chạy trong từng CSDL site QLTTNN_Q1, QLTTNN_Q7 và QLTTNN_TD.
    Đổi tên cột nhưng giữ nguyên giá trị BCrypt; không ghi mật khẩu gốc vào CSDL.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_ID(DB_NAME()) <= 4
BEGIN
    ;THROW 51090, N'Hãy chọn một CSDL site, không chạy trong system database.', 1;
END;

IF OBJECT_ID(N'dbo.TaiKhoan', N'U') IS NULL
BEGIN
    ;THROW 51091, N'Thiếu bảng dbo.TaiKhoan.', 1;
END;

BEGIN TRY
    BEGIN TRANSACTION;

    DECLARE @has_old_password_column BIT =
        CASE WHEN COL_LENGTH(N'dbo.TaiKhoan', N'mat_khau_bam') IS NULL THEN 0 ELSE 1 END;
    DECLARE @has_password_column BIT =
        CASE WHEN COL_LENGTH(N'dbo.TaiKhoan', N'mat_khau') IS NULL THEN 0 ELSE 1 END;

    IF @has_old_password_column = 1 AND @has_password_column = 1
    BEGIN
        EXEC sys.sp_executesql N'
            IF EXISTS
            (
                SELECT 1 FROM dbo.TaiKhoan
                WHERE CONVERT(NVARCHAR(255), mat_khau_bam) <> CONVERT(NVARCHAR(255), mat_khau)
            )
                THROW 51092, N''Hai cột mật khẩu có dữ liệu khác nhau; dừng để tránh mất dữ liệu.'', 1;
            ALTER TABLE dbo.TaiKhoan DROP COLUMN mat_khau_bam;';
    END
    ELSE IF @has_old_password_column = 1
    BEGIN
        EXEC sys.sp_executesql N'EXEC sys.sp_rename N''dbo.TaiKhoan.mat_khau_bam'', N''mat_khau'', N''COLUMN'';';
    END
    ELSE IF @has_password_column = 0
    BEGIN
        ;THROW 51093, N'Không tìm thấy cột mật khẩu hiện tại để đổi tên.', 1;
    END;

    IF COL_LENGTH(N'dbo.TaiKhoan', N'slug') IS NULL
        EXEC(N'ALTER TABLE dbo.TaiKhoan ADD slug VARCHAR(120) NULL;');

    EXEC sys.sp_executesql N'
        UPDATE dbo.TaiKhoan
        SET slug = LOWER(ma_tai_khoan)
        WHERE slug IS NULL OR LTRIM(RTRIM(slug)) = '''';

        IF EXISTS
        (
            SELECT 1 FROM dbo.TaiKhoan
            WHERE slug = ''admin-big-thaitrungquochieu''
              AND LOWER(email) <> ''thaitrungquochieu@gmail.com''
        )
            THROW 51094, N''Slug admin-big-thaitrungquochieu đã thuộc tài khoản khác.'', 1;

        UPDATE dbo.TaiKhoan
        SET slug = ''admin-big-thaitrungquochieu''
        WHERE LOWER(email) = ''thaitrungquochieu@gmail.com'';

        IF EXISTS (SELECT 1 FROM dbo.TaiKhoan WHERE slug IS NULL OR LTRIM(RTRIM(slug)) = '''')
            THROW 51095, N''Có tài khoản chưa được gán slug.'', 1;

        IF EXISTS (SELECT slug FROM dbo.TaiKhoan GROUP BY slug HAVING COUNT_BIG(*) > 1)
            THROW 51096, N''Slug bị trùng trong TaiKhoan; hãy đối soát trước khi áp dụng unique constraint.'', 1;

        IF EXISTS
        (
            SELECT 1 FROM sys.columns
            WHERE object_id = OBJECT_ID(N''dbo.TaiKhoan'')
              AND name = N''slug'' AND is_nullable = 1
        )
            ALTER TABLE dbo.TaiKhoan ALTER COLUMN slug VARCHAR(120) NOT NULL;

        IF NOT EXISTS
        (
            SELECT 1 FROM sys.indexes
            WHERE object_id = OBJECT_ID(N''dbo.TaiKhoan'')
              AND name = N''UQ_TaiKhoan_slug'' AND is_unique = 1
        )
            ALTER TABLE dbo.TaiKhoan ADD CONSTRAINT UQ_TaiKhoan_slug UNIQUE (slug);';

    IF EXISTS
    (
        SELECT 1 FROM sys.extended_properties
        WHERE major_id = OBJECT_ID(N'dbo.TaiKhoan')
          AND minor_id = COLUMNPROPERTY(OBJECT_ID(N'dbo.TaiKhoan'), N'mat_khau', 'ColumnId')
          AND name = N'MS_Description'
    )
        EXEC sys.sp_updateextendedproperty
            @name=N'MS_Description',
            @value=N'Mật khẩu được lưu dưới dạng BCryptSHA256 hash; không lưu mật khẩu gốc.',
            @level0type=N'SCHEMA', @level0name=N'dbo',
            @level1type=N'TABLE', @level1name=N'TaiKhoan',
            @level2type=N'COLUMN', @level2name=N'mat_khau';
    ELSE
        EXEC sys.sp_addextendedproperty
            @name=N'MS_Description',
            @value=N'Mật khẩu được lưu dưới dạng BCryptSHA256 hash; không lưu mật khẩu gốc.',
            @level0type=N'SCHEMA', @level0name=N'dbo',
            @level1type=N'TABLE', @level1name=N'TaiKhoan',
            @level2type=N'COLUMN', @level2name=N'mat_khau';

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;

EXEC(N'
    SELECT DB_NAME() AS database_da_cap_nhat,
           COUNT_BIG(*) AS so_tai_khoan,
           SUM(CASE WHEN slug IS NULL OR LTRIM(RTRIM(slug)) = '''' THEN 1 ELSE 0 END) AS so_slug_thieu,
           SUM(CASE WHEN LOWER(email) = ''thaitrungquochieu@gmail.com''
                         AND slug = ''admin-big-thaitrungquochieu''
                    THEN 1 ELSE 0 END) AS so_admin_big_co_slug
    FROM dbo.TaiKhoan;');
GO
