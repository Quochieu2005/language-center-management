/*
    Retryable coordinator state for teacher account provisioning/deactivation.
    Run this script once on the database configured by AUTH_SESSION_SITE_CODE
    (normally QLTTNN_Q1), not on every site database.
*/
SET XACT_ABORT ON;
GO

IF OBJECT_ID(N'dbo.TaiKhoan', N'U') IS NULL
   OR OBJECT_ID(N'dbo.CoSo', N'U') IS NULL
   OR OBJECT_ID(N'dbo.PhienDangNhap', N'U') IS NULL
    THROW 51161, N'Thiếu TaiKhoan, CoSo hoặc PhienDangNhap; hãy cài các script trước.', 1;
GO

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.GiaoDichQuanLyGiaoVien', N'U') IS NULL
    BEGIN
        CREATE TABLE dbo.GiaoDichQuanLyGiaoVien
        (
            ma_giao_dich          UNIQUEIDENTIFIER NOT NULL,
            hanh_dong             VARCHAR(20)      NOT NULL,
            ma_tai_khoan          VARCHAR(24)      NOT NULL,
            ma_giao_vien          VARCHAR(24)      NOT NULL,
            ma_co_so              VARCHAR(10)      NOT NULL,
            ma_nguoi_thuc_hien    VARCHAR(24)      NOT NULL,
            phien_ban_ban_dau     BIGINT           NOT NULL,
            site_codes_json       NVARCHAR(MAX)    NOT NULL,
            du_lieu_json          NVARCHAR(MAX)    NOT NULL,
            trang_thai            VARCHAR(20)      NOT NULL
                CONSTRAINT DF_GiaoDichQuanLyGiaoVien_trang_thai DEFAULT ('dang_xu_ly'),
            tao_luc_utc           DATETIME2(3)     NOT NULL
                CONSTRAINT DF_GiaoDichQuanLyGiaoVien_tao DEFAULT (SYSUTCDATETIME()),
            cap_nhat_luc_utc      DATETIME2(3)     NOT NULL
                CONSTRAINT DF_GiaoDichQuanLyGiaoVien_cap_nhat DEFAULT (SYSUTCDATETIME()),
            hoan_tat_luc_utc      DATETIME2(3)     NULL,
            CONSTRAINT PK_GiaoDichQuanLyGiaoVien PRIMARY KEY (ma_giao_dich),
            CONSTRAINT UQ_GiaoDichQuanLyGiaoVien_hanh_dong_tai_khoan UNIQUE (hanh_dong, ma_tai_khoan),
            CONSTRAINT FK_GiaoDichQuanLyGiaoVien_TaiKhoan FOREIGN KEY (ma_tai_khoan)
                REFERENCES dbo.TaiKhoan(ma_tai_khoan),
            CONSTRAINT FK_GiaoDichQuanLyGiaoVien_CoSo FOREIGN KEY (ma_co_so)
                REFERENCES dbo.CoSo(ma_co_so),
            CONSTRAINT FK_GiaoDichQuanLyGiaoVien_NguoiThucHien FOREIGN KEY (ma_nguoi_thuc_hien)
                REFERENCES dbo.TaiKhoan(ma_tai_khoan),
            CONSTRAINT CK_GiaoDichQuanLyGiaoVien_hanh_dong
                CHECK (hanh_dong IN ('tao', 'vo_hieu_hoa')),
            CONSTRAINT CK_GiaoDichQuanLyGiaoVien_phien_ban CHECK (phien_ban_ban_dau > 0),
            CONSTRAINT CK_GiaoDichQuanLyGiaoVien_site_codes CHECK (ISJSON(site_codes_json) = 1),
            CONSTRAINT CK_GiaoDichQuanLyGiaoVien_du_lieu CHECK (ISJSON(du_lieu_json) = 1),
            CONSTRAINT CK_GiaoDichQuanLyGiaoVien_trang_thai
                CHECK (trang_thai IN ('dang_xu_ly', 'hoan_tat')),
            CONSTRAINT CK_GiaoDichQuanLyGiaoVien_hoan_tat CHECK
                ((trang_thai = 'hoan_tat' AND hoan_tat_luc_utc IS NOT NULL)
                 OR (trang_thai = 'dang_xu_ly' AND hoan_tat_luc_utc IS NULL))
        );
    END;

    IF NOT EXISTS
       (SELECT 1 FROM sys.indexes
        WHERE object_id = OBJECT_ID(N'dbo.GiaoDichQuanLyGiaoVien')
          AND name = N'IX_GiaoDichQuanLyGiaoVien_trang_thai')
        CREATE INDEX IX_GiaoDichQuanLyGiaoVien_trang_thai
            ON dbo.GiaoDichQuanLyGiaoVien (trang_thai, tao_luc_utc)
            INCLUDE (hanh_dong, ma_tai_khoan, ma_giao_vien, ma_co_so);

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

SELECT DB_NAME() AS database_da_cap_nhat,
       OBJECT_ID(N'dbo.GiaoDichQuanLyGiaoVien', N'U') AS object_id_giao_dich_quan_ly_giao_vien;
GO
