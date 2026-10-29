:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

/*
    Run in SQLCMD Mode once on each site database: QLTTNN_Q1, QLTTNN_Q7, QLTTNN_TD.
    Admin profiles live in dbo.Admin; authentication and active/inactive state live
    in dbo.TaiKhoan. Account creation/status APIs no longer require lifecycle tables.
    Transfer and password-reset coordinator tables are intentionally retained.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.TaiKhoan', N'U') IS NULL OR OBJECT_ID(N'dbo.CoSo', N'U') IS NULL
    THROW 51251, N'Thiếu dbo.TaiKhoan hoặc dbo.CoSo; hãy cài schema trước.', 1;
GO

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.Admin', N'U') IS NULL
    BEGIN
        CREATE TABLE dbo.Admin
        (
            ma_admin      VARCHAR(24)    NOT NULL,
            ma_tai_khoan  VARCHAR(24)    NOT NULL,
            ma_co_so      VARCHAR(10)    NULL,
            loai_admin    VARCHAR(20)    NOT NULL,
            ho_ten        NVARCHAR(150)  NOT NULL,
            sdt           VARCHAR(20)    NULL,
            trang_thai    BIT            NOT NULL CONSTRAINT DF_Admin_trang_thai DEFAULT (1),
            CONSTRAINT PK_Admin PRIMARY KEY (ma_admin),
            CONSTRAINT UQ_Admin_ma_tai_khoan UNIQUE (ma_tai_khoan),
            CONSTRAINT FK_Admin_TaiKhoan FOREIGN KEY (ma_tai_khoan)
                REFERENCES dbo.TaiKhoan(ma_tai_khoan),
            CONSTRAINT FK_Admin_CoSo FOREIGN KEY (ma_co_so)
                REFERENCES dbo.CoSo(ma_co_so),
            CONSTRAINT CK_Admin_loai CHECK (loai_admin IN ('admin_big', 'admin_small')),
            CONSTRAINT CK_Admin_pham_vi CHECK
                ((loai_admin = 'admin_big' AND ma_co_so IS NULL)
                 OR (loai_admin = 'admin_small' AND ma_co_so IS NOT NULL))
        );
        CREATE INDEX IX_Admin_co_so_trang_thai
            ON dbo.Admin (ma_co_so, loai_admin, trang_thai);
    END;

    IF OBJECT_ID(N'dbo.Seq_AD', N'SO') IS NULL
        EXEC(N'CREATE SEQUENCE dbo.Seq_AD AS BIGINT START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 999999 NO CYCLE;');

    /* Import Admin Big profile from replicated account rows. */
    INSERT INTO dbo.Admin
        (ma_admin, ma_tai_khoan, ma_co_so, loai_admin, ho_ten, sdt, trang_thai)
    SELECT t.ma_tai_khoan, t.ma_tai_khoan, NULL, 'admin_big', t.ten_dang_nhap, NULL,
           CASE WHEN LOWER(LTRIM(RTRIM(CONVERT(VARCHAR(20), t.trang_thai))))
                     IN ('1', 'true', 'active', 'hoat_dong') THEN 1 ELSE 0 END
    FROM dbo.TaiKhoan AS t
    WHERE t.vai_tro = 'admin_big'
      AND NOT EXISTS
          (SELECT 1 FROM dbo.Admin AS a WHERE a.ma_tai_khoan = t.ma_tai_khoan);

    /* Move site-manager profiles to Admin while preserving their existing IDs. */
    INSERT INTO dbo.Admin
        (ma_admin, ma_tai_khoan, ma_co_so, loai_admin, ho_ten, sdt, trang_thai)
    SELECT n.ma_nhan_vien, n.ma_tai_khoan, n.ma_co_so, 'admin_small', n.ho_ten, n.sdt,
           CASE WHEN n.trang_thai = 'dang_lam'
                     AND LOWER(LTRIM(RTRIM(CONVERT(VARCHAR(20), t.trang_thai))))
                         IN ('1', 'true', 'active', 'hoat_dong')
                THEN 1 ELSE 0 END
    FROM dbo.NhanVien AS n
    INNER JOIN dbo.TaiKhoan AS t ON t.ma_tai_khoan = n.ma_tai_khoan
    WHERE n.chuc_vu = 'quan_ly_co_so'
      AND NOT EXISTS
          (SELECT 1 FROM dbo.Admin AS a WHERE a.ma_tai_khoan = n.ma_tai_khoan);

    /* Keep NhanVien history and receipt references intact after the Admin copy is created. */
    IF OBJECT_ID(N'dbo.GiaoDichCapTaiKhoanHocVien', N'U') IS NOT NULL
        DROP TABLE dbo.GiaoDichCapTaiKhoanHocVien;
    IF OBJECT_ID(N'dbo.GiaoDichQuanLyGiaoVien', N'U') IS NOT NULL
        DROP TABLE dbo.GiaoDichQuanLyGiaoVien;
    IF OBJECT_ID(N'dbo.GiaoDichTaoAdminSmall', N'U') IS NOT NULL
        DROP TABLE dbo.GiaoDichTaoAdminSmall;
    IF OBJECT_ID(N'dbo.GiaoDichTrangThaiTaiKhoan', N'U') IS NOT NULL
        DROP TABLE dbo.GiaoDichTrangThaiTaiKhoan;
    IF OBJECT_ID(N'dbo.GiaoDichVoHieuHoaAdminSmall', N'U') IS NOT NULL
        DROP TABLE dbo.GiaoDichVoHieuHoaAdminSmall;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

SELECT DB_NAME() AS database_da_cap_nhat,
       OBJECT_ID(N'dbo.Admin', N'U') AS bang_admin,
       OBJECT_ID(N'dbo.GiaoDichCapTaiKhoanHocVien', N'U') AS bang_cap_tai_khoan_hoc_vien,
       OBJECT_ID(N'dbo.GiaoDichQuanLyGiaoVien', N'U') AS bang_quan_ly_giao_vien,
       OBJECT_ID(N'dbo.GiaoDichTaoAdminSmall', N'U') AS bang_tao_admin_small,
       OBJECT_ID(N'dbo.GiaoDichTrangThaiTaiKhoan', N'U') AS bang_trang_thai_tai_khoan,
       OBJECT_ID(N'dbo.GiaoDichVoHieuHoaAdminSmall', N'U') AS bang_vo_hieu_hoa_admin_small;
GO
