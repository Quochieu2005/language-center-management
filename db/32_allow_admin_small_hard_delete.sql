:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

/*
    Chạy riêng trên từng CSDL site trước khi bật xóa vĩnh viễn Admin Small.
    Mã người thao tác trong giao dịch/lịch sử được giữ như dữ liệu lịch sử, không FK.
    Không tạo bảng/database và không xóa bản ghi nghiệp vụ hoặc nhật ký.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_ID(DB_NAME()) <= 4
    THROW 51320, N'Hãy chọn một CSDL site, không chạy trong system database.', 1;
IF OBJECT_ID(N'dbo.TaiKhoan', N'U') IS NULL
    THROW 51321, N'Thiếu dbo.TaiKhoan; hãy cài schema trước.', 1;
GO

BEGIN TRY
    BEGIN TRANSACTION;

    DECLARE @fk TABLE (table_name sysname NOT NULL, constraint_name sysname NOT NULL);
    INSERT INTO @fk (table_name, constraint_name) VALUES
        (N'GiaoDichChuyenCoSo', N'FK_GiaoDichChuyenCoSo_TaiKhoanDeNghi'),
        (N'GiaoDichChuyenCoSo', N'FK_GiaoDichChuyenCoSo_TaiKhoanQuyetDinh'),
        (N'LichSuChuyenCoSo', N'FK_LichSuChuyenCoSo_TaiKhoan'),
        (N'DiemDanh', N'FK_DiemDanh_TaiKhoan'),
        (N'NhatKyHeThong', N'FK_NhatKyHeThong_TaiKhoan');

    DECLARE @table sysname, @constraint sysname, @sql nvarchar(500);
    DECLARE fk_cursor CURSOR LOCAL FAST_FORWARD FOR
        SELECT table_name, constraint_name FROM @fk;
    OPEN fk_cursor;
    FETCH NEXT FROM fk_cursor INTO @table, @constraint;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        IF OBJECT_ID(N'dbo.' + @table, N'U') IS NOT NULL
           AND EXISTS (
               SELECT 1 FROM sys.foreign_keys
               WHERE parent_object_id = OBJECT_ID(N'dbo.' + @table)
                 AND name = @constraint
           )
        BEGIN
            SET @sql = N'ALTER TABLE dbo.' + QUOTENAME(@table)
                     + N' DROP CONSTRAINT ' + QUOTENAME(@constraint) + N';';
            EXEC sys.sp_executesql @sql;
        END;
        FETCH NEXT FROM fk_cursor INTO @table, @constraint;
    END;
    CLOSE fk_cursor;
    DEALLOCATE fk_cursor;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF CURSOR_STATUS('local', 'fk_cursor') >= 0 CLOSE fk_cursor;
    IF CURSOR_STATUS('local', 'fk_cursor') > -3 DEALLOCATE fk_cursor;
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
