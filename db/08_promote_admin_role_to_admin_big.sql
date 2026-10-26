:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

/*
    Rename the global administrator role from admin to admin_big.
    Run once per existing site database. Enable SQLCMD Mode in SSMS and set
    DatabaseName to each active site's database. Re-running is safe.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_ID(DB_NAME()) <= 4
BEGIN
    ;THROW 51080, N'Hãy chọn một CSDL site, không chạy trong system database.', 1;
END;

IF OBJECT_ID(N'dbo.TaiKhoan', N'U') IS NULL
BEGIN
    ;THROW 51081, N'Thiếu dbo.TaiKhoan.', 1;
END;

IF EXISTS
(
    SELECT 1 FROM dbo.TaiKhoan
    WHERE vai_tro NOT IN ('admin', 'admin_big', 'nhan_vien', 'giao_vien')
       OR (vai_tro IN ('admin', 'admin_big') AND ma_co_so IS NOT NULL)
       OR (vai_tro NOT IN ('admin', 'admin_big') AND ma_co_so IS NULL)
)
BEGIN
    ;THROW 51082, N'Dữ liệu vai trò/phạm vi tài khoản không hợp lệ; dừng để đối soát trước khi đổi constraint.', 1;
END;

BEGIN TRY
    BEGIN TRANSACTION;

    IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE parent_object_id = OBJECT_ID(N'dbo.TaiKhoan')
               AND name = N'CK_TaiKhoan_vai_tro')
        ALTER TABLE dbo.TaiKhoan DROP CONSTRAINT CK_TaiKhoan_vai_tro;

    IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE parent_object_id = OBJECT_ID(N'dbo.TaiKhoan')
               AND name = N'CK_TaiKhoan_pham_vi')
        ALTER TABLE dbo.TaiKhoan DROP CONSTRAINT CK_TaiKhoan_pham_vi;

    UPDATE dbo.TaiKhoan
    SET vai_tro = 'admin_big', phien_ban = phien_ban + 1,
        cap_nhat_luc = SYSUTCDATETIME()
    WHERE vai_tro = 'admin';

    ALTER TABLE dbo.TaiKhoan WITH CHECK
        ADD CONSTRAINT CK_TaiKhoan_vai_tro
        CHECK (vai_tro IN ('admin_big', 'nhan_vien', 'giao_vien'));

    ALTER TABLE dbo.TaiKhoan WITH CHECK
        ADD CONSTRAINT CK_TaiKhoan_pham_vi
        CHECK
        (
            (vai_tro = 'admin_big' AND ma_co_so IS NULL)
            OR (vai_tro <> 'admin_big' AND ma_co_so IS NOT NULL)
        );

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

SELECT DB_NAME() AS database_dang_cap_nhat,
       ma_tai_khoan, vai_tro, ma_co_so, trang_thai
FROM dbo.TaiKhoan
WHERE vai_tro = 'admin_big';
GO
