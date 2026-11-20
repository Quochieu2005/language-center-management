/* Only run on a disposable QLTTNN_TEST* database after migrations 39 and 43. */
SET NOCOUNT ON;
SET XACT_ABORT ON;
IF LEFT(DB_NAME(), 11) <> N'QLTTNN_TEST'
    THROW 51450, N'Chỉ chạy kiểm thử ghi trên database QLTTNN_TEST* dùng riêng.', 1;
DECLARE @site varchar(10) = SUBSTRING(DB_NAME(), 8, 10);
DECLARE @other_site varchar(10) =
    (SELECT TOP (1) ma_co_so FROM dbo.CoSo WHERE ma_co_so <> @site ORDER BY ma_co_so);
IF @other_site IS NULL
    THROW 51451, N'Cần một cơ sở khác tồn tại để phân biệt lỗi FK và CHECK site.', 1;
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints
               WHERE parent_object_id = OBJECT_ID(N'dbo.YeuCauLienHe')
                 AND name = N'CK_YeuCauLienHe_site_local' AND is_disabled = 0 AND is_not_trusted = 0)
    THROW 51452, N'Chưa có CHECK site liên hệ đang bật/trusted.', 1;
DECLARE @rejected bit = 0;
BEGIN TRY
    BEGIN TRANSACTION;
    INSERT dbo.YeuCauLienHe
        (ma_yeu_cau, ma_co_so, ho_ten, email, tieu_de, noi_dung, khoa_chong_lap, payload_hash)
    VALUES ('TEST-CONTACT-BOUNDARY', @other_site, N'Test', 'test@example.invalid',
            N'Test', N'Test', CONVERT(varchar(36), NEWID()), REPLICATE('0', 64));
    ROLLBACK TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    IF ERROR_NUMBER() <> 547 OR ERROR_MESSAGE() NOT LIKE N'%CK_YeuCauLienHe_site_local%'
        THROW;
    SET @rejected = 1;
END CATCH;
IF @rejected <> 1
    THROW 51453, N'Lỗi: DB vẫn cho ghi liên hệ của cơ sở khác.', 1;
SELECT N'PASS: CHECK site từ chối ghi nhầm; dữ liệu kiểm thử đã rollback.' AS result;
