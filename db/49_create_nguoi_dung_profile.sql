:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_ID(DB_NAME()) <= 4
    THROW 51490, N'Hãy chọn một CSDL site, không chạy trong system database.', 1;
IF OBJECT_ID(N'dbo.TaiKhoan', N'U') IS NULL
    THROW 51491, N'Thiếu bảng dbo.TaiKhoan; hãy chạy schema trước.', 1;
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = N'CK_TaiKhoan_vai_tro' AND definition LIKE N'%nguoi_dung%')
    THROW 51492, N'Hãy chạy 48_add_nguoi_dung_account_scope.sql trước.', 1;
GO

-- CHỈ chạy tại site authority (AUTH_SESSION_SITE_CODE, hiện là Q1), như 45/46.
-- dbo.NguoiDung là hồ sơ cá nhân của tài khoản vai trò nguoi_dung (xem website, chưa thuộc cơ sở nào).
-- Bảng nằm một chỗ tại authority, không nhân bản: khi người đó thành học viên, hồ sơ được chép sang
-- dbo.HocVien tại site của họ và bản ghi ở đây bị xóa.
BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.NguoiDung', N'U') IS NULL
        EXEC(N'CREATE TABLE dbo.NguoiDung
        (
            ma_nguoi_dung VARCHAR(24)   NOT NULL,
            ma_tai_khoan  VARCHAR(24)   NOT NULL,
            ho_ten        NVARCHAR(150) NOT NULL,
            ngay_sinh     DATE          NULL,
            gioi_tinh     NVARCHAR(20)  NULL,
            sdt           NVARCHAR(20)  NULL,
            dia_chi       NVARCHAR(300) NULL,
            ngay_tao      DATETIME2(0)  NOT NULL CONSTRAINT DF_NguoiDung_ngay_tao DEFAULT (SYSUTCDATETIME()),
            cap_nhat_luc  DATETIME2(0)  NOT NULL CONSTRAINT DF_NguoiDung_cap_nhat DEFAULT (SYSUTCDATETIME()),
            CONSTRAINT PK_NguoiDung PRIMARY KEY (ma_nguoi_dung),
            CONSTRAINT UQ_NguoiDung_ma_tai_khoan UNIQUE (ma_tai_khoan),
            CONSTRAINT FK_NguoiDung_TaiKhoan FOREIGN KEY (ma_tai_khoan) REFERENCES dbo.TaiKhoan(ma_tai_khoan),
            CONSTRAINT CK_NguoiDung_ho_ten CHECK (LEN(LTRIM(RTRIM(ho_ten))) > 0),
            CONSTRAINT CK_NguoiDung_gioi_tinh CHECK (gioi_tinh IS NULL OR gioi_tinh IN (N''Nam'', N''Nữ'', N''Khác''))
        )');

    -- Bản 48 cũ từng thêm 5 cột hồ sơ vào TaiKhoan: chép sang bảng mới rồi bỏ cột.
    IF COL_LENGTH(N'dbo.TaiKhoan', N'ho_ten') IS NOT NULL
    BEGIN
        EXEC(N'INSERT dbo.NguoiDung (ma_nguoi_dung, ma_tai_khoan, ho_ten, ngay_sinh, gioi_tinh, sdt, dia_chi)
               SELECT REPLACE(t.ma_tai_khoan, ''-TK-'', ''-ND-''), t.ma_tai_khoan, COALESCE(NULLIF(LTRIM(RTRIM(t.ho_ten)), N''''), t.ten_dang_nhap),
                      t.ngay_sinh, t.gioi_tinh, t.sdt, t.dia_chi
               FROM dbo.TaiKhoan AS t
               WHERE t.vai_tro = ''nguoi_dung''
                 AND NOT EXISTS (SELECT 1 FROM dbo.NguoiDung AS n WHERE n.ma_tai_khoan = t.ma_tai_khoan)');
        EXEC(N'ALTER TABLE dbo.TaiKhoan DROP COLUMN ho_ten, sdt, ngay_sinh, gioi_tinh, dia_chi');
    END;

    COMMIT TRANSACTION;
    PRINT N'Đã bảo đảm bảng dbo.NguoiDung và bỏ cột hồ sơ cũ khỏi dbo.TaiKhoan.';
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
