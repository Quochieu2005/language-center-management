:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

/*
    Run once in each site database (QLTTNN_Q1, QLTTNN_Q7, QLTTNN_TD).
    AUTH_SESSION_SITE_CODE is the coordinator for this forward-recovery ledger.
    Account rows are deactivated on every site captured when the operation starts;
    the site-specific employee profile and audit history stay at their owning site.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.TaiKhoan', N'U') IS NULL OR OBJECT_ID(N'dbo.CoSo', N'U') IS NULL
    THROW 51141, N'Thiếu dbo.TaiKhoan hoặc dbo.CoSo; hãy cài schema trước.', 1;

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.GiaoDichVoHieuHoaAdminSmall', N'U') IS NULL
    BEGIN
        CREATE TABLE dbo.GiaoDichVoHieuHoaAdminSmall
        (
            ma_giao_dich          UNIQUEIDENTIFIER NOT NULL,
            ma_tai_khoan          VARCHAR(24)      NOT NULL,
            ma_co_so              VARCHAR(10)      NOT NULL,
            ma_admin_big          VARCHAR(24)      NOT NULL,
            phien_ban_ban_dau     BIGINT           NOT NULL,
            site_codes_json       NVARCHAR(MAX)    NOT NULL,
            trang_thai            VARCHAR(20)      NOT NULL
                CONSTRAINT DF_GDVoHieuHoaAdminSmall_trang_thai DEFAULT ('dang_xu_ly'),
            tao_luc_utc           DATETIME2(3)     NOT NULL
                CONSTRAINT DF_GDVoHieuHoaAdminSmall_tao DEFAULT (SYSUTCDATETIME()),
            cap_nhat_luc_utc      DATETIME2(3)     NOT NULL
                CONSTRAINT DF_GDVoHieuHoaAdminSmall_cap_nhat DEFAULT (SYSUTCDATETIME()),
            hoan_tat_luc_utc      DATETIME2(3)     NULL,
            CONSTRAINT PK_GiaoDichVoHieuHoaAdminSmall PRIMARY KEY (ma_giao_dich),
            CONSTRAINT UQ_GDVoHieuHoaAdminSmall_tai_khoan UNIQUE (ma_tai_khoan),
            CONSTRAINT FK_GDVoHieuHoaAdminSmall_TaiKhoan FOREIGN KEY (ma_tai_khoan)
                REFERENCES dbo.TaiKhoan(ma_tai_khoan),
            CONSTRAINT FK_GDVoHieuHoaAdminSmall_CoSo FOREIGN KEY (ma_co_so)
                REFERENCES dbo.CoSo(ma_co_so),
            CONSTRAINT FK_GDVoHieuHoaAdminSmall_AdminBig FOREIGN KEY (ma_admin_big)
                REFERENCES dbo.TaiKhoan(ma_tai_khoan),
            CONSTRAINT CK_GDVoHieuHoaAdminSmall_phien_ban CHECK (phien_ban_ban_dau > 0),
            CONSTRAINT CK_GDVoHieuHoaAdminSmall_site_codes CHECK (ISJSON(site_codes_json) = 1),
            CONSTRAINT CK_GDVoHieuHoaAdminSmall_trang_thai CHECK (trang_thai IN ('dang_xu_ly', 'hoan_tat')),
            CONSTRAINT CK_GDVoHieuHoaAdminSmall_noi_dung CHECK
                ((trang_thai = 'hoan_tat' AND hoan_tat_luc_utc IS NOT NULL)
                 OR (trang_thai = 'dang_xu_ly' AND hoan_tat_luc_utc IS NULL))
        );
    END;

    IF NOT EXISTS
       (SELECT 1 FROM sys.indexes
        WHERE object_id = OBJECT_ID(N'dbo.GiaoDichVoHieuHoaAdminSmall')
          AND name = N'IX_GDVoHieuHoaAdminSmall_trang_thai')
        CREATE INDEX IX_GDVoHieuHoaAdminSmall_trang_thai
            ON dbo.GiaoDichVoHieuHoaAdminSmall (trang_thai, tao_luc_utc)
            INCLUDE (ma_tai_khoan, ma_co_so);

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

SELECT DB_NAME() AS database_da_cap_nhat,
       OBJECT_ID(N'dbo.GiaoDichVoHieuHoaAdminSmall', N'U') AS object_id_giao_dich_vo_hieu_hoa_admin_small;
GO
