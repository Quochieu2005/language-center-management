/*
    Run once in the database configured by AUTH_SESSION_SITE_CODE.
    This is coordinator state for retrying replicated TaiKhoan status changes;
    it is not a central business-data database and must not be copied to every site.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.TaiKhoan', N'U') IS NULL
   OR OBJECT_ID(N'dbo.CoSo', N'U') IS NULL
   OR OBJECT_ID(N'dbo.PhienDangNhap', N'U') IS NULL
    THROW 51171, N'Thiếu TaiKhoan, CoSo hoặc PhienDangNhap; hãy cài các script trước.', 1;

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.GiaoDichTrangThaiTaiKhoan', N'U') IS NULL
    BEGIN
        CREATE TABLE dbo.GiaoDichTrangThaiTaiKhoan
        (
            ma_giao_dich          UNIQUEIDENTIFIER NOT NULL,
            ma_tai_khoan          VARCHAR(24)      NOT NULL,
            ma_nguoi_thuc_hien    VARCHAR(24)      NOT NULL,
            ma_co_so              VARCHAR(10)      NOT NULL,
            vai_tro_muc_tieu      VARCHAR(20)      NOT NULL,
            trang_thai_cu         VARCHAR(20)      NOT NULL,
            trang_thai_moi        VARCHAR(20)      NOT NULL,
            phien_ban_ban_dau     BIGINT           NOT NULL,
            site_codes_json       NVARCHAR(MAX)    NOT NULL,
            trang_thai            VARCHAR(20)      NOT NULL
                CONSTRAINT DF_GDTrangThaiTaiKhoan_trang_thai DEFAULT ('dang_xu_ly'),
            tao_luc_utc           DATETIME2(3)     NOT NULL
                CONSTRAINT DF_GDTrangThaiTaiKhoan_tao DEFAULT (SYSUTCDATETIME()),
            cap_nhat_luc_utc      DATETIME2(3)     NOT NULL
                CONSTRAINT DF_GDTrangThaiTaiKhoan_cap_nhat DEFAULT (SYSUTCDATETIME()),
            hoan_tat_luc_utc      DATETIME2(3)     NULL,
            CONSTRAINT PK_GiaoDichTrangThaiTaiKhoan PRIMARY KEY (ma_giao_dich),
            CONSTRAINT FK_GDTrangThaiTaiKhoan_TaiKhoan FOREIGN KEY (ma_tai_khoan)
                REFERENCES dbo.TaiKhoan(ma_tai_khoan),
            CONSTRAINT FK_GDTrangThaiTaiKhoan_NguoiThucHien FOREIGN KEY (ma_nguoi_thuc_hien)
                REFERENCES dbo.TaiKhoan(ma_tai_khoan),
            CONSTRAINT FK_GDTrangThaiTaiKhoan_CoSo FOREIGN KEY (ma_co_so)
                REFERENCES dbo.CoSo(ma_co_so),
            CONSTRAINT CK_GDTrangThaiTaiKhoan_vai_tro
                CHECK (vai_tro_muc_tieu IN ('admin_small', 'giao_vien')),
            CONSTRAINT CK_GDTrangThaiTaiKhoan_trang_thai_cu
                CHECK (trang_thai_cu IN ('hoat_dong', 'vo_hieu', 'khoa')),
            CONSTRAINT CK_GDTrangThaiTaiKhoan_trang_thai_moi
                CHECK (trang_thai_moi IN ('hoat_dong', 'vo_hieu') AND trang_thai_moi <> trang_thai_cu),
            CONSTRAINT CK_GDTrangThaiTaiKhoan_phien_ban CHECK (phien_ban_ban_dau > 0),
            CONSTRAINT CK_GDTrangThaiTaiKhoan_site_codes CHECK (ISJSON(site_codes_json) = 1),
            CONSTRAINT CK_GDTrangThaiTaiKhoan_trang_thai
                CHECK (trang_thai IN ('dang_xu_ly', 'hoan_tat')),
            CONSTRAINT CK_GDTrangThaiTaiKhoan_hoan_tat CHECK
                ((trang_thai = 'hoan_tat' AND hoan_tat_luc_utc IS NOT NULL)
                 OR (trang_thai = 'dang_xu_ly' AND hoan_tat_luc_utc IS NULL))
        );
    END;

    IF NOT EXISTS
       (SELECT 1 FROM sys.indexes
        WHERE object_id = OBJECT_ID(N'dbo.GiaoDichTrangThaiTaiKhoan')
          AND name = N'UX_GDTrangThaiTaiKhoan_dang_xu_ly')
        CREATE UNIQUE INDEX UX_GDTrangThaiTaiKhoan_dang_xu_ly
            ON dbo.GiaoDichTrangThaiTaiKhoan (ma_tai_khoan)
            WHERE trang_thai = 'dang_xu_ly';

    IF NOT EXISTS
       (SELECT 1 FROM sys.indexes
        WHERE object_id = OBJECT_ID(N'dbo.GiaoDichTrangThaiTaiKhoan')
          AND name = N'IX_GDTrangThaiTaiKhoan_trang_thai')
        CREATE INDEX IX_GDTrangThaiTaiKhoan_trang_thai
            ON dbo.GiaoDichTrangThaiTaiKhoan (trang_thai, tao_luc_utc)
            INCLUDE (ma_tai_khoan, ma_co_so, trang_thai_moi);

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

SELECT DB_NAME() AS coordinator_database,
       OBJECT_ID(N'dbo.GiaoDichTrangThaiTaiKhoan', N'U') AS object_id_giao_dich_trang_thai_tai_khoan;
GO
