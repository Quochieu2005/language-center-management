SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.KhoaHoc', N'U') IS NULL
    BEGIN
        ;THROW 50000, 'dbo.KhoaHoc does not exist.', 1;
    END;

    IF OBJECT_ID(N'dbo.CK_KhoaHoc_so_buoi', N'C') IS NOT NULL
        ALTER TABLE dbo.KhoaHoc DROP CONSTRAINT CK_KhoaHoc_so_buoi;

    ALTER TABLE dbo.KhoaHoc ALTER COLUMN so_buoi SMALLINT NULL;
    ALTER TABLE dbo.KhoaHoc ADD CONSTRAINT CK_KhoaHoc_so_buoi
        CHECK (so_buoi IS NULL OR so_buoi > 0);

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
