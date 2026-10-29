/*
    Run once on every configured site database after db/22 is installed on the
    Coordinator. Normal UPDATE remains prohibited. DELETE on these append-only
    records is permitted only while the API sets qlttnn_student_purge in the
    current SQL Server session, and only records selected by the purge service.
*/
SET NOCOUNT ON;

IF OBJECT_ID(N'dbo.LichSuChuyenCoSo', N'U') IS NULL
   OR OBJECT_ID(N'dbo.NhatKyHeThong', N'U') IS NULL
   OR OBJECT_ID(N'dbo.NhatKyDongBo', N'U') IS NULL
   OR OBJECT_ID(N'dbo.SuKienDangNhap', N'U') IS NULL
   OR OBJECT_ID(N'dbo.SuKienQuenMatKhau', N'U') IS NULL
    THROW 51230, N'Thiếu bảng nhật ký cần thiết; hãy cài schema, session và OTP trước.', 1;
GO

IF OBJECT_ID(N'dbo.TR_LichSuChuyenCoSo_AppendOnly', N'TR') IS NOT NULL
    DROP TRIGGER dbo.TR_LichSuChuyenCoSo_AppendOnly;
GO
CREATE TRIGGER dbo.TR_LichSuChuyenCoSo_AppendOnly
ON dbo.LichSuChuyenCoSo
AFTER UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM inserted)
    BEGIN
        ;THROW 51231, N'LichSuChuyenCoSo không được cập nhật.', 1;
    END;
    IF ISNULL(TRY_CONVERT(bit, SESSION_CONTEXT(N'qlttnn_student_purge')), 0) <> 1
    BEGIN
        ;THROW 51232, N'Chỉ luồng xóa học viên được phép xóa sự kiện chuyển cơ sở.', 1;
    END;
END;
GO

IF OBJECT_ID(N'dbo.TR_NhatKyHeThong_AppendOnly', N'TR') IS NOT NULL
    DROP TRIGGER dbo.TR_NhatKyHeThong_AppendOnly;
GO
CREATE TRIGGER dbo.TR_NhatKyHeThong_AppendOnly
ON dbo.NhatKyHeThong
AFTER UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM inserted)
    BEGIN
        ;THROW 51233, N'NhatKyHeThong không được cập nhật.', 1;
    END;
    IF ISNULL(TRY_CONVERT(bit, SESSION_CONTEXT(N'qlttnn_student_purge')), 0) <> 1
    BEGIN
        ;THROW 51234, N'Chỉ luồng xóa học viên được phép xóa nhật ký liên quan.', 1;
    END;
END;
GO

IF OBJECT_ID(N'dbo.TR_NhatKyDongBo_AppendOnly', N'TR') IS NOT NULL
    DROP TRIGGER dbo.TR_NhatKyDongBo_AppendOnly;
GO
CREATE TRIGGER dbo.TR_NhatKyDongBo_AppendOnly
ON dbo.NhatKyDongBo
AFTER UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM inserted)
    BEGIN
        ;THROW 51235, N'NhatKyDongBo không được cập nhật.', 1;
    END;
    IF ISNULL(TRY_CONVERT(bit, SESSION_CONTEXT(N'qlttnn_student_purge')), 0) <> 1
    BEGIN
        ;THROW 51236, N'Chỉ luồng xóa học viên được phép xóa sự kiện đồng bộ liên quan.', 1;
    END;
END;
GO

IF OBJECT_ID(N'dbo.TR_SuKienDangNhap_AppendOnly', N'TR') IS NOT NULL
    DROP TRIGGER dbo.TR_SuKienDangNhap_AppendOnly;
GO
CREATE TRIGGER dbo.TR_SuKienDangNhap_AppendOnly
ON dbo.SuKienDangNhap
AFTER UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM inserted)
    BEGIN
        ;THROW 51237, N'SuKienDangNhap không được cập nhật.', 1;
    END;
    IF ISNULL(TRY_CONVERT(bit, SESSION_CONTEXT(N'qlttnn_student_purge')), 0) <> 1
    BEGIN
        ;THROW 51238, N'Chỉ luồng xóa học viên được phép xóa sự kiện đăng nhập liên quan.', 1;
    END;
END;
GO

IF OBJECT_ID(N'dbo.TR_SuKienQuenMatKhau_AppendOnly', N'TR') IS NOT NULL
    DROP TRIGGER dbo.TR_SuKienQuenMatKhau_AppendOnly;
GO
CREATE TRIGGER dbo.TR_SuKienQuenMatKhau_AppendOnly
ON dbo.SuKienQuenMatKhau
AFTER UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM inserted)
    BEGIN
        ;THROW 51239, N'SuKienQuenMatKhau không được cập nhật.', 1;
    END;
    IF ISNULL(TRY_CONVERT(bit, SESSION_CONTEXT(N'qlttnn_student_purge')), 0) <> 1
    BEGIN
        ;THROW 51240, N'Chỉ luồng xóa học viên được phép xóa sự kiện đặt lại liên quan.', 1;
    END;
END;
GO

SELECT DB_NAME() AS site_database,
       COUNT(*) AS scoped_student_purge_triggers
FROM sys.triggers
WHERE name IN
    (N'TR_LichSuChuyenCoSo_AppendOnly', N'TR_NhatKyHeThong_AppendOnly',
     N'TR_NhatKyDongBo_AppendOnly', N'TR_SuKienDangNhap_AppendOnly',
     N'TR_SuKienQuenMatKhau_AppendOnly');
GO
