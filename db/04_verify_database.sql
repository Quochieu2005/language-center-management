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
                 N'GiaoDichChuyenCoSo', N'LichSuChuyenCoSo')
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
