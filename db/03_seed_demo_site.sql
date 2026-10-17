:setvar DatabaseName "QLTTNN_Q1"
:setvar SiteCode "Q1"
USE [$(DatabaseName)];
GO

/*
    Dữ liệu kiểm thử tùy chọn, chạy một lần trên mỗi site.
    Chọn DatabaseName và SiteCode khớp nhau trước khi chạy.
    Không có tài khoản/mật khẩu mẫu; không dùng cho dữ liệu thật.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;

DECLARE @SiteCode VARCHAR(10) = '$(SiteCode)';
DECLARE @ExpectedDatabase VARCHAR(128) = CONCAT('QLTTNN_', @SiteCode);
DECLARE @Today DATE = CONVERT(DATE, SYSUTCDATETIME());
DECLARE @DemoStudentName NVARCHAR(150) = CONCAT(N'Học viên kiểm thử ', @SiteCode);
DECLARE @Counter BIGINT;
DECLARE @MaHocVien VARCHAR(24);
DECLARE @MaGiaoVien VARCHAR(24);
DECLARE @MaNhanVien VARCHAR(24);
DECLARE @MaPhong VARCHAR(24);
DECLARE @MaLop VARCHAR(24);
DECLARE @MaBuoi VARCHAR(24);
DECLARE @MaDangKy VARCHAR(24);
DECLARE @MaHocPhi VARCHAR(24);
DECLARE @MaPhieu VARCHAR(24);
DECLARE @MaDiem VARCHAR(24);

IF OBJECT_ID(N'dbo.CoSo', N'U') IS NULL
BEGIN
    ;THROW 51039, N'Chưa tạo schema. Hãy chạy 01_create_schema.sql trước.', 1;
END;

IF DB_NAME() <> @ExpectedDatabase
BEGIN
    ;THROW 51040, N'DatabaseName và SiteCode không khớp nhau.', 1;
END;

IF NOT EXISTS (SELECT 1 FROM dbo.CoSo WHERE ma_co_so = @SiteCode AND trang_thai = 'hoat_dong')
BEGIN
    ;THROW 51041, N'Site chưa có trong CoSo hoặc không ở trạng thái hoat_dong. Hãy nạp danh mục trước.', 1;
END;

IF EXISTS (SELECT 1 FROM dbo.HocVien WHERE ma_co_so = @SiteCode AND ho_ten = @DemoStudentName)
BEGIN
    ;THROW 51042, N'Dữ liệu demo đã tồn tại tại site này; không nạp lặp lại.', 1;
END;

/* Lấy số từ sequence riêng của database; số đã lấy có thể bị khuyết nếu rollback. */
SELECT @Counter = NEXT VALUE FOR dbo.Seq_HV;
SET @MaHocVien = CONCAT(@SiteCode, '-HV-', RIGHT(CONCAT('000000', @Counter), 6));
SELECT @Counter = NEXT VALUE FOR dbo.Seq_GV;
SET @MaGiaoVien = CONCAT(@SiteCode, '-GV-', RIGHT(CONCAT('000000', @Counter), 6));
SELECT @Counter = NEXT VALUE FOR dbo.Seq_NV;
SET @MaNhanVien = CONCAT(@SiteCode, '-NV-', RIGHT(CONCAT('000000', @Counter), 6));
SELECT @Counter = NEXT VALUE FOR dbo.Seq_PH;
SET @MaPhong = CONCAT(@SiteCode, '-PH-', RIGHT(CONCAT('000000', @Counter), 6));
SELECT @Counter = NEXT VALUE FOR dbo.Seq_LH;
SET @MaLop = CONCAT(@SiteCode, '-LH-', RIGHT(CONCAT('000000', @Counter), 6));
SELECT @Counter = NEXT VALUE FOR dbo.Seq_BH;
SET @MaBuoi = CONCAT(@SiteCode, '-BH-', RIGHT(CONCAT('000000', @Counter), 6));
SELECT @Counter = NEXT VALUE FOR dbo.Seq_DK;
SET @MaDangKy = CONCAT(@SiteCode, '-DK-', RIGHT(CONCAT('000000', @Counter), 6));
SELECT @Counter = NEXT VALUE FOR dbo.Seq_HP;
SET @MaHocPhi = CONCAT(@SiteCode, '-HP-', RIGHT(CONCAT('000000', @Counter), 6));
SELECT @Counter = NEXT VALUE FOR dbo.Seq_PT;
SET @MaPhieu = CONCAT(@SiteCode, '-PT-', RIGHT(CONCAT('000000', @Counter), 6));
SELECT @Counter = NEXT VALUE FOR dbo.Seq_DM;
SET @MaDiem = CONCAT(@SiteCode, '-DM-', RIGHT(CONCAT('000000', @Counter), 6));

BEGIN TRY
    BEGIN TRANSACTION;

    INSERT dbo.HocVien
        (ma_hoc_vien, ma_co_so, co_so_goc, ho_ten, ngay_nhap_hoc, trang_thai)
    VALUES
        (@MaHocVien, @SiteCode, @SiteCode, @DemoStudentName, @Today, 'dang_hoc');

    INSERT dbo.GiaoVien
        (ma_giao_vien, ma_co_so, ho_ten, chuyen_mon, trang_thai)
    VALUES
        (@MaGiaoVien, @SiteCode, CONCAT(N'Giáo viên kiểm thử ', @SiteCode), N'Tiếng Anh', 'dang_day');

    INSERT dbo.NhanVien
        (ma_nhan_vien, ma_co_so, ho_ten, chuc_vu, trang_thai)
    VALUES
        (@MaNhanVien, @SiteCode, CONCAT(N'Kế toán kiểm thử ', @SiteCode), 'ke_toan', 'dang_lam');

    INSERT dbo.PhongHoc (ma_phong, ma_co_so, ten_phong, suc_chua, trang_thai)
    VALUES (@MaPhong, @SiteCode, CONCAT(N'Phòng kiểm thử ', @SiteCode), 20, 'hoat_dong');

    INSERT dbo.LopHoc
        (ma_lop, ma_co_so, ma_khoa_hoc, ma_giao_vien, ma_phong, ten_lop,
         si_so_toi_da, si_so_hien_tai, ngay_khai_giang, ngay_ket_thuc,
         lich_hoc, gio_bat_dau, gio_ket_thuc, trang_thai)
    VALUES
        (@MaLop, @SiteCode, 'KH-IELTS-65', @MaGiaoVien, @MaPhong,
         CONCAT(N'Lớp kiểm thử ', @SiteCode), 20, 1, @Today, DATEADD(DAY, 90, @Today),
         N'T2-T4-T6', '18:00', '20:00', 'dang_hoc');

    INSERT dbo.BuoiHoc
        (ma_buoi, ma_co_so, ma_lop, so_thu_tu, ngay_hoc, gio_bat_dau, gio_ket_thuc,
         ma_phong, ma_giao_vien, trang_thai, ghi_chu)
    VALUES
        (@MaBuoi, @SiteCode, @MaLop, 1, DATEADD(DAY, 1, @Today), '18:00', '20:00',
         @MaPhong, @MaGiaoVien, 'du_kien', N'Buổi học dữ liệu kiểm thử');

    INSERT dbo.DangKy (ma_dang_ky, ma_co_so, ma_hoc_vien, ma_lop, trang_thai)
    VALUES (@MaDangKy, @SiteCode, @MaHocVien, @MaLop, 'dang_hoc');

    INSERT dbo.HocPhi
        (ma_hoc_phi, ma_co_so, ma_dang_ky, so_tien_phai_dong, giam_gia, so_tien_da_dong, trang_thai)
    VALUES (@MaHocPhi, @SiteCode, @MaDangKy, 12000000, 0, 2000000, 'dong_mot_phan');

    INSERT dbo.PhieuThu
        (ma_phieu, ma_co_so, ma_hoc_phi, loai, so_tien, hinh_thuc, ma_nhan_vien, ghi_chu)
    VALUES
        (@MaPhieu, @SiteCode, @MaHocPhi, 'thu', 2000000, 'chuyen_khoan', @MaNhanVien,
         N'Phiếu thu dữ liệu kiểm thử');

    INSERT dbo.Diem
        (ma_diem, ma_co_so, ma_dang_ky, loai_diem, diem_so, ma_giao_vien_nhap)
    VALUES (@MaDiem, @SiteCode, @MaDangKy, 'giua_ky', 8.50, @MaGiaoVien);

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;

SELECT @SiteCode AS site_demo, @MaHocVien AS ma_hoc_vien, @MaLop AS ma_lop,
       @MaDangKy AS ma_dang_ky, @MaHocPhi AS ma_hoc_phi;
GO
