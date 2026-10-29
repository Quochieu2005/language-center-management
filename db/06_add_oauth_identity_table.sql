:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

/*
    Deprecated migration retained so old setup notes do not accidentally create
    dbo.TaiKhoanLienKetOAuth again. OAuth provider IDs now live on dbo.TaiKhoan.
    For an existing database, run 27_move_oauth_identity_to_account.sql instead.
*/
SET NOCOUNT ON;

PRINT N'06_add_oauth_identity_table.sql đã ngừng sử dụng. Hãy chạy 27_move_oauth_identity_to_account.sql.';
GO
