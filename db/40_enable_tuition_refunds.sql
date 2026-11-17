:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

/* Run separately in every site database before deploying the refund API. */
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_ID(DB_NAME()) <= 4
    THROW 51400, N'Hãy chọn một CSDL site, không chạy trong system database.', 1;
IF OBJECT_ID(N'dbo.PhieuThu', N'U') IS NULL
    THROW 51401, N'Thiếu bảng dbo.PhieuThu; hãy tạo schema nền trước.', 1;

BEGIN TRY
    BEGIN TRANSACTION;

    IF COL_LENGTH(N'dbo.PhieuThu', N'ma_phieu_goc') IS NULL
        ALTER TABLE dbo.PhieuThu ADD ma_phieu_goc VARCHAR(24) NULL;
    IF COL_LENGTH(N'dbo.PhieuThu', N'khoa_idempotency') IS NULL
        ALTER TABLE dbo.PhieuThu ADD khoa_idempotency CHAR(36) NULL;

    IF NOT EXISTS (
        SELECT 1 FROM sys.key_constraints
        WHERE parent_object_id = OBJECT_ID(N'dbo.PhieuThu')
          AND name = N'UQ_PhieuThu_ma_phieu_site'
    )
        ALTER TABLE dbo.PhieuThu ADD CONSTRAINT UQ_PhieuThu_ma_phieu_site UNIQUE (ma_phieu, ma_co_so);

    IF NOT EXISTS (
        SELECT 1 FROM sys.foreign_keys
        WHERE parent_object_id = OBJECT_ID(N'dbo.PhieuThu')
          AND name = N'FK_PhieuThu_PhieuGocCungCoSo'
    )
        ALTER TABLE dbo.PhieuThu ADD CONSTRAINT FK_PhieuThu_PhieuGocCungCoSo
            FOREIGN KEY (ma_phieu_goc, ma_co_so) REFERENCES dbo.PhieuThu(ma_phieu, ma_co_so);

    IF NOT EXISTS (
        SELECT 1 FROM sys.indexes
        WHERE object_id = OBJECT_ID(N'dbo.PhieuThu')
          AND name = N'UX_PhieuThu_khoa_idempotency'
    )
        CREATE UNIQUE INDEX UX_PhieuThu_khoa_idempotency
            ON dbo.PhieuThu (khoa_idempotency)
            WHERE khoa_idempotency IS NOT NULL;

    COMMIT TRANSACTION;
    PRINT N'Đã bật tham chiếu phiếu gốc và chống gửi lặp cho nghiệp vụ hoàn tại site này.';
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
