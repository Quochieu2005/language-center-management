/*
    Chạy một lần trên từng database QLTTNN_<SITE>, sau các script schema hiện có.
    Không tạo database hoặc bảng mới. Bổ sung CHECK để SQL Server chặn ghi trực
    tiếp một dòng nghiệp vụ vào sai site, kể cả khi lệnh không đi qua API.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;

DECLARE @database_name sysname = DB_NAME();
IF LEFT(@database_name, 7) <> N'QLTTNN_' OR LEN(@database_name) <= 7
   OR LEN(@database_name) > 17
    THROW 51300, N'Hãy chọn đúng một database site có tên QLTTNN_<SITE>.', 1;

DECLARE @site_code varchar(10) = SUBSTRING(@database_name, 8, 10);
IF LEN(@site_code) > 10 OR OBJECT_ID(N'dbo.CoSo', N'U') IS NULL
    THROW 51301, N'Không xác định được mã site hoặc thiếu dbo.CoSo.', 1;
IF NOT EXISTS
(
    SELECT 1 FROM dbo.CoSo
    WHERE ma_co_so = @site_code AND trang_thai = 'hoat_dong'
)
    THROW 51302, N'Mã site trong tên database không khớp một cơ sở đang hoạt động.', 1;

DECLARE @boundaries table
(
    row_id int IDENTITY(1,1) PRIMARY KEY,
    table_name sysname NOT NULL,
    constraint_name sysname NOT NULL,
    scope_kind varchar(20) NOT NULL
);

INSERT INTO @boundaries (table_name, constraint_name, scope_kind)
VALUES
    (N'HocVien', N'CK_HocVien_site_local', 'ma_co_so'),
    (N'GiaoVien', N'CK_GiaoVien_site_local', 'ma_co_so'),
    (N'NhanVien', N'CK_NhanVien_site_local', 'ma_co_so'),
    (N'Admin', N'CK_Admin_site_local', 'admin'),
    (N'PhongHoc', N'CK_PhongHoc_site_local', 'ma_co_so'),
    (N'LopHoc', N'CK_LopHoc_site_local', 'ma_co_so'),
    (N'BuoiHoc', N'CK_BuoiHoc_site_local', 'ma_co_so'),
    (N'DangKy', N'CK_DangKy_site_local', 'ma_co_so'),
    (N'HocPhi', N'CK_HocPhi_site_local', 'ma_co_so'),
    (N'DotHocPhi', N'CK_DotHocPhi_site_local', 'ma_co_so'),
    (N'GiaoDichChuyenCoSo', N'CK_GiaoDichChuyenCoSo_site_local', 'transfer_source'),
    (N'LichSuChuyenCoSo', N'CK_LichSuChuyenCoSo_site_local', 'transfer_log'),
    (N'PhieuThu', N'CK_PhieuThu_site_local', 'ma_co_so'),
    (N'Diem', N'CK_Diem_site_local', 'ma_co_so'),
    (N'DiemDanh', N'CK_DiemDanh_site_local', 'ma_co_so'),
    (N'ThongBao', N'CK_ThongBao_site_local', 'ma_co_so');

DECLARE @index int = 1;
DECLARE @row_count int = (SELECT COUNT(*) FROM @boundaries);
DECLARE @table_name sysname;
DECLARE @constraint_name sysname;
DECLARE @scope_kind varchar(20);
DECLARE @predicate nvarchar(500);
DECLARE @site_literal nvarchar(30) = QUOTENAME(@site_code, '''');
DECLARE @sql nvarchar(max);
DECLARE @invalid bit;
DECLARE @error_message nvarchar(2048);

BEGIN TRY
    BEGIN TRANSACTION;

    WHILE @index <= @row_count
    BEGIN
        SELECT @table_name = table_name,
               @constraint_name = constraint_name,
               @scope_kind = scope_kind
        FROM @boundaries WHERE row_id = @index;

        IF OBJECT_ID(N'dbo.' + @table_name, N'U') IS NULL
        BEGIN
            SET @error_message = N'Thiếu bảng dbo.' + @table_name + N'; chưa thêm ràng buộc site.';
            THROW 51303, @error_message, 1;
        END;

        SET @predicate = CASE @scope_kind
            WHEN 'admin' THEN
                N'(([loai_admin] = ''admin_big'' AND [ma_co_so] IS NULL) '
                + N'OR ([loai_admin] = ''admin_small'' AND [ma_co_so] = ' + @site_literal + N'))'
            WHEN 'transfer_source' THEN N'[co_so_nguon] = ' + @site_literal
            WHEN 'transfer_log' THEN N'[site_ghi] = ' + @site_literal
            ELSE N'[ma_co_so] IS NOT NULL AND [ma_co_so] = ' + @site_literal
        END;

        SET @sql = N'SELECT @invalid = CASE WHEN EXISTS '
            + N'(SELECT 1 FROM dbo.' + QUOTENAME(@table_name)
            + N' WHERE NOT (' + @predicate + N')) THEN 1 ELSE 0 END;';
        SET @invalid = 0;
        EXEC sys.sp_executesql
            @sql,
            N'@invalid bit OUTPUT',
            @invalid = @invalid OUTPUT;
        IF @invalid = 1
        BEGIN
            SET @error_message = N'Bảng dbo.' + @table_name
                + N' đang có dòng ngoài site ' + @site_code
                + N'. Đối soát dữ liệu trước khi chạy lại migration.';
            THROW 51304, @error_message, 1;
        END;

        IF NOT EXISTS
        (
            SELECT 1 FROM sys.check_constraints
            WHERE parent_object_id = OBJECT_ID(N'dbo.' + @table_name)
              AND name = @constraint_name
        )
        BEGIN
            SET @sql = N'ALTER TABLE dbo.' + QUOTENAME(@table_name)
                + N' WITH CHECK ADD CONSTRAINT ' + QUOTENAME(@constraint_name)
                + N' CHECK (' + @predicate + N');';
            EXEC sys.sp_executesql @sql;
        END;

        SET @index += 1;
    END;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;

SELECT DB_NAME() AS database_site,
       @site_code AS ma_site,
       COUNT(*) AS so_rang_buoc_site_local
FROM sys.check_constraints
WHERE parent_object_id IN
(
    SELECT OBJECT_ID(N'dbo.' + table_name) FROM @boundaries
)
  AND name IN (SELECT constraint_name FROM @boundaries);
