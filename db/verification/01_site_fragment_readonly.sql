/* TC-SITE-01 / TC-FRAG-01: chọn DB site trước khi chạy; không đổi dữ liệu/schema. */
SET NOCOUNT ON;
DECLARE @db sysname = DB_NAME();
IF LEFT(@db, 7) <> N'QLTTNN_' OR LEN(@db) <= 7 OR LEN(@db) > 17
    THROW 51400, N'Hãy chọn database QLTTNN_<SITE>, không chạy trong master.', 1;
DECLARE @site varchar(10) = SUBSTRING(@db, 8, 10);
IF NOT EXISTS (SELECT 1 FROM dbo.CoSo WHERE ma_co_so = @site)
    THROW 51401, N'Site của database không có trong danh mục CoSo.', 1;

SELECT @@SERVERNAME AS instance_name, DB_NAME() AS database_name,
       @site AS site_code, SERVERPROPERTY('Edition') AS edition,
       SERVERPROPERTY('ProductVersion') AS product_version,
       SYSDATETIMEOFFSET() AS sampled_at;

/* Có tên constraint không có nghĩa constraint đang bảo vệ dữ liệu. */
SELECT name, OBJECT_NAME(parent_object_id) AS table_name,
       is_disabled, is_not_trusted
FROM sys.check_constraints
WHERE name LIKE N'CK_%[_]site[_]local'
ORDER BY table_name;

IF EXISTS (
    SELECT 1 FROM sys.check_constraints
    WHERE name IN (N'CK_LopHoc_site_local', N'CK_DangKy_site_local')
      AND (is_disabled = 1 OR is_not_trusted = 1)
) OR (SELECT COUNT(*) FROM sys.check_constraints
      WHERE (name = N'CK_LopHoc_site_local' AND parent_object_id = OBJECT_ID(N'dbo.LopHoc'))
         OR (name = N'CK_DangKy_site_local' AND parent_object_id = OBJECT_ID(N'dbo.DangKy'))) <> 2
    THROW 51402, N'Thiếu hoặc tắt/chưa trust CHECK site của lớp/đăng ký; đối soát migration 30.', 1;

IF EXISTS (SELECT 1 FROM dbo.LopHoc WHERE ma_co_so IS NULL OR ma_co_so <> @site)
   OR EXISTS (SELECT 1 FROM dbo.DangKy WHERE ma_co_so IS NULL OR ma_co_so <> @site)
   OR EXISTS (SELECT 1 FROM dbo.YeuCauLienHe WHERE ma_co_so IS NULL OR ma_co_so <> @site)
    THROW 51403, N'Có dòng lớp/đăng ký nằm sai mảnh.', 1;

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints
               WHERE parent_object_id = OBJECT_ID(N'dbo.YeuCauLienHe')
                 AND name = N'CK_YeuCauLienHe_site_local'
                 AND is_disabled = 0 AND is_not_trusted = 0)
    THROW 51406, N'Thiếu CHECK site liên hệ đang bật/trusted; chạy migration 43.', 1;

IF EXISTS (
    SELECT 1 FROM dbo.DangKy AS d
    LEFT JOIN dbo.LopHoc AS l ON l.ma_lop = d.ma_lop AND l.ma_co_so = d.ma_co_so
    LEFT JOIN dbo.HocVien AS h ON h.ma_hoc_vien = d.ma_hoc_vien AND h.ma_co_so = d.ma_co_so
    WHERE l.ma_lop IS NULL OR h.ma_hoc_vien IS NULL
) OR EXISTS (
    SELECT 1 FROM dbo.HocPhi AS hp
    LEFT JOIN dbo.DangKy AS d ON d.ma_dang_ky = hp.ma_dang_ky AND d.ma_co_so = hp.ma_co_so
    WHERE d.ma_dang_ky IS NULL
)
    THROW 51404, N'Có dòng dẫn xuất thiếu cha hoặc khác site với cha.', 1;

/* Dùng tập mã để so với fixture kỳ vọng và hợp kết quả ngoài database. */
SELECT @site AS site_code, ma_lop, ma_co_so, ma_khoa_hoc,
       si_so_hien_tai, si_so_toi_da, trang_thai
FROM dbo.LopHoc ORDER BY ma_lop;
SELECT @site AS site_code, ma_dang_ky, ma_co_so, ma_lop, trang_thai
FROM dbo.DangKy ORDER BY ma_dang_ky;
SELECT @site AS site_code, COUNT_BIG(*) AS class_count FROM dbo.LopHoc;
SELECT @site AS site_code, COUNT_BIG(*) AS enrollment_count FROM dbo.DangKy;
SELECT @site AS site_code, COUNT_BIG(*) AS active_student_rows
FROM dbo.HocVien WHERE trang_thai = 'dang_hoc';

/* Chỉ là số dòng ổn định để đối chiếu; khi đang chuyển phải áp dụng quy tắc Coordinator. */
SELECT N'LOCAL checks passed; still compare all site sets and expected fixtures' AS result;
