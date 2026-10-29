:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

/*
    Run once in each site database (QLTTNN_Q1, QLTTNN_Q7, QLTTNN_TD).
    The API uses the AUTH_SESSION_SITE_CODE database as the forward-recovery
    coordinator. TaiKhoan remains a separate replica at every site.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.TaiKhoan', N'U') IS NULL OR OBJECT_ID(N'dbo.CoSo', N'U') IS NULL
    THROW 51151, N'Thiếu dbo.TaiKhoan hoặc dbo.CoSo; hãy cài schema trước.', 1;

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.GiaoDichCapNhatAdminBig', N'U') IS NULL
    BEGIN
        CREATE TABLE dbo.GiaoDichCapNhatAdminBig
        (
            ma_giao_dich       UNIQUEIDENTIFIER NOT NULL,
            ma_admin_big       VARCHAR(24)      NOT NULL,
            site_codes_json    NVARCHAR(MAX)    NOT NULL,
            gia_tri_cu_json    NVARCHAR(MAX)    NULL,
            gia_tri_moi_json   NVARCHAR(MAX)    NULL,
            trang_thai         VARCHAR(20)      NOT NULL
                CONSTRAINT DF_GDCapNhatAdminBig_trang_thai DEFAULT ('dang_xu_ly'),
            tao_luc_utc        DATETIME2(3)     NOT NULL
                CONSTRAINT DF_GDCapNhatAdminBig_tao DEFAULT (SYSUTCDATETIME()),
            cap_nhat_luc_utc   DATETIME2(3)     NOT NULL
                CONSTRAINT DF_GDCapNhatAdminBig_cap_nhat DEFAULT (SYSUTCDATETIME()),
            hoan_tat_luc_utc   DATETIME2(3)     NULL,
            CONSTRAINT PK_GiaoDichCapNhatAdminBig PRIMARY KEY (ma_giao_dich),
            CONSTRAINT FK_GDCapNhatAdminBig_TaiKhoan FOREIGN KEY (ma_admin_big)
                REFERENCES dbo.TaiKhoan(ma_tai_khoan),
            CONSTRAINT CK_GDCapNhatAdminBig_site_codes CHECK (ISJSON(site_codes_json) = 1),
            CONSTRAINT CK_GDCapNhatAdminBig_trang_thai CHECK (trang_thai IN ('dang_xu_ly', 'hoan_tat')),
            CONSTRAINT CK_GDCapNhatAdminBig_noi_dung CHECK
                ((trang_thai = 'dang_xu_ly'
                  AND gia_tri_cu_json IS NOT NULL AND ISJSON(gia_tri_cu_json) = 1
                  AND gia_tri_moi_json IS NOT NULL AND ISJSON(gia_tri_moi_json) = 1
                  AND hoan_tat_luc_utc IS NULL)
                 OR (trang_thai = 'hoan_tat'
                  AND gia_tri_cu_json IS NULL AND gia_tri_moi_json IS NULL
                  AND hoan_tat_luc_utc IS NOT NULL))
        );
    END;

    IF NOT EXISTS
       (SELECT 1 FROM sys.indexes
        WHERE object_id = OBJECT_ID(N'dbo.GiaoDichCapNhatAdminBig')
          AND name = N'UX_GDCapNhatAdminBig_dang_xu_ly')
        CREATE UNIQUE INDEX UX_GDCapNhatAdminBig_dang_xu_ly
            ON dbo.GiaoDichCapNhatAdminBig (ma_admin_big)
            WHERE trang_thai = 'dang_xu_ly';

    IF NOT EXISTS
       (SELECT 1 FROM sys.indexes
        WHERE object_id = OBJECT_ID(N'dbo.GiaoDichCapNhatAdminBig')
          AND name = N'IX_GDCapNhatAdminBig_trang_thai')
        CREATE INDEX IX_GDCapNhatAdminBig_trang_thai
            ON dbo.GiaoDichCapNhatAdminBig (trang_thai, tao_luc_utc)
            INCLUDE (ma_admin_big);

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

SELECT DB_NAME() AS database_da_cap_nhat,
       OBJECT_ID(N'dbo.GiaoDichCapNhatAdminBig', N'U') AS object_id_giao_dich_cap_nhat_admin_big;
GO
