/*
    Run once in AUTH_SESSION_SITE_CODE only, after the student account coordinator
    schema has been installed. This is retry state, not consolidated student data.
    A row exists only while a hard delete is incomplete and is removed on success.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.TaiKhoan', N'U') IS NULL OR OBJECT_ID(N'dbo.CoSo', N'U') IS NULL
    THROW 51220, N'Hãy cài schema site trước khi tạo Coordinator xóa học viên.', 1;
GO

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.GiaoDichXoaHocVien', N'U') IS NULL
    BEGIN
        CREATE TABLE dbo.GiaoDichXoaHocVien
        (
            ma_giao_dich             UNIQUEIDENTIFIER NOT NULL,
            slug_hoc_vien            VARCHAR(160)     NOT NULL,
            ma_hoc_vien              VARCHAR(24)      NOT NULL,
            ma_tai_khoan             VARCHAR(24)      NULL,
            ma_co_so_yeu_cau         VARCHAR(10)      NOT NULL,
            ma_tai_khoan_thuc_hien   VARCHAR(24)      NOT NULL,
            vai_tro_thuc_hien        VARCHAR(20)      NOT NULL,
            ma_giao_vien_thuc_hien   VARCHAR(24)      NULL,
            site_codes_json          NVARCHAR(MAX)    NOT NULL,
            site_completed_json      NVARCHAR(MAX)    NOT NULL CONSTRAINT DF_GDXoaHocVien_done DEFAULT (N'[]'),
            profile_slugs_json       NVARCHAR(MAX)    NOT NULL,
            identifiers_json         NVARCHAR(MAX)    NOT NULL,
            tao_luc_utc              DATETIME2(3)     NOT NULL CONSTRAINT DF_GDXoaHocVien_tao DEFAULT (SYSUTCDATETIME()),
            cap_nhat_luc_utc         DATETIME2(3)     NOT NULL CONSTRAINT DF_GDXoaHocVien_cap_nhat DEFAULT (SYSUTCDATETIME()),
            CONSTRAINT PK_GiaoDichXoaHocVien PRIMARY KEY (ma_giao_dich),
            CONSTRAINT UQ_GiaoDichXoaHocVien_slug UNIQUE (slug_hoc_vien),
            CONSTRAINT CK_GDXoaHocVien_role CHECK (vai_tro_thuc_hien IN ('admin_big', 'admin_small', 'giao_vien')),
            CONSTRAINT CK_GDXoaHocVien_json CHECK
                (ISJSON(site_codes_json) = 1 AND ISJSON(site_completed_json) = 1
                 AND ISJSON(profile_slugs_json) = 1 AND ISJSON(identifiers_json) = 1)
        );

        CREATE INDEX IX_GDXoaHocVien_updated
            ON dbo.GiaoDichXoaHocVien (cap_nhat_luc_utc)
            INCLUDE (slug_hoc_vien, ma_hoc_vien, ma_co_so_yeu_cau);
    END;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

SELECT DB_NAME() AS coordinator_database,
       OBJECT_ID(N'dbo.GiaoDichXoaHocVien', N'U') AS object_id_giao_dich_xoa_hoc_vien;
GO
