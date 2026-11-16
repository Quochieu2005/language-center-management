:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_ID(DB_NAME()) <= 4
    THROW 51380, N'Hãy chọn một CSDL site, không chạy trong system database.', 1;
IF OBJECT_ID(N'dbo.HocVien', N'U') IS NULL
    THROW 51381, N'Thiếu bảng dbo.HocVien; hãy chạy schema và migration học viên trước.', 1;
GO

BEGIN TRY
    BEGIN TRANSACTION;

    IF COL_LENGTH(N'dbo.HocVien', N'avatar_public_id') IS NULL
        ALTER TABLE dbo.HocVien ADD avatar_public_id NVARCHAR(255) NULL;

    IF COL_LENGTH(N'dbo.HocVien', N'avatar_secure_url') IS NULL
        ALTER TABLE dbo.HocVien ADD avatar_secure_url NVARCHAR(1024) NULL;

    COMMIT TRANSACTION;
    PRINT N'Đã bảo đảm metadata ảnh đại diện Cloudinary trên dbo.HocVien.';
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
