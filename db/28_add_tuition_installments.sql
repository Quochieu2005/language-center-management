:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

/*
    Add site-local scheduled tuition installments and preserve existing balances.
    Run separately against QLTTNN_Q1, QLTTNN_Q7 and QLTTNN_TD.
    Existing tuition rows are backfilled as a single full-payment installment.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_ID(DB_NAME()) <= 4
    THROW 51281, N'Hãy chọn một CSDL site, không chạy trong system database.', 1;

IF OBJECT_ID(N'dbo.HocPhi', N'U') IS NULL
    THROW 51282, N'Thiếu dbo.HocPhi; hãy cài schema trước.', 1;

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.Seq_DH', N'SO') IS NULL
        CREATE SEQUENCE dbo.Seq_DH AS BIGINT START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 999999 NO CYCLE;

    IF OBJECT_ID(N'dbo.DotHocPhi', N'U') IS NULL
    BEGIN
        CREATE TABLE dbo.DotHocPhi
        (
            ma_dot_hoc_phi    VARCHAR(24)    NOT NULL,
            ma_co_so          VARCHAR(10)    NOT NULL,
            ma_hoc_phi        VARCHAR(24)    NOT NULL,
            so_thu_tu         SMALLINT       NOT NULL,
            ngay_den_han      DATE           NOT NULL,
            so_tien_phai_dong DECIMAL(18, 0) NOT NULL,
            so_tien_da_dong   DECIMAL(18, 0) NOT NULL CONSTRAINT DF_DotHocPhi_da_dong DEFAULT (0),
            trang_thai        VARCHAR(20)    NOT NULL CONSTRAINT DF_DotHocPhi_trang_thai DEFAULT ('chua_dong'),
            CONSTRAINT PK_DotHocPhi PRIMARY KEY (ma_dot_hoc_phi),
            CONSTRAINT UQ_DotHocPhi_hoc_phi_thu_tu UNIQUE (ma_hoc_phi, so_thu_tu),
            CONSTRAINT FK_DotHocPhi_HocPhiCungCoSo FOREIGN KEY (ma_hoc_phi, ma_co_so)
                REFERENCES dbo.HocPhi(ma_hoc_phi, ma_co_so),
            CONSTRAINT CK_DotHocPhi_so_thu_tu CHECK (so_thu_tu >= 1),
            CONSTRAINT CK_DotHocPhi_so_tien CHECK
                (so_tien_phai_dong >= 0 AND so_tien_da_dong >= 0 AND so_tien_da_dong <= so_tien_phai_dong),
            CONSTRAINT CK_DotHocPhi_trang_thai CHECK (trang_thai IN ('chua_dong', 'dong_mot_phan', 'da_dong'))
        );
    END;

    IF COL_LENGTH(N'dbo.DotHocPhi', N'ma_dot_hoc_phi') IS NULL
       OR COL_LENGTH(N'dbo.DotHocPhi', N'ma_co_so') IS NULL
       OR COL_LENGTH(N'dbo.DotHocPhi', N'ma_hoc_phi') IS NULL
       OR COL_LENGTH(N'dbo.DotHocPhi', N'so_thu_tu') IS NULL
       OR COL_LENGTH(N'dbo.DotHocPhi', N'ngay_den_han') IS NULL
       OR COL_LENGTH(N'dbo.DotHocPhi', N'so_tien_phai_dong') IS NULL
       OR COL_LENGTH(N'dbo.DotHocPhi', N'so_tien_da_dong') IS NULL
       OR COL_LENGTH(N'dbo.DotHocPhi', N'trang_thai') IS NULL
        THROW 51283, N'Dbo.DotHocPhi đã tồn tại nhưng thiếu cột bắt buộc; dừng để đối soát.', 1;

    IF NOT EXISTS
       (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.DotHocPhi')
        AND name = N'IX_DotHocPhi_site_han')
        CREATE INDEX IX_DotHocPhi_site_han ON dbo.DotHocPhi(ma_co_so, ngay_den_han, trang_thai);

    IF EXISTS
    (
        SELECT 1 FROM dbo.HocPhi
        WHERE so_tien_phai_dong < 0 OR giam_gia < 0 OR so_tien_da_dong < 0
           OR giam_gia > so_tien_phai_dong
           OR so_tien_da_dong > so_tien_phai_dong - giam_gia
    )
        THROW 51284, N'Có khoản HocPhi không hợp lệ; dừng để tránh backfill sai số dư.', 1;

    INSERT INTO dbo.DotHocPhi
        (ma_dot_hoc_phi, ma_co_so, ma_hoc_phi, so_thu_tu, ngay_den_han,
         so_tien_phai_dong, so_tien_da_dong, trang_thai)
    SELECT
        CONCAT(hp.ma_co_so, '-DH-', RIGHT(CONCAT('000000', CONVERT(VARCHAR(6), NEXT VALUE FOR dbo.Seq_DH)), 6)),
        hp.ma_co_so,
        hp.ma_hoc_phi,
        1,
        COALESCE(
            CAST(DATEADD(HOUR, 7, dk.ngay_dang_ky) AS DATE),
            CAST(DATEADD(HOUR, 7, SYSUTCDATETIME()) AS DATE)
        ),
        hp.so_tien_phai_dong - hp.giam_gia,
        hp.so_tien_da_dong,
        CASE
            WHEN hp.so_tien_da_dong >= hp.so_tien_phai_dong - hp.giam_gia THEN 'da_dong'
            WHEN hp.so_tien_da_dong > 0 THEN 'dong_mot_phan'
            ELSE 'chua_dong'
        END
    FROM dbo.HocPhi AS hp
    LEFT JOIN dbo.DangKy AS dk
      ON dk.ma_dang_ky = hp.ma_dang_ky AND dk.ma_co_so = hp.ma_co_so
    WHERE NOT EXISTS
    (
        SELECT 1 FROM dbo.DotHocPhi AS dh
        WHERE dh.ma_hoc_phi = hp.ma_hoc_phi AND dh.ma_co_so = hp.ma_co_so
    );

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

SELECT DB_NAME() AS database_dang_cap_nhat,
       (SELECT COUNT_BIG(*) FROM dbo.HocPhi) AS so_khoan_hoc_phi,
       (SELECT COUNT_BIG(*) FROM dbo.DotHocPhi) AS so_dot_hoc_phi,
       (SELECT COUNT_BIG(*) FROM dbo.HocPhi AS hp
        WHERE NOT EXISTS (SELECT 1 FROM dbo.DotHocPhi AS dh
                          WHERE dh.ma_hoc_phi = hp.ma_hoc_phi AND dh.ma_co_so = hp.ma_co_so))
           AS so_khoan_chua_co_lich;
GO
