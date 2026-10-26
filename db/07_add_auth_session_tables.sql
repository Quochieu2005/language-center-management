:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

/*
    Add revocable login sessions and privacy-preserving login rate-limit events.
    Run once per existing site database. Enable SQLCMD Mode in SSMS and set
    DatabaseName to QLTTNN_Q1, QLTTNN_Q7, or QLTTNN_TD for each run.
    Fresh databases already receive these tables from 01_create_schema.sql.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_ID(DB_NAME()) <= 4
BEGIN
    ;THROW 51070, N'Hãy chọn một CSDL site, không chạy trong system database.', 1;
END;

IF OBJECT_ID(N'dbo.TaiKhoan', N'U') IS NULL
BEGIN
    ;THROW 51071, N'Thiếu dbo.TaiKhoan. Hãy tạo schema trước khi thêm bảng phiên đăng nhập.', 1;
END;

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.PhienDangNhap', N'U') IS NULL
    BEGIN
        CREATE TABLE dbo.PhienDangNhap
        (
            ma_phien                 UNIQUEIDENTIFIER NOT NULL,
            ma_tai_khoan             VARCHAR(24)      NOT NULL,
            phien_ban_tai_khoan      BIGINT           NOT NULL,
            token_bam                CHAR(64)         NOT NULL,
            tao_luc_utc              DATETIME2(3)     NOT NULL CONSTRAINT DF_PhienDangNhap_tao DEFAULT (SYSUTCDATETIME()),
            hoat_dong_cuoi_utc       DATETIME2(3)     NOT NULL CONSTRAINT DF_PhienDangNhap_hoat_dong DEFAULT (SYSUTCDATETIME()),
            het_han_utc              DATETIME2(3)     NOT NULL,
            thu_hoi_luc_utc          DATETIME2(3)     NULL,
            CONSTRAINT PK_PhienDangNhap PRIMARY KEY (ma_phien),
            CONSTRAINT UQ_PhienDangNhap_token_bam UNIQUE (token_bam),
            CONSTRAINT FK_PhienDangNhap_TaiKhoan FOREIGN KEY (ma_tai_khoan)
                REFERENCES dbo.TaiKhoan(ma_tai_khoan),
            CONSTRAINT CK_PhienDangNhap_phien_ban CHECK (phien_ban_tai_khoan > 0),
            CONSTRAINT CK_PhienDangNhap_thoi_gian CHECK (het_han_utc > hoat_dong_cuoi_utc)
        );
    END;

    IF OBJECT_ID(N'dbo.SuKienDangNhap', N'U') IS NULL
    BEGIN
        CREATE TABLE dbo.SuKienDangNhap
        (
            ma_su_kien       UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_SuKienDangNhap_id DEFAULT (NEWID()),
            dinh_danh_bam    CHAR(64)         NOT NULL,
            ip_bam           CHAR(64)         NOT NULL,
            ket_qua          VARCHAR(20)      NOT NULL,
            thoi_diem_utc    DATETIME2(3)     NOT NULL CONSTRAINT DF_SuKienDangNhap_thoi_diem DEFAULT (SYSUTCDATETIME()),
            CONSTRAINT PK_SuKienDangNhap PRIMARY KEY (ma_su_kien),
            CONSTRAINT CK_SuKienDangNhap_ket_qua CHECK (ket_qua IN ('thanh_cong', 'that_bai'))
        );
    END;

    IF NOT EXISTS
       (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.PhienDangNhap')
          AND name = N'IX_PhienDangNhap_tai_khoan_hieu_luc')
        CREATE INDEX IX_PhienDangNhap_tai_khoan_hieu_luc
            ON dbo.PhienDangNhap (ma_tai_khoan, het_han_utc)
            INCLUDE (thu_hoi_luc_utc, phien_ban_tai_khoan);

    IF NOT EXISTS
       (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.SuKienDangNhap')
          AND name = N'IX_SuKienDangNhap_ip_thoi_diem')
        CREATE INDEX IX_SuKienDangNhap_ip_thoi_diem
            ON dbo.SuKienDangNhap (ip_bam, thoi_diem_utc);

    IF NOT EXISTS
       (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.SuKienDangNhap')
          AND name = N'IX_SuKienDangNhap_dinh_danh_ip_ket_qua_thoi_diem')
        CREATE INDEX IX_SuKienDangNhap_dinh_danh_ip_ket_qua_thoi_diem
            ON dbo.SuKienDangNhap (dinh_danh_bam, ip_bam, ket_qua, thoi_diem_utc);

    IF OBJECT_ID(N'dbo.TR_SuKienDangNhap_AppendOnly', N'TR') IS NULL
    EXEC sys.sp_executesql N'
        CREATE TRIGGER dbo.TR_SuKienDangNhap_AppendOnly
        ON dbo.SuKienDangNhap
        INSTEAD OF UPDATE, DELETE
        AS
        BEGIN
            SET NOCOUNT ON;
            ;THROW 51072, ''SuKienDangNhap chỉ được thêm mới.'', 1;
        END;';

    IF (SELECT COUNT(*) FROM sys.columns WHERE object_id = OBJECT_ID(N'dbo.PhienDangNhap')
        AND name IN (N'ma_phien', N'ma_tai_khoan', N'phien_ban_tai_khoan', N'token_bam',
                     N'tao_luc_utc', N'hoat_dong_cuoi_utc', N'het_han_utc', N'thu_hoi_luc_utc')) <> 8
       OR (SELECT COUNT(*) FROM sys.columns WHERE object_id = OBJECT_ID(N'dbo.SuKienDangNhap')
        AND name IN (N'ma_su_kien', N'dinh_danh_bam', N'ip_bam', N'ket_qua', N'thoi_diem_utc')) <> 5
    BEGIN
        ;THROW 51073, N'Bảng đăng nhập đã tồn tại nhưng thiếu cột mong đợi; dừng để kiểm tra thủ công.', 1;
    END;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

SELECT DB_NAME() AS database_dang_cap_nhat,
       OBJECT_ID(N'dbo.PhienDangNhap', N'U') AS object_id_phien_dang_nhap,
       OBJECT_ID(N'dbo.SuKienDangNhap', N'U') AS object_id_su_kien_dang_nhap;
GO
