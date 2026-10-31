:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_ID(DB_NAME()) <= 4
    THROW 51310, N'Hãy chọn một CSDL site, không chạy trong system database.', 1;
IF OBJECT_ID(N'dbo.TaiKhoan', N'U') IS NULL OR OBJECT_ID(N'dbo.Logs', N'U') IS NULL
    THROW 51311, N'Thiếu bảng dbo.TaiKhoan hoặc dbo.Logs; hãy chạy các migration trước.', 1;
GO

BEGIN TRY
    BEGIN TRANSACTION;

    IF COL_LENGTH(N'dbo.TaiKhoan', N'avatar_public_id') IS NULL
        ALTER TABLE dbo.TaiKhoan ADD avatar_public_id NVARCHAR(255) NULL;

    IF COL_LENGTH(N'dbo.TaiKhoan', N'avatar_secure_url') IS NULL
        ALTER TABLE dbo.TaiKhoan ADD avatar_secure_url NVARCHAR(1024) NULL;

    COMMIT TRANSACTION;
    PRINT N'Đã bảo đảm hai cột ảnh đại diện trên dbo.TaiKhoan.';
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
