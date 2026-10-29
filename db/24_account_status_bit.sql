/*
    Run on every site database (Q1, Q7, TD) during a maintenance window.
    TaiKhoan.trang_thai is now BIT: 1 = active, 0 = inactive.
    Account active/inactive state is stored as BIT in TaiKhoan.trang_thai.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.TaiKhoan', N'U') IS NULL
    THROW 51241, N'Thiếu bảng dbo.TaiKhoan; hãy cài schema trước.', 1;

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.CK_TaiKhoan_trang_thai', N'C') IS NOT NULL
        ALTER TABLE dbo.TaiKhoan DROP CONSTRAINT CK_TaiKhoan_trang_thai;

    DECLARE @default_name sysname;
    SELECT @default_name = dc.name
    FROM sys.default_constraints AS dc
    INNER JOIN sys.columns AS c
        ON c.object_id = dc.parent_object_id AND c.column_id = dc.parent_column_id
    WHERE dc.parent_object_id = OBJECT_ID(N'dbo.TaiKhoan')
      AND c.name = N'trang_thai';

    IF @default_name IS NOT NULL
    BEGIN
        DECLARE @drop_default_sql NVARCHAR(500) =
            N'ALTER TABLE dbo.TaiKhoan DROP CONSTRAINT ' + QUOTENAME(@default_name) + N';';
        EXEC sys.sp_executesql @drop_default_sql;
    END;

    UPDATE dbo.TaiKhoan
    SET trang_thai = CASE
        WHEN LOWER(LTRIM(RTRIM(CONVERT(VARCHAR(20), trang_thai))))
             IN ('1', 'true', 'active', 'hoat_dong') THEN 1
        ELSE 0
    END;

    IF EXISTS
    (
        SELECT 1 FROM sys.columns AS c
        INNER JOIN sys.types AS t ON t.user_type_id = c.user_type_id
        WHERE c.object_id = OBJECT_ID(N'dbo.TaiKhoan')
          AND c.name = N'trang_thai' AND t.name <> N'bit'
    )
        ALTER TABLE dbo.TaiKhoan ALTER COLUMN trang_thai BIT NOT NULL;

    ALTER TABLE dbo.TaiKhoan
        ADD CONSTRAINT DF_TaiKhoan_trang_thai DEFAULT (1) FOR trang_thai;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

SELECT DB_NAME() AS database_da_cap_nhat,
       TYPE_NAME(COLUMNPROPERTY(OBJECT_ID(N'dbo.TaiKhoan'), N'trang_thai', 'SystemTypeId'))
           AS kieu_trang_thai_tai_khoan;
GO
