/*
    Run once on every active site database after migration 18.
    Adds a site-local notification audience for Admin Small and branch staff.
*/
SET XACT_ABORT ON;
GO

IF OBJECT_ID(N'dbo.ThongBao', N'U') IS NULL
    THROW 51042, 'dbo.ThongBao is missing; apply the notification schema first.', 1;
GO

BEGIN TRANSACTION;

IF EXISTS (
    SELECT 1
    FROM sys.check_constraints
    WHERE parent_object_id = OBJECT_ID(N'dbo.ThongBao')
      AND name = N'CK_ThongBao_doi_tuong'
)
    ALTER TABLE dbo.ThongBao DROP CONSTRAINT CK_ThongBao_doi_tuong;

ALTER TABLE dbo.ThongBao WITH CHECK
ADD CONSTRAINT CK_ThongBao_doi_tuong
CHECK (doi_tuong IN ('admin_all', 'admin_big', 'admin_small', 'site_staff'));

ALTER TABLE dbo.ThongBao CHECK CONSTRAINT CK_ThongBao_doi_tuong;

COMMIT TRANSACTION;
GO
