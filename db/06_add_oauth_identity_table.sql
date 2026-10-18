:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

/*
    Migration cộng bảng liên kết tài khoản Google/Facebook vào từng CSDL site đã tạo.
    Chạy riêng cho từng site sau khi xác nhận dbo.TaiKhoan đã tồn tại và sao lưu database.
    Không xóa hoặc đổi dữ liệu hiện có. Chạy lại an toàn nếu bảng đã có đúng cấu trúc.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_ID(DB_NAME()) <= 4
BEGIN
    ;THROW 51060, N'Hãy chọn một CSDL site, không chạy trong system database.', 1;
END;

IF OBJECT_ID(N'dbo.TaiKhoan', N'U') IS NULL
BEGIN
    ;THROW 51061, N'Thiếu dbo.TaiKhoan. Hãy tạo schema trước khi thêm liên kết OAuth.', 1;
END;

IF OBJECT_ID(N'dbo.TaiKhoanLienKetOAuth', N'U') IS NULL
BEGIN
    BEGIN TRY
        BEGIN TRANSACTION;

        CREATE TABLE dbo.TaiKhoanLienKetOAuth
        (
            ma_lien_ket       UNIQUEIDENTIFIER NOT NULL,
            ma_tai_khoan      VARCHAR(24)      NOT NULL,
            nha_cung_cap      VARCHAR(16)      NOT NULL,
            provider_subject  NVARCHAR(255)    NOT NULL,
            trang_thai        VARCHAR(20)      NOT NULL CONSTRAINT DF_TaiKhoanLienKetOAuth_trang_thai DEFAULT ('hoat_dong'),
            ngay_lien_ket      DATETIME2(0)     NOT NULL,
            ngay_thu_hoi       DATETIME2(0)     NULL,
            phien_ban          BIGINT           NOT NULL CONSTRAINT DF_TaiKhoanLienKetOAuth_phien_ban DEFAULT (1),
            cap_nhat_luc       DATETIME2(0)     NOT NULL,
            CONSTRAINT PK_TaiKhoanLienKetOAuth PRIMARY KEY (ma_lien_ket),
            CONSTRAINT UQ_TaiKhoanLienKetOAuth_provider_subject UNIQUE (nha_cung_cap, provider_subject),
            CONSTRAINT UQ_TaiKhoanLienKetOAuth_tai_khoan_provider UNIQUE (ma_tai_khoan, nha_cung_cap),
            CONSTRAINT FK_TaiKhoanLienKetOAuth_TaiKhoan FOREIGN KEY (ma_tai_khoan)
                REFERENCES dbo.TaiKhoan(ma_tai_khoan),
            CONSTRAINT CK_TaiKhoanLienKetOAuth_nha_cung_cap CHECK (nha_cung_cap IN ('google', 'facebook')),
            CONSTRAINT CK_TaiKhoanLienKetOAuth_trang_thai CHECK (trang_thai IN ('hoat_dong', 'da_thu_hoi')),
            CONSTRAINT CK_TaiKhoanLienKetOAuth_thu_hoi CHECK
                ((trang_thai = 'hoat_dong' AND ngay_thu_hoi IS NULL) OR
                 (trang_thai = 'da_thu_hoi' AND ngay_thu_hoi IS NOT NULL)),
            CONSTRAINT CK_TaiKhoanLienKetOAuth_phien_ban CHECK (phien_ban > 0)
        );

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;

IF OBJECT_ID(N'dbo.TaiKhoanLienKetOAuth', N'U') IS NOT NULL
BEGIN
    IF
    (
    SELECT COUNT(*)
    FROM sys.columns
    WHERE object_id = OBJECT_ID(N'dbo.TaiKhoanLienKetOAuth')
      AND name IN (N'ma_lien_ket', N'ma_tai_khoan', N'nha_cung_cap', N'provider_subject',
                   N'trang_thai', N'ngay_lien_ket', N'ngay_thu_hoi', N'phien_ban', N'cap_nhat_luc')
    ) <> 9
    BEGIN
        ;THROW 51062, N'Bảng dbo.TaiKhoanLienKetOAuth đã tồn tại nhưng thiếu cột mong đợi; dừng để kiểm tra thủ công.', 1;
    END;

    IF
    (
        SELECT COUNT(*)
        FROM sys.key_constraints
        WHERE parent_object_id = OBJECT_ID(N'dbo.TaiKhoanLienKetOAuth')
          AND name IN (N'PK_TaiKhoanLienKetOAuth', N'UQ_TaiKhoanLienKetOAuth_provider_subject',
                       N'UQ_TaiKhoanLienKetOAuth_tai_khoan_provider')
    ) <> 3
    OR NOT EXISTS
       (SELECT 1 FROM sys.foreign_keys
        WHERE parent_object_id = OBJECT_ID(N'dbo.TaiKhoanLienKetOAuth')
          AND name = N'FK_TaiKhoanLienKetOAuth_TaiKhoan')
    OR
    (
        SELECT COUNT(*)
        FROM sys.check_constraints
        WHERE parent_object_id = OBJECT_ID(N'dbo.TaiKhoanLienKetOAuth')
          AND name IN (N'CK_TaiKhoanLienKetOAuth_nha_cung_cap', N'CK_TaiKhoanLienKetOAuth_trang_thai',
                       N'CK_TaiKhoanLienKetOAuth_thu_hoi', N'CK_TaiKhoanLienKetOAuth_phien_ban')
    ) <> 4
    BEGIN
        ;THROW 51063, N'Bảng dbo.TaiKhoanLienKetOAuth đã tồn tại nhưng thiếu khóa hoặc ràng buộc mong đợi; dừng để kiểm tra thủ công.', 1;
    END;
END;
GO

SELECT DB_NAME() AS database_dang_cap_nhat,
       OBJECT_ID(N'dbo.TaiKhoanLienKetOAuth', N'U') AS object_id_oauth_identity;
GO
