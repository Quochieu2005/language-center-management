:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

/*
    Chạy riêng trên từng CSDL site QLTTNN_Q1, QLTTNN_Q7 và QLTTNN_TD.
    Yêu cầu đã gửi được lưu tại đúng site người gửi chọn; không tạo DB trung tâm.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_ID(DB_NAME()) <= 4
    THROW 51390, N'Hãy chọn một CSDL site, không chạy trong system database.', 1;
IF OBJECT_ID(N'dbo.CoSo', N'U') IS NULL OR OBJECT_ID(N'dbo.Logs', N'U') IS NULL
    THROW 51391, N'Thiếu bảng CoSo hoặc Logs; hãy chạy schema/migration nền trước.', 1;
IF OBJECT_ID(N'dbo.YeuCauLienHe', N'U') IS NOT NULL
   AND OBJECT_ID(N'dbo.Seq_LH', N'SO') IS NOT NULL
BEGIN
    PRINT N'Bảng YeuCauLienHe và sequence Seq_LH đã tồn tại; không thay đổi dữ liệu.';
    RETURN;
END;
IF OBJECT_ID(N'dbo.YeuCauLienHe', N'U') IS NOT NULL
    THROW 51392, N'Bảng YeuCauLienHe đã có nhưng thiếu Seq_LH; cần đối soát trước khi chạy.', 1;

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.Seq_LH', N'SO') IS NULL
        EXEC(N'CREATE SEQUENCE dbo.Seq_LH AS BIGINT START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 999999 NO CYCLE;');

    CREATE TABLE dbo.YeuCauLienHe
    (
        ma_yeu_cau             VARCHAR(24)    NOT NULL,
        ma_co_so               VARCHAR(10)    NOT NULL,
        ho_ten                 NVARCHAR(120)  NOT NULL,
        email                  NVARCHAR(254) NOT NULL,
        so_dien_thoai          VARCHAR(20)    NULL,
        tieu_de                NVARCHAR(160)  NOT NULL,
        noi_dung               NVARCHAR(MAX)  NOT NULL,
        trang_thai             VARCHAR(20)    NOT NULL CONSTRAINT DF_YeuCauLienHe_trang_thai DEFAULT ('cho_xu_ly'),
        khoa_chong_lap          VARCHAR(128)   NOT NULL,
        payload_hash           CHAR(64)       NOT NULL,
        noi_dung_phan_hoi      NVARCHAR(MAX)  NULL,
        ma_nguoi_phan_hoi      VARCHAR(24)    NULL,
        phan_hoi_luc_utc       DATETIME2(3)   NULL,
        tao_luc_utc            DATETIME2(3)   NOT NULL CONSTRAINT DF_YeuCauLienHe_tao_luc DEFAULT (SYSUTCDATETIME()),
        cap_nhat_luc_utc       DATETIME2(3)   NOT NULL CONSTRAINT DF_YeuCauLienHe_cap_nhat_luc DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT PK_YeuCauLienHe PRIMARY KEY (ma_yeu_cau),
        CONSTRAINT UQ_YeuCauLienHe_site_key UNIQUE (ma_co_so, khoa_chong_lap),
        CONSTRAINT FK_YeuCauLienHe_CoSo FOREIGN KEY (ma_co_so) REFERENCES dbo.CoSo(ma_co_so),
        CONSTRAINT CK_YeuCauLienHe_trang_thai CHECK (trang_thai IN ('cho_xu_ly', 'da_phan_hoi')),
        CONSTRAINT CK_YeuCauLienHe_ho_ten CHECK (LEN(LTRIM(RTRIM(ho_ten))) BETWEEN 1 AND 120),
        CONSTRAINT CK_YeuCauLienHe_email CHECK (LEN(LTRIM(RTRIM(email))) BETWEEN 3 AND 254),
        CONSTRAINT CK_YeuCauLienHe_tieu_de CHECK (LEN(LTRIM(RTRIM(tieu_de))) BETWEEN 1 AND 160),
        CONSTRAINT CK_YeuCauLienHe_noi_dung CHECK (LEN(LTRIM(RTRIM(noi_dung))) BETWEEN 1 AND 5000),
        CONSTRAINT CK_YeuCauLienHe_phan_hoi CHECK
        (
            (trang_thai = 'cho_xu_ly' AND noi_dung_phan_hoi IS NULL
                AND ma_nguoi_phan_hoi IS NULL AND phan_hoi_luc_utc IS NULL)
            OR
            (trang_thai = 'da_phan_hoi' AND noi_dung_phan_hoi IS NOT NULL
                AND LEN(LTRIM(RTRIM(noi_dung_phan_hoi))) BETWEEN 1 AND 5000
                AND ma_nguoi_phan_hoi IS NOT NULL AND phan_hoi_luc_utc IS NOT NULL)
        )
    );

    CREATE INDEX IX_YeuCauLienHe_site_status_created
        ON dbo.YeuCauLienHe (ma_co_so, trang_thai, tao_luc_utc DESC, ma_yeu_cau DESC)
        INCLUDE (ho_ten, email, tieu_de, phan_hoi_luc_utc);

    COMMIT TRANSACTION;
    PRINT N'Đã tạo hộp thư liên hệ tại CSDL site hiện chọn.';
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
