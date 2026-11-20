/* Run after migration 39 on each QLTTNN_<SITE> database. Never move contact rows. */
SET NOCOUNT ON;
SET XACT_ABORT ON;
DECLARE @database sysname = DB_NAME();
IF LEFT(@database, 7) <> N'QLTTNN_' OR LEN(@database) <= 7 OR LEN(@database) > 17
    THROW 51430, N'Hãy chọn database QLTTNN_<SITE>.', 1;
DECLARE @site varchar(10) = SUBSTRING(@database, 8, 10);
IF OBJECT_ID(N'dbo.YeuCauLienHe', N'U') IS NULL
    THROW 51431, N'Thiếu YeuCauLienHe; chạy migration 39 trước.', 1;
IF NOT EXISTS (SELECT 1 FROM dbo.CoSo WHERE ma_co_so = @site)
    THROW 51432, N'Mã site của database không có trong CoSo.', 1;

BEGIN TRY
    BEGIN TRANSACTION;
    IF EXISTS (SELECT 1 FROM dbo.YeuCauLienHe WITH (TABLOCKX, HOLDLOCK)
               WHERE ma_co_so IS NULL OR ma_co_so <> @site)
        THROW 51433, N'Có liên hệ sai site; dừng để đối soát, không tự di chuyển/xóa.', 1;

    /* Recreate our named boundary so an incorrect existing predicate cannot pass. */
    IF EXISTS (SELECT 1 FROM sys.check_constraints
               WHERE parent_object_id = OBJECT_ID(N'dbo.YeuCauLienHe')
                 AND name = N'CK_YeuCauLienHe_site_local')
        ALTER TABLE dbo.YeuCauLienHe DROP CONSTRAINT CK_YeuCauLienHe_site_local;
    DECLARE @sql nvarchar(max) = N'ALTER TABLE dbo.YeuCauLienHe WITH CHECK '
        + N'ADD CONSTRAINT CK_YeuCauLienHe_site_local CHECK '
        + N'(ma_co_so IS NOT NULL AND ma_co_so = ' + QUOTENAME(@site, '''') + N');';
    EXEC sys.sp_executesql @sql;
    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
