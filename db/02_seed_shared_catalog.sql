:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

/* Chạy riêng trên từng site. Dữ liệu trong file này phải giống nhau ở cả ba CSDL. */
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_ID(DB_NAME()) <= 4
BEGIN
    ;THROW 51010, N'Hãy chọn một CSDL site, không chạy trong system database.', 1;
END;

IF OBJECT_ID(N'dbo.CoSo', N'U') IS NULL OR OBJECT_ID(N'dbo.MonHoc', N'U') IS NULL OR OBJECT_ID(N'dbo.KhoaHoc', N'U') IS NULL
BEGIN
    ;THROW 51011, N'Chưa tạo schema. Hãy chạy 01_create_schema.sql trước.', 1;
END;

BEGIN TRY
    BEGIN TRANSACTION;

    IF NOT EXISTS (SELECT 1 FROM dbo.CoSo WHERE ma_co_so = 'Q1')
        INSERT dbo.CoSo (ma_co_so, ten_co_so, trang_thai) VALUES ('Q1', N'Cơ sở Quận 1', 'hoat_dong');

    IF NOT EXISTS (SELECT 1 FROM dbo.CoSo WHERE ma_co_so = 'Q7')
        INSERT dbo.CoSo (ma_co_so, ten_co_so, trang_thai) VALUES ('Q7', N'Cơ sở Quận 7', 'hoat_dong');

    IF NOT EXISTS (SELECT 1 FROM dbo.CoSo WHERE ma_co_so = 'TD')
        INSERT dbo.CoSo (ma_co_so, ten_co_so, trang_thai) VALUES ('TD', N'Cơ sở Thủ Đức', 'hoat_dong');

    IF NOT EXISTS (SELECT 1 FROM dbo.MonHoc WHERE ma_mon = 'MH-ENG')
        INSERT dbo.MonHoc (ma_mon, ten_mon, mo_ta) VALUES ('MH-ENG', N'Tiếng Anh', N'Danh mục môn học dùng chung');

    IF NOT EXISTS (SELECT 1 FROM dbo.MonHoc WHERE ma_mon = 'MH-JPN')
        INSERT dbo.MonHoc (ma_mon, ten_mon, mo_ta) VALUES ('MH-JPN', N'Tiếng Nhật', N'Danh mục môn học dùng chung');

    IF NOT EXISTS (SELECT 1 FROM dbo.KhoaHoc WHERE ma_khoa_hoc = 'KH-IELTS-65')
        INSERT dbo.KhoaHoc (ma_khoa_hoc, ma_mon, ten_khoa_hoc, trinh_do, so_buoi, hoc_phi_chuan)
        VALUES ('KH-IELTS-65', 'MH-ENG', N'IELTS 6.5', N'IELTS 6.5', 24, 12000000);

    IF NOT EXISTS (SELECT 1 FROM dbo.KhoaHoc WHERE ma_khoa_hoc = 'KH-JP-N5')
        INSERT dbo.KhoaHoc (ma_khoa_hoc, ma_mon, ten_khoa_hoc, trinh_do, so_buoi, hoc_phi_chuan)
        VALUES ('KH-JP-N5', 'MH-JPN', N'Tiếng Nhật N5', N'N5', 30, 6000000);

    IF (SELECT COUNT(*) FROM dbo.CoSo WHERE ma_co_so IN ('Q1', 'Q7', 'TD')) <> 3
       OR EXISTS
       (
           SELECT 1
           FROM dbo.CoSo
           WHERE (ma_co_so = 'Q1' AND (ten_co_so <> N'Cơ sở Quận 1' OR trang_thai <> 'hoat_dong'))
              OR (ma_co_so = 'Q7' AND (ten_co_so <> N'Cơ sở Quận 7' OR trang_thai <> 'hoat_dong'))
              OR (ma_co_so = 'TD' AND (ten_co_so <> N'Cơ sở Thủ Đức' OR trang_thai <> 'hoat_dong'))
       )
    BEGIN
        ;THROW 51012, N'Danh mục CoSo đã có dữ liệu khác với bộ seed ban đầu; cần đối soát trước khi tiếp tục.', 1;
    END;

    IF EXISTS
       (
           SELECT 1 FROM dbo.MonHoc
           WHERE (ma_mon = 'MH-ENG' AND ten_mon <> N'Tiếng Anh')
              OR (ma_mon = 'MH-JPN' AND ten_mon <> N'Tiếng Nhật')
       )
       OR EXISTS
       (
           SELECT 1 FROM dbo.KhoaHoc
           WHERE (ma_khoa_hoc = 'KH-IELTS-65' AND (ma_mon <> 'MH-ENG' OR ten_khoa_hoc <> N'IELTS 6.5' OR so_buoi <> 24 OR hoc_phi_chuan <> 12000000))
              OR (ma_khoa_hoc = 'KH-JP-N5' AND (ma_mon <> 'MH-JPN' OR ten_khoa_hoc <> N'Tiếng Nhật N5' OR so_buoi <> 30 OR hoc_phi_chuan <> 6000000))
       )
    BEGIN
        ;THROW 51013, N'Danh mục môn/khóa học khác với bộ seed ban đầu; cần đối soát trước khi tiếp tục.', 1;
    END;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

SELECT ma_co_so, ten_co_so, trang_thai, phien_ban, cap_nhat_luc
FROM dbo.CoSo
ORDER BY ma_co_so;

SELECT k.ma_khoa_hoc, k.ten_khoa_hoc, m.ten_mon, k.so_buoi, k.hoc_phi_chuan
FROM dbo.KhoaHoc AS k
JOIN dbo.MonHoc AS m ON m.ma_mon = k.ma_mon
ORDER BY k.ma_khoa_hoc;
GO
