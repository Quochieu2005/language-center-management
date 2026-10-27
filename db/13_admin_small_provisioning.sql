:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

/*
    Run in SQLCMD Mode once on each site database (QLTTNN_Q1, QLTTNN_Q7,
    QLTTNN_TD). The Coordinator stores the progress ledger; the other copies
    keep the same schema so AUTH_SESSION_SITE_CODE can point to any active site.
    This ledger stores account/profile identifiers and state only. It never
    stores the temporary password in plaintext or duplicates its hash.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.TaiKhoan', N'U') IS NULL OR OBJECT_ID(N'dbo.CoSo', N'U') IS NULL
    THROW 51131, N'Thiếu dbo.TaiKhoan hoặc dbo.CoSo; hãy cài schema trước.', 1;

IF COL_LENGTH(N'dbo.TaiKhoan', N'bat_buoc_doi_mat_khau') IS NULL
    THROW 51132, N'Thiếu cột dbo.TaiKhoan.bat_buoc_doi_mat_khau.', 1;

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.GiaoDichTaoAdminSmall', N'U') IS NULL
    BEGIN
        CREATE TABLE dbo.GiaoDichTaoAdminSmall
        (
            ma_giao_dich      UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_GiaoDichTaoAdminSmall_id DEFAULT (NEWID()),
            ma_tai_khoan      VARCHAR(24)      NOT NULL,
            ma_nhan_vien      VARCHAR(24)      NOT NULL,
            ma_co_so          VARCHAR(10)      NOT NULL,
            ho_ten            NVARCHAR(150)    NOT NULL,
            ma_admin_big      VARCHAR(24)      NOT NULL,
            trang_thai        VARCHAR(20)      NOT NULL CONSTRAINT DF_GiaoDichTaoAdminSmall_trang_thai DEFAULT ('dang_xu_ly'),
            email_da_gui      BIT              NOT NULL CONSTRAINT DF_GiaoDichTaoAdminSmall_email_da_gui DEFAULT (0),
            tao_luc_utc       DATETIME2(3)     NOT NULL CONSTRAINT DF_GiaoDichTaoAdminSmall_tao DEFAULT (SYSUTCDATETIME()),
            cap_nhat_luc_utc  DATETIME2(3)     NOT NULL CONSTRAINT DF_GiaoDichTaoAdminSmall_cap_nhat DEFAULT (SYSUTCDATETIME()),
            hoan_tat_luc_utc  DATETIME2(3)     NULL,
            CONSTRAINT PK_GiaoDichTaoAdminSmall PRIMARY KEY (ma_giao_dich),
            CONSTRAINT UQ_GiaoDichTaoAdminSmall_tai_khoan UNIQUE (ma_tai_khoan),
            CONSTRAINT FK_GiaoDichTaoAdminSmall_TaiKhoan FOREIGN KEY (ma_tai_khoan)
                REFERENCES dbo.TaiKhoan(ma_tai_khoan),
            CONSTRAINT FK_GiaoDichTaoAdminSmall_CoSo FOREIGN KEY (ma_co_so)
                REFERENCES dbo.CoSo(ma_co_so),
            CONSTRAINT FK_GiaoDichTaoAdminSmall_AdminBig FOREIGN KEY (ma_admin_big)
                REFERENCES dbo.TaiKhoan(ma_tai_khoan),
            CONSTRAINT CK_GiaoDichTaoAdminSmall_trang_thai
                CHECK (trang_thai IN ('dang_xu_ly', 'cho_gui_email', 'hoan_tat')),
            CONSTRAINT CK_GiaoDichTaoAdminSmall_noi_dung CHECK
                ((trang_thai = 'hoan_tat' AND hoan_tat_luc_utc IS NOT NULL)
                 OR (trang_thai <> 'hoan_tat' AND hoan_tat_luc_utc IS NULL))
        );
    END;

    IF NOT EXISTS
       (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.GiaoDichTaoAdminSmall')
          AND name = N'IX_GiaoDichTaoAdminSmall_trang_thai')
        CREATE INDEX IX_GiaoDichTaoAdminSmall_trang_thai
            ON dbo.GiaoDichTaoAdminSmall (trang_thai, tao_luc_utc)
            INCLUDE (ma_tai_khoan, ma_nhan_vien, ma_co_so);

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

SELECT DB_NAME() AS database_da_cap_nhat,
       OBJECT_ID(N'dbo.GiaoDichTaoAdminSmall', N'U') AS object_id_giao_dich_tao_admin_small;
GO
