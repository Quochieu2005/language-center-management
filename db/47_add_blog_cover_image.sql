:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_ID(DB_NAME()) <= 4
    THROW 51470, N'Hãy chọn một CSDL site, không chạy trong system database.', 1;
IF OBJECT_ID(N'dbo.BaiVietBlog', N'U') IS NULL
    THROW 51471, N'Thiếu bảng dbo.BaiVietBlog; hãy chạy 36_add_blog_tables.sql trước.', 1;
GO

-- Chạy trên MỌI site (Q1, Q7, TD): Blog là dữ liệu nhân bản, site thiếu cột sẽ bị API coi là thiếu site.
IF COL_LENGTH(N'dbo.BaiVietBlog', N'anh_bia_public_id') IS NULL
    EXEC(N'ALTER TABLE dbo.BaiVietBlog ADD anh_bia_public_id NVARCHAR(255) NULL');
IF COL_LENGTH(N'dbo.BaiVietBlog', N'anh_bia_url') IS NULL
    EXEC(N'ALTER TABLE dbo.BaiVietBlog ADD anh_bia_url NVARCHAR(1024) NULL');
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = N'CK_BaiVietBlog_anh_bia')
    EXEC(N'ALTER TABLE dbo.BaiVietBlog ADD CONSTRAINT CK_BaiVietBlog_anh_bia CHECK
           ((anh_bia_public_id IS NULL AND anh_bia_url IS NULL)
            OR (anh_bia_public_id IS NOT NULL AND anh_bia_url IS NOT NULL))');
GO

PRINT N'Đã bảo đảm metadata ảnh bìa Cloudinary trên dbo.BaiVietBlog.';
GO
