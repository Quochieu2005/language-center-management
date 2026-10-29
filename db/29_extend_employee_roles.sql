:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_ID(DB_NAME()) <= 4
    THROW 51291, N'Hãy chọn một CSDL site, không chạy trong system database.', 1;
IF OBJECT_ID(N'dbo.NhanVien', N'U') IS NULL
    THROW 51292, N'Thiếu dbo.NhanVien; hãy cài schema trước.', 1;
IF EXISTS
(
    SELECT 1 FROM dbo.NhanVien
    WHERE chuc_vu NOT IN ('le_tan', 'tu_van', 'ke_toan', 'xep_lop', 'quan_ly_co_so')
)
    THROW 51293, N'Có chức vụ nhân viên ngoài danh sách; dừng để đối soát trước khi cập nhật.', 1;

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.CK_NhanVien_chuc_vu', N'C') IS NOT NULL
        ALTER TABLE dbo.NhanVien DROP CONSTRAINT CK_NhanVien_chuc_vu;

    ALTER TABLE dbo.NhanVien WITH CHECK
        ADD CONSTRAINT CK_NhanVien_chuc_vu CHECK
            (chuc_vu IN ('le_tan', 'tu_van', 'ke_toan', 'xep_lop', 'quan_ly_co_so'));

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

SELECT DB_NAME() AS database_dang_cap_nhat,
       COUNT_BIG(*) AS tong_nhan_vien,
       SUM(CASE WHEN chuc_vu = 'tu_van' THEN 1 ELSE 0 END) AS nhan_vien_tu_van,
       SUM(CASE WHEN chuc_vu = 'ke_toan' THEN 1 ELSE 0 END) AS nhan_vien_ke_toan,
       SUM(CASE WHEN chuc_vu = 'xep_lop' THEN 1 ELSE 0 END) AS nhan_vien_xep_lop
FROM dbo.NhanVien;
GO
