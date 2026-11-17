:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

/* Run once in every site database before deploying the merged employee role. */
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_ID(DB_NAME()) <= 4
    THROW 51410, N'Hãy chọn một CSDL site, không chạy trong system database.', 1;
IF OBJECT_ID(N'dbo.NhanVien', N'U') IS NULL
    THROW 51411, N'Thiếu dbo.NhanVien; hãy cài schema trước.', 1;
IF EXISTS
(
    SELECT 1 FROM dbo.NhanVien
    WHERE chuc_vu IS NULL
       OR chuc_vu NOT IN ('le_tan', 'tu_van', 'ke_toan', 'quan_ly_co_so')
)
    THROW 51412, N'Có chức vụ ngoài danh sách đã biết; dừng để đối soát trước khi cập nhật.', 1;

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.CK_NhanVien_chuc_vu', N'C') IS NOT NULL
        ALTER TABLE dbo.NhanVien DROP CONSTRAINT CK_NhanVien_chuc_vu;

    UPDATE dbo.NhanVien
    SET chuc_vu = 'ke_toan'
    WHERE chuc_vu = 'le_tan';

    ALTER TABLE dbo.NhanVien WITH CHECK
        ADD CONSTRAINT CK_NhanVien_chuc_vu CHECK
            (chuc_vu IN ('tu_van', 'ke_toan', 'quan_ly_co_so'));

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

SELECT DB_NAME() AS database_dang_cap_nhat,
       COUNT_BIG(*) AS tong_nhan_vien,
       SUM(CASE WHEN chuc_vu = 'ke_toan' THEN 1 ELSE 0 END) AS ke_toan_va_le_tan,
       SUM(CASE WHEN chuc_vu = 'tu_van' THEN 1 ELSE 0 END) AS tu_van_va_xep_lop
FROM dbo.NhanVien;
GO
