:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_ID(DB_NAME()) <= 4
    THROW 51480, N'Hãy chọn một CSDL site, không chạy trong system database.', 1;
IF OBJECT_ID(N'dbo.TaiKhoan', N'U') IS NULL
    THROW 51481, N'Thiếu bảng dbo.TaiKhoan; hãy chạy schema trước.', 1;
GO

-- Chạy trên MỌI site (Q1, Q7, TD) TRƯỚC khi API bắt đầu tạo hoặc nhân bản tài khoản vai trò nguoi_dung.
-- nguoi_dung: tài khoản xem website, chưa thuộc cơ sở nào (ma_co_so NULL) và chưa có hồ sơ học viên.
-- Hồ sơ của họ nằm ở bảng dbo.NguoiDung tại authority (migration 49), không phải cột trong TaiKhoan.
BEGIN TRY
    BEGIN TRANSACTION;

    IF NOT EXISTS (
        SELECT 1 FROM sys.check_constraints
        WHERE name = N'CK_TaiKhoan_vai_tro' AND parent_object_id = OBJECT_ID(N'dbo.TaiKhoan')
          AND definition LIKE N'%nguoi_dung%'
    )
    BEGIN
        IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = N'CK_TaiKhoan_vai_tro' AND parent_object_id = OBJECT_ID(N'dbo.TaiKhoan'))
            EXEC(N'ALTER TABLE dbo.TaiKhoan DROP CONSTRAINT CK_TaiKhoan_vai_tro');
        EXEC(N'ALTER TABLE dbo.TaiKhoan ADD CONSTRAINT CK_TaiKhoan_vai_tro CHECK
               (vai_tro IN (''admin_big'', ''nhan_vien'', ''giao_vien'', ''hoc_vien'', ''nguoi_dung''))');
    END;

    IF NOT EXISTS (
        SELECT 1 FROM sys.check_constraints
        WHERE name = N'CK_TaiKhoan_pham_vi' AND parent_object_id = OBJECT_ID(N'dbo.TaiKhoan')
          AND definition LIKE N'%nguoi_dung%'
    )
    BEGIN
        IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = N'CK_TaiKhoan_pham_vi' AND parent_object_id = OBJECT_ID(N'dbo.TaiKhoan'))
            EXEC(N'ALTER TABLE dbo.TaiKhoan DROP CONSTRAINT CK_TaiKhoan_pham_vi');
        EXEC(N'ALTER TABLE dbo.TaiKhoan ADD CONSTRAINT CK_TaiKhoan_pham_vi CHECK
               ((vai_tro IN (''admin_big'', ''nguoi_dung'') AND ma_co_so IS NULL)
                OR (vai_tro NOT IN (''admin_big'', ''nguoi_dung'') AND ma_co_so IS NOT NULL))');
    END;

    COMMIT TRANSACTION;
    PRINT N'Đã cho phép vai trò nguoi_dung (ma_co_so NULL) trong dbo.TaiKhoan.';
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
