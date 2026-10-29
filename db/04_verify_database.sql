:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

SET NOCOUNT ON;

IF DB_ID(DB_NAME()) <= 4
BEGIN
    ;THROW 51020, N'Hãy chọn một CSDL site, không chạy trong system database.', 1;
END;

IF (SELECT COUNT(*) FROM sys.tables
    WHERE schema_id = SCHEMA_ID(N'dbo')
      AND name IN (N'HocVien', N'LopHoc', N'GiaoVien', N'MonHoc', N'DangKy', N'HocPhi', N'Diem',
                   N'GiaoDichChuyenCoSo', N'LichSuChuyenCoSo')) <> 9
BEGIN
    ;THROW 51021, N'Thiếu bảng cốt lõi hoặc bảng giao dịch chuyển cơ sở. Hãy kiểm tra lại 01_create_schema.sql.', 1;
END;

IF COL_LENGTH(N'dbo.TaiKhoan', N'google_subject') IS NULL
   OR COL_LENGTH(N'dbo.TaiKhoan', N'facebook_subject') IS NULL
   OR OBJECT_ID(N'dbo.TaiKhoanLienKetOAuth', N'U') IS NOT NULL
   OR NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.TaiKhoan')
                  AND name = N'UX_TaiKhoan_google_subject' AND is_unique = 1)
   OR NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.TaiKhoan')
                  AND name = N'UX_TaiKhoan_facebook_subject' AND is_unique = 1)
   OR NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE parent_object_id = OBJECT_ID(N'dbo.TaiKhoan')
                  AND name = N'CK_TaiKhoan_google_subject')
   OR NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE parent_object_id = OBJECT_ID(N'dbo.TaiKhoan')
                  AND name = N'CK_TaiKhoan_facebook_subject')
BEGIN
    ;THROW 51026, N'Thiếu cột định danh đăng nhập trong TaiKhoan hoặc còn bảng OAuth cũ. Chạy 27_move_oauth_identity_to_account.sql trên site này.', 1;
END;

IF OBJECT_ID(N'dbo.PhienDangNhap', N'U') IS NULL
   OR OBJECT_ID(N'dbo.Logs', N'U') IS NULL
BEGIN
    ;THROW 51074, N'Thiếu bảng phiên hoặc Logs. Chạy các migration xác thực và 26_consolidate_logs_and_remove_notification_reads.sql trên site này.', 1;
END;

IF COL_LENGTH(N'dbo.TokenDatLaiMatKhau', N'so_lan_sai') IS NULL
   OR OBJECT_ID(N'dbo.GiaoDichDatLaiMatKhau', N'U') IS NULL
   OR NOT EXISTS (SELECT 1 FROM sys.triggers WHERE name = N'TR_Logs_AppendOnly')
BEGIN
    ;THROW 51124, N'Thiếu cấu trúc OTP hoặc trigger bảo vệ Logs. Chạy migration OTP và 26_consolidate_logs_and_remove_notification_reads.sql trên site này.', 1;
END;

IF OBJECT_ID(N'dbo.TrangThaiDocThongBao', N'U') IS NOT NULL
   OR OBJECT_ID(N'dbo.SuKienDangNhap', N'U') IS NOT NULL
   OR OBJECT_ID(N'dbo.SuKienQuenMatKhau', N'U') IS NOT NULL
   OR OBJECT_ID(N'dbo.NhatKyHeThong', N'U') IS NOT NULL
   OR OBJECT_ID(N'dbo.NhatKyDongBo', N'U') IS NOT NULL
BEGIN
    ;THROW 51268, N'Còn bảng nhật ký cũ hoặc trạng thái đọc; hãy chạy migration 26 trên site này.', 1;
END;

IF (SELECT COUNT(*) FROM sys.check_constraints
    WHERE parent_object_id = OBJECT_ID(N'dbo.TaiKhoan')
      AND name IN (N'CK_TaiKhoan_vai_tro', N'CK_TaiKhoan_pham_vi')) <> 2
BEGIN
    ;THROW 51075, N'Thiếu constraint vai trò/phạm vi tài khoản.', 1;
END;

IF (SELECT COUNT(*) FROM sys.columns
    WHERE object_id = OBJECT_ID(N'dbo.TaiKhoan')
      AND name IN (N'slug', N'mat_khau')) <> 2
   OR NOT EXISTS (SELECT 1 FROM sys.indexes
                  WHERE object_id = OBJECT_ID(N'dbo.TaiKhoan')
                    AND name = N'UQ_TaiKhoan_slug' AND is_unique = 1)
BEGIN
    ;THROW 51076, N'Thiếu cột slug/mat_khau hoặc unique constraint của slug trên TaiKhoan.', 1;
END;

IF (SELECT COUNT(*) FROM sys.columns
    WHERE object_id = OBJECT_ID(N'dbo.CoSo') AND name = N'slug') <> 1
   OR (SELECT COUNT(*) FROM sys.columns
       WHERE object_id = OBJECT_ID(N'dbo.KhoaHoc') AND name = N'slug') <> 1
   OR (SELECT COUNT(*) FROM sys.columns
       WHERE object_id = OBJECT_ID(N'dbo.MonHoc') AND name = N'slug') <> 1
   OR NOT EXISTS (SELECT 1 FROM sys.indexes
                  WHERE object_id = OBJECT_ID(N'dbo.CoSo')
                    AND name = N'UQ_CoSo_slug' AND is_unique = 1)
   OR NOT EXISTS (SELECT 1 FROM sys.indexes
                  WHERE object_id = OBJECT_ID(N'dbo.KhoaHoc')
                    AND name = N'UQ_KhoaHoc_slug' AND is_unique = 1)
   OR NOT EXISTS (SELECT 1 FROM sys.indexes
                  WHERE object_id = OBJECT_ID(N'dbo.MonHoc')
                    AND name = N'UQ_MonHoc_slug' AND is_unique = 1)
BEGIN
    ;THROW 51097, N'Thiếu slug duy nhất cho danh mục cơ sở, môn học hoặc khóa học.', 1;
END;

IF (SELECT COUNT(*) FROM sys.triggers
    WHERE parent_id = OBJECT_ID(N'dbo.LichSuChuyenCoSo')
      AND name = N'TR_LichSuChuyenCoSo_AppendOnly') <> 1
BEGIN
    ;THROW 51022, N'Thiếu trigger bảo vệ nhật ký chuyển cơ sở append-only.', 1;
END;

IF (SELECT COUNT(*) FROM sys.sequences
    WHERE schema_id = SCHEMA_ID(N'dbo')
      AND name IN (N'Seq_CC', N'Seq_LS')) <> 2
BEGIN
    ;THROW 51023, N'Thiếu sequence cấp mã giao dịch hoặc sự kiện chuyển cơ sở.', 1;
END;

IF (SELECT COUNT(*) FROM sys.columns
    WHERE object_id = OBJECT_ID(N'dbo.GiaoDichChuyenCoSo')
      AND name IN (N'ma_tai_khoan_de_nghi', N'ma_tai_khoan_quyet_dinh', N'ly_do_de_nghi',
                   N'ly_do_tu_choi', N'ngay_quyet_dinh', N'khoa_chong_trung_chuyen')) <> 6
BEGIN
    ;THROW 51024, N'Thiếu cột phục vụ đề nghị/duyệt chuyển cơ sở hoặc giới hạn giao dịch đang mở.', 1;
END;

IF (SELECT COUNT(*) FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.GiaoDichChuyenCoSo')
      AND name IN (N'UX_GiaoDichChuyenCoSo_khoa_chong_trung', N'IX_GiaoDichChuyenCoSo_hang_cho_duyet')) <> 2
BEGIN
    ;THROW 51025, N'Thiếu index giới hạn đề nghị đang mở hoặc phục vụ hộp thư chờ duyệt.', 1;
END;

SELECT DB_NAME() AS database_dang_kiem_tra;

/* Kiểm tra các bảng cốt lõi có tồn tại tại database đang chọn. */
SELECT ten_bang = t.name,
       so_dong = SUM(p.rows)
FROM sys.tables AS t
JOIN sys.partitions AS p ON p.object_id = t.object_id AND p.index_id IN (0, 1)
WHERE t.schema_id = SCHEMA_ID(N'dbo')
  AND t.name IN (N'HocVien', N'LopHoc', N'GiaoVien', N'MonHoc', N'DangKy', N'HocPhi', N'Diem',
                 N'GiaoDichChuyenCoSo', N'LichSuChuyenCoSo', N'TaiKhoan',
                 N'PhienDangNhap', N'TokenDatLaiMatKhau', N'GiaoDichDatLaiMatKhau', N'Logs')
GROUP BY t.name
ORDER BY t.name;

/* Danh mục nhân bản phải có đủ ba cơ sở ban đầu. */
SELECT ma_co_so, ten_co_so, trang_thai
FROM dbo.CoSo
ORDER BY ma_co_so;

SELECT ma_mon, ten_mon FROM dbo.MonHoc ORDER BY ma_mon;
SELECT ma_khoa_hoc, ma_mon, ten_khoa_hoc, so_buoi, hoc_phi_chuan
FROM dbo.KhoaHoc
ORDER BY ma_khoa_hoc;

/* Kiểm tra constraint tại site này; không truy vấn database site khác. */
DBCC CHECKCONSTRAINTS WITH ALL_CONSTRAINTS;
GO
