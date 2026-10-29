:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

/*
    Add 2-minute admin password-reset OTP state and resumable replica updates.
    Run once on each active site database. The coordinator uses only the DB
    selected by AUTH_SESSION_SITE_CODE; every site still keeps its own DB.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_ID(DB_NAME()) <= 4
BEGIN
    ;THROW 51120, N'Hãy chọn một CSDL site, không chạy trong system database.', 1;
END;

IF OBJECT_ID(N'dbo.TaiKhoan', N'U') IS NULL
   OR OBJECT_ID(N'dbo.TokenDatLaiMatKhau', N'U') IS NULL
BEGIN
    ;THROW 51121, N'Thiếu dbo.TaiKhoan hoặc dbo.TokenDatLaiMatKhau. Hãy tạo schema trước.', 1;
END;

BEGIN TRY
    BEGIN TRANSACTION;

    IF COL_LENGTH(N'dbo.TokenDatLaiMatKhau', N'so_lan_sai') IS NULL
        EXEC sys.sp_executesql N'ALTER TABLE dbo.TokenDatLaiMatKhau
            ADD so_lan_sai TINYINT NOT NULL
                CONSTRAINT DF_Token_so_lan_sai DEFAULT (0) WITH VALUES;';

    IF NOT EXISTS
       (SELECT 1 FROM sys.check_constraints
        WHERE parent_object_id = OBJECT_ID(N'dbo.TokenDatLaiMatKhau')
          AND name = N'CK_TokenDatLaiMatKhau_so_lan_sai')
        EXEC sys.sp_executesql N'ALTER TABLE dbo.TokenDatLaiMatKhau WITH CHECK
            ADD CONSTRAINT CK_TokenDatLaiMatKhau_so_lan_sai CHECK (so_lan_sai <= 5);';

    IF EXISTS
       (SELECT 1 FROM sys.columns
        WHERE object_id = OBJECT_ID(N'dbo.TokenDatLaiMatKhau')
          AND name IN (N'ngay_tao', N'het_han') AND scale < 3)
    BEGIN
        IF EXISTS (SELECT 1 FROM sys.check_constraints
                   WHERE parent_object_id = OBJECT_ID(N'dbo.TokenDatLaiMatKhau')
                     AND name = N'CK_TokenDatLaiMatKhau_han')
            ALTER TABLE dbo.TokenDatLaiMatKhau DROP CONSTRAINT CK_TokenDatLaiMatKhau_han;
        ALTER TABLE dbo.TokenDatLaiMatKhau ALTER COLUMN ngay_tao DATETIME2(3) NOT NULL;
        ALTER TABLE dbo.TokenDatLaiMatKhau ALTER COLUMN het_han DATETIME2(3) NOT NULL;
        IF NOT EXISTS (SELECT 1 FROM sys.check_constraints
                       WHERE parent_object_id = OBJECT_ID(N'dbo.TokenDatLaiMatKhau')
                         AND name = N'CK_TokenDatLaiMatKhau_han')
            ALTER TABLE dbo.TokenDatLaiMatKhau WITH CHECK
                ADD CONSTRAINT CK_TokenDatLaiMatKhau_han CHECK (het_han > ngay_tao);
    END;

    IF OBJECT_ID(N'dbo.SuKienQuenMatKhau', N'U') IS NULL
    BEGIN
        CREATE TABLE dbo.SuKienQuenMatKhau
        (
            ma_su_kien       UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_SuKienQuenMatKhau_id DEFAULT (NEWID()),
            dinh_danh_bam    CHAR(64)         NOT NULL,
            ip_bam           CHAR(64)         NOT NULL,
            ma_token         VARCHAR(30)      NULL,
            loai_su_kien     VARCHAR(20)      NOT NULL,
            thoi_diem_utc    DATETIME2(3)     NOT NULL CONSTRAINT DF_SuKienQuenMatKhau_thoi_diem DEFAULT (SYSUTCDATETIME()),
            CONSTRAINT PK_SuKienQuenMatKhau PRIMARY KEY (ma_su_kien),
            CONSTRAINT CK_SuKienQuenMatKhau_loai CHECK (loai_su_kien IN ('yeu_cau', 'otp_sai', 'dat_lai'))
        );
    END;

    IF NOT EXISTS
       (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.SuKienQuenMatKhau')
          AND name = N'IX_SuKienQuenMatKhau_ip_thoi_diem')
        CREATE INDEX IX_SuKienQuenMatKhau_ip_thoi_diem
            ON dbo.SuKienQuenMatKhau (ip_bam, loai_su_kien, thoi_diem_utc);

    IF NOT EXISTS
       (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.SuKienQuenMatKhau')
          AND name = N'IX_SuKienQuenMatKhau_dinh_danh_ip_thoi_diem')
        CREATE INDEX IX_SuKienQuenMatKhau_dinh_danh_ip_thoi_diem
            ON dbo.SuKienQuenMatKhau (dinh_danh_bam, ip_bam, loai_su_kien, thoi_diem_utc);

    IF NOT EXISTS
       (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.SuKienQuenMatKhau')
          AND name = N'IX_SuKienQuenMatKhau_token')
        CREATE INDEX IX_SuKienQuenMatKhau_token
            ON dbo.SuKienQuenMatKhau (ma_token, loai_su_kien, thoi_diem_utc)
            WHERE ma_token IS NOT NULL;

    IF OBJECT_ID(N'dbo.TR_SuKienQuenMatKhau_AppendOnly', N'TR') IS NULL
        EXEC sys.sp_executesql N'
            CREATE TRIGGER dbo.TR_SuKienQuenMatKhau_AppendOnly
            ON dbo.SuKienQuenMatKhau
            INSTEAD OF UPDATE, DELETE
            AS
            BEGIN
                SET NOCOUNT ON;
                ;THROW 51122, ''SuKienQuenMatKhau chỉ được thêm mới.'', 1;
            END;';

    IF OBJECT_ID(N'dbo.GiaoDichDatLaiMatKhau', N'U') IS NULL
    BEGIN
        CREATE TABLE dbo.GiaoDichDatLaiMatKhau
        (
            ma_giao_dich       UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_GiaoDichDatLaiMatKhau_id DEFAULT (NEWID()),
            ma_tai_khoan       VARCHAR(24)      NOT NULL,
            mat_khau_moi_bam   NVARCHAR(255)    NULL,
            trang_thai         VARCHAR(20)      NOT NULL CONSTRAINT DF_GiaoDichDatLaiMatKhau_trang_thai DEFAULT ('dang_xu_ly'),
            tao_luc_utc        DATETIME2(3)     NOT NULL CONSTRAINT DF_GiaoDichDatLaiMatKhau_tao DEFAULT (SYSUTCDATETIME()),
            cap_nhat_luc_utc   DATETIME2(3)     NOT NULL CONSTRAINT DF_GiaoDichDatLaiMatKhau_cap_nhat DEFAULT (SYSUTCDATETIME()),
            hoan_tat_luc_utc   DATETIME2(3)     NULL,
            CONSTRAINT PK_GiaoDichDatLaiMatKhau PRIMARY KEY (ma_giao_dich),
            CONSTRAINT FK_GiaoDichDatLaiMatKhau_TaiKhoan FOREIGN KEY (ma_tai_khoan)
                REFERENCES dbo.TaiKhoan(ma_tai_khoan),
            CONSTRAINT CK_GiaoDichDatLaiMatKhau_trang_thai CHECK (trang_thai IN ('dang_xu_ly', 'hoan_tat')),
            CONSTRAINT CK_GiaoDichDatLaiMatKhau_noi_dung CHECK
                ((trang_thai = 'dang_xu_ly' AND mat_khau_moi_bam IS NOT NULL AND hoan_tat_luc_utc IS NULL)
                 OR (trang_thai = 'hoan_tat' AND mat_khau_moi_bam IS NULL AND hoan_tat_luc_utc IS NOT NULL))
        );
    END;

    IF NOT EXISTS
       (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.GiaoDichDatLaiMatKhau')
          AND name = N'UX_GiaoDichDatLaiMatKhau_dang_xu_ly')
        CREATE UNIQUE INDEX UX_GiaoDichDatLaiMatKhau_dang_xu_ly
            ON dbo.GiaoDichDatLaiMatKhau (ma_tai_khoan)
            WHERE trang_thai = 'dang_xu_ly';

    IF NOT EXISTS
       (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.GiaoDichDatLaiMatKhau')
          AND name = N'IX_GiaoDichDatLaiMatKhau_trang_thai')
        CREATE INDEX IX_GiaoDichDatLaiMatKhau_trang_thai
            ON dbo.GiaoDichDatLaiMatKhau (trang_thai, tao_luc_utc)
            INCLUDE (ma_tai_khoan);

    IF (SELECT COUNT(*) FROM sys.columns
        WHERE object_id = OBJECT_ID(N'dbo.TokenDatLaiMatKhau')
          AND name IN (N'so_lan_sai')) <> 1
       OR OBJECT_ID(N'dbo.SuKienQuenMatKhau', N'U') IS NULL
       OR OBJECT_ID(N'dbo.GiaoDichDatLaiMatKhau', N'U') IS NULL
    BEGIN
        ;THROW 51123, N'Không tạo đủ cấu trúc OTP đặt lại mật khẩu.', 1;
    END;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

SELECT DB_NAME() AS database_da_cap_nhat,
       COL_LENGTH(N'dbo.TokenDatLaiMatKhau', N'so_lan_sai') AS cot_so_lan_sai,
       OBJECT_ID(N'dbo.SuKienQuenMatKhau', N'U') AS bang_su_kien_otp,
       OBJECT_ID(N'dbo.GiaoDichDatLaiMatKhau', N'U') AS bang_dieu_phoi_dat_lai_mat_khau;
GO
