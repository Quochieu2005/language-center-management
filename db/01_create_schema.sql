:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

/*
    Chạy riêng trong từng CSDL QLTTNN_Q1, QLTTNN_Q7 và QLTTNN_TD.
    Bật SQLCMD Mode trong SSMS. Script chỉ dành cho CSDL mới/chưa có bảng.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_ID(DB_NAME()) <= 4
BEGIN
    ;THROW 51000, N'Không chạy schema trong system database.', 1;
END;

IF EXISTS (SELECT 1 FROM sys.tables WHERE schema_id = SCHEMA_ID(N'dbo'))
BEGIN
    ;THROW 51001, N'Database đã có bảng dbo. Script schema chỉ chạy trên database mới.', 1;
END;

BEGIN TRY
    BEGIN TRANSACTION;

    /* Danh mục nhân bản: mọi site có cùng khóa và cùng nội dung. */
    CREATE TABLE dbo.CoSo
    (
        ma_co_so       VARCHAR(10)    NOT NULL,
        slug           VARCHAR(120)   NOT NULL,
        ten_co_so      NVARCHAR(100)  NOT NULL,
        dia_chi        NVARCHAR(300)  NULL,
        sdt            VARCHAR(20)    NULL,
        trang_thai     VARCHAR(20)    NOT NULL CONSTRAINT DF_CoSo_trang_thai DEFAULT ('chuan_bi'),
        phien_ban      BIGINT         NOT NULL CONSTRAINT DF_CoSo_phien_ban DEFAULT (1),
        cap_nhat_luc   DATETIME2(0)   NOT NULL CONSTRAINT DF_CoSo_cap_nhat_luc DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT PK_CoSo PRIMARY KEY (ma_co_so),
        CONSTRAINT UQ_CoSo_slug UNIQUE (slug),
        CONSTRAINT CK_CoSo_trang_thai CHECK (trang_thai IN ('chuan_bi', 'hoat_dong', 'dong_cua')),
        CONSTRAINT CK_CoSo_phien_ban CHECK (phien_ban > 0)
    );

    CREATE TABLE dbo.MonHoc
    (
        ma_mon         VARCHAR(30)    NOT NULL,
        slug           VARCHAR(120)   NOT NULL,
        ten_mon        NVARCHAR(100)  NOT NULL,
        mo_ta          NVARCHAR(500)  NULL,
        phien_ban      BIGINT         NOT NULL CONSTRAINT DF_MonHoc_phien_ban DEFAULT (1),
        cap_nhat_luc   DATETIME2(0)   NOT NULL CONSTRAINT DF_MonHoc_cap_nhat_luc DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT PK_MonHoc PRIMARY KEY (ma_mon),
        CONSTRAINT UQ_MonHoc_slug UNIQUE (slug),
        CONSTRAINT CK_MonHoc_phien_ban CHECK (phien_ban > 0)
    );

    CREATE TABLE dbo.KhoaHoc
    (
        ma_khoa_hoc    VARCHAR(30)    NOT NULL,
        slug           VARCHAR(160)   NOT NULL,
        ma_mon         VARCHAR(30)    NOT NULL,
        ten_khoa_hoc   NVARCHAR(120)  NOT NULL,
        trinh_do       NVARCHAR(30)   NOT NULL,
        so_buoi        SMALLINT       NOT NULL,
        hoc_phi_chuan  DECIMAL(18, 0) NOT NULL,
        phien_ban      BIGINT         NOT NULL CONSTRAINT DF_KhoaHoc_phien_ban DEFAULT (1),
        cap_nhat_luc   DATETIME2(0)   NOT NULL CONSTRAINT DF_KhoaHoc_cap_nhat_luc DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT PK_KhoaHoc PRIMARY KEY (ma_khoa_hoc),
        CONSTRAINT UQ_KhoaHoc_slug UNIQUE (slug),
        CONSTRAINT FK_KhoaHoc_MonHoc FOREIGN KEY (ma_mon) REFERENCES dbo.MonHoc(ma_mon),
        CONSTRAINT CK_KhoaHoc_so_buoi CHECK (so_buoi > 0),
        CONSTRAINT CK_KhoaHoc_hoc_phi CHECK (hoc_phi_chuan >= 0),
        CONSTRAINT CK_KhoaHoc_phien_ban CHECK (phien_ban > 0)
    );

    /* Tài khoản nhân bản; mật khẩu lưu dạng băm, subject Google/Facebook cùng dòng. */
    CREATE TABLE dbo.TaiKhoan
    (
        ma_tai_khoan             VARCHAR(24)    NOT NULL,
        slug                     VARCHAR(120)   NOT NULL,
        ten_dang_nhap            NVARCHAR(100)  NOT NULL,
        email                    NVARCHAR(254)  NOT NULL,
        mat_khau                 NVARCHAR(255)  NOT NULL,
        google_subject           NVARCHAR(255)  NULL,
        facebook_subject         NVARCHAR(255)  NULL,
        vai_tro                  VARCHAR(20)    NOT NULL,
        ma_co_so                 VARCHAR(10)    NULL,
        trang_thai               BIT            NOT NULL CONSTRAINT DF_TaiKhoan_trang_thai DEFAULT (1), -- 1 = active, 0 = inactive
        bat_buoc_doi_mat_khau    BIT            NOT NULL CONSTRAINT DF_TaiKhoan_bat_buoc_doi DEFAULT (0),
        ngay_tao                 DATETIME2(0)   NOT NULL CONSTRAINT DF_TaiKhoan_ngay_tao DEFAULT (SYSUTCDATETIME()),
        ngay_doi_mat_khau_cuoi   DATETIME2(0)   NULL,
        phien_ban                BIGINT         NOT NULL CONSTRAINT DF_TaiKhoan_phien_ban DEFAULT (1),
        cap_nhat_luc             DATETIME2(0)   NOT NULL CONSTRAINT DF_TaiKhoan_cap_nhat_luc DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT PK_TaiKhoan PRIMARY KEY (ma_tai_khoan),
        CONSTRAINT UQ_TaiKhoan_slug UNIQUE (slug),
        CONSTRAINT UQ_TaiKhoan_ten_dang_nhap UNIQUE (ten_dang_nhap),
        CONSTRAINT UQ_TaiKhoan_email UNIQUE (email),
        CONSTRAINT UQ_TaiKhoan_ma_va_co_so UNIQUE (ma_tai_khoan, ma_co_so),
        CONSTRAINT CK_TaiKhoan_google_subject CHECK
            (google_subject IS NULL OR LEN(LTRIM(RTRIM(google_subject))) > 0),
        CONSTRAINT CK_TaiKhoan_facebook_subject CHECK
            (facebook_subject IS NULL OR LEN(LTRIM(RTRIM(facebook_subject))) > 0),
        CONSTRAINT FK_TaiKhoan_CoSo FOREIGN KEY (ma_co_so) REFERENCES dbo.CoSo(ma_co_so),
        CONSTRAINT CK_TaiKhoan_vai_tro CHECK (vai_tro IN ('admin_big', 'nhan_vien', 'giao_vien', 'hoc_vien')),
        CONSTRAINT CK_TaiKhoan_pham_vi CHECK
            ((vai_tro = 'admin_big' AND ma_co_so IS NULL) OR (vai_tro <> 'admin_big' AND ma_co_so IS NOT NULL)),
        CONSTRAINT CK_TaiKhoan_phien_ban CHECK (phien_ban > 0)
    );

    CREATE UNIQUE INDEX UX_TaiKhoan_google_subject
        ON dbo.TaiKhoan (google_subject)
        WHERE google_subject IS NOT NULL;

    CREATE UNIQUE INDEX UX_TaiKhoan_facebook_subject
        ON dbo.TaiKhoan (facebook_subject)
        WHERE facebook_subject IS NOT NULL;

    /* Session registry and hashed login attempts are site-local security state. */
    CREATE TABLE dbo.PhienDangNhap
    (
        ma_phien                 UNIQUEIDENTIFIER NOT NULL,
        ma_tai_khoan             VARCHAR(24)      NOT NULL,
        phien_ban_tai_khoan      BIGINT           NOT NULL,
        token_bam                CHAR(64)         NOT NULL,
        tao_luc_utc              DATETIME2(3)     NOT NULL CONSTRAINT DF_PhienDangNhap_tao DEFAULT (SYSUTCDATETIME()),
        hoat_dong_cuoi_utc       DATETIME2(3)     NOT NULL CONSTRAINT DF_PhienDangNhap_hoat_dong DEFAULT (SYSUTCDATETIME()),
        het_han_utc              DATETIME2(3)     NOT NULL,
        thu_hoi_luc_utc          DATETIME2(3)     NULL,
        CONSTRAINT PK_PhienDangNhap PRIMARY KEY (ma_phien),
        CONSTRAINT UQ_PhienDangNhap_token_bam UNIQUE (token_bam),
        CONSTRAINT FK_PhienDangNhap_TaiKhoan FOREIGN KEY (ma_tai_khoan) REFERENCES dbo.TaiKhoan(ma_tai_khoan),
        CONSTRAINT CK_PhienDangNhap_phien_ban CHECK (phien_ban_tai_khoan > 0),
        CONSTRAINT CK_PhienDangNhap_thoi_gian CHECK (het_han_utc > hoat_dong_cuoi_utc)
    );

    CREATE INDEX IX_PhienDangNhap_tai_khoan_hieu_luc
        ON dbo.PhienDangNhap (ma_tai_khoan, het_han_utc)
        INCLUDE (thu_hoi_luc_utc, phien_ban_tai_khoan);

    CREATE TABLE dbo.SuKienDangNhap
    (
        ma_su_kien       UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_SuKienDangNhap_id DEFAULT (NEWID()),
        dinh_danh_bam    CHAR(64)         NOT NULL,
        ip_bam           CHAR(64)         NOT NULL,
        ket_qua          VARCHAR(20)      NOT NULL,
        thoi_diem_utc    DATETIME2(3)     NOT NULL CONSTRAINT DF_SuKienDangNhap_thoi_diem DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT PK_SuKienDangNhap PRIMARY KEY (ma_su_kien),
        CONSTRAINT CK_SuKienDangNhap_ket_qua CHECK (ket_qua IN ('thanh_cong', 'that_bai'))
    );

    CREATE INDEX IX_SuKienDangNhap_ip_thoi_diem
        ON dbo.SuKienDangNhap (ip_bam, thoi_diem_utc);
    CREATE INDEX IX_SuKienDangNhap_dinh_danh_ip_ket_qua_thoi_diem
        ON dbo.SuKienDangNhap (dinh_danh_bam, ip_bam, ket_qua, thoi_diem_utc);

    EXEC sys.sp_executesql N'
        CREATE TRIGGER dbo.TR_SuKienDangNhap_AppendOnly
        ON dbo.SuKienDangNhap
        INSTEAD OF UPDATE, DELETE
        AS
        BEGIN
            SET NOCOUNT ON;
            ;THROW 51033, ''SuKienDangNhap chỉ được thêm mới.'', 1;
        END;';

    /* Hồ sơ riêng theo site. ma_co_so trên bảng con là khóa phân mảnh. */
    CREATE TABLE dbo.HocVien
    (
        ma_hoc_vien   VARCHAR(24)    NOT NULL,
        slug          VARCHAR(160)   NOT NULL,
        ma_co_so      VARCHAR(10)    NOT NULL,
        co_so_goc     VARCHAR(10)    NOT NULL,
        ma_tai_khoan  VARCHAR(24)    NULL,
        ho_ten        NVARCHAR(150)  NOT NULL,
        ngay_sinh     DATE           NULL,
        gioi_tinh     NVARCHAR(20)   NULL,
        sdt           VARCHAR(20)    NULL,
        email         NVARCHAR(254)  NULL,
        dia_chi       NVARCHAR(300)  NULL,
        ngay_nhap_hoc DATE           NOT NULL,
        trang_thai    VARCHAR(20)    NOT NULL CONSTRAINT DF_HocVien_trang_thai DEFAULT ('dang_hoc'),
        CONSTRAINT PK_HocVien PRIMARY KEY (ma_hoc_vien),
        CONSTRAINT UQ_HocVien_slug UNIQUE (slug),
        CONSTRAINT UQ_HocVien_ma_va_co_so UNIQUE (ma_hoc_vien, ma_co_so),
        CONSTRAINT FK_HocVien_CoSo FOREIGN KEY (ma_co_so) REFERENCES dbo.CoSo(ma_co_so),
        CONSTRAINT FK_HocVien_CoSoGoc FOREIGN KEY (co_so_goc) REFERENCES dbo.CoSo(ma_co_so),
        CONSTRAINT FK_HocVien_TaiKhoan FOREIGN KEY (ma_tai_khoan) REFERENCES dbo.TaiKhoan(ma_tai_khoan),
        CONSTRAINT CK_HocVien_trang_thai CHECK (trang_thai IN ('dang_hoc', 'bao_luu', 'da_chuyen_di', 'nghi_hoc'))
    );

    CREATE UNIQUE INDEX UX_HocVien_ma_tai_khoan
        ON dbo.HocVien (ma_tai_khoan)
        WHERE ma_tai_khoan IS NOT NULL;

    CREATE TABLE dbo.GiaoVien
    (
        ma_giao_vien  VARCHAR(24)    NOT NULL,
        ma_co_so      VARCHAR(10)    NOT NULL,
        ma_tai_khoan  VARCHAR(24)    NULL,
        ho_ten        NVARCHAR(150)  NOT NULL,
        sdt           VARCHAR(20)    NULL,
        email         NVARCHAR(254)  NULL,
        chuyen_mon    NVARCHAR(200)  NOT NULL,
        trang_thai    VARCHAR(20)    NOT NULL CONSTRAINT DF_GiaoVien_trang_thai DEFAULT ('dang_day'),
        CONSTRAINT PK_GiaoVien PRIMARY KEY (ma_giao_vien),
        CONSTRAINT UQ_GiaoVien_ma_va_co_so UNIQUE (ma_giao_vien, ma_co_so),
        CONSTRAINT FK_GiaoVien_CoSo FOREIGN KEY (ma_co_so) REFERENCES dbo.CoSo(ma_co_so),
        CONSTRAINT FK_GiaoVien_TaiKhoan FOREIGN KEY (ma_tai_khoan, ma_co_so)
            REFERENCES dbo.TaiKhoan(ma_tai_khoan, ma_co_so),
        CONSTRAINT CK_GiaoVien_trang_thai CHECK (trang_thai IN ('dang_day', 'tam_nghi', 'nghi_viec'))
    );

    CREATE TABLE dbo.NhanVien
    (
        ma_nhan_vien  VARCHAR(24)    NOT NULL,
        ma_co_so      VARCHAR(10)    NOT NULL,
        ma_tai_khoan  VARCHAR(24)    NULL,
        ho_ten        NVARCHAR(150)  NOT NULL,
        sdt           VARCHAR(20)    NULL,
        email         NVARCHAR(254)  NULL,
        chuc_vu       VARCHAR(30)    NOT NULL,
        trang_thai    VARCHAR(20)    NOT NULL CONSTRAINT DF_NhanVien_trang_thai DEFAULT ('dang_lam'),
        CONSTRAINT PK_NhanVien PRIMARY KEY (ma_nhan_vien),
        CONSTRAINT UQ_NhanVien_ma_va_co_so UNIQUE (ma_nhan_vien, ma_co_so),
        CONSTRAINT FK_NhanVien_CoSo FOREIGN KEY (ma_co_so) REFERENCES dbo.CoSo(ma_co_so),
        CONSTRAINT FK_NhanVien_TaiKhoan FOREIGN KEY (ma_tai_khoan, ma_co_so)
            REFERENCES dbo.TaiKhoan(ma_tai_khoan, ma_co_so),
        CONSTRAINT CK_NhanVien_chuc_vu CHECK
            (chuc_vu IN ('le_tan', 'tu_van', 'ke_toan', 'xep_lop', 'quan_ly_co_so')),
        CONSTRAINT CK_NhanVien_trang_thai CHECK (trang_thai IN ('dang_lam', 'nghi_viec'))
    );

    /* Hồ sơ quản trị site; dữ liệu đăng nhập và quyền vẫn thuộc TaiKhoan. */
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

    CREATE TABLE dbo.PhongHoc
    (
        ma_phong    VARCHAR(24)    NOT NULL,
        ma_co_so    VARCHAR(10)    NOT NULL,
        ten_phong   NVARCHAR(100)  NOT NULL,
        suc_chua    SMALLINT       NOT NULL,
        trang_thai  VARCHAR(20)    NOT NULL CONSTRAINT DF_PhongHoc_trang_thai DEFAULT ('hoat_dong'),
        CONSTRAINT PK_PhongHoc PRIMARY KEY (ma_phong),
        CONSTRAINT UQ_PhongHoc_ma_va_co_so UNIQUE (ma_phong, ma_co_so),
        CONSTRAINT FK_PhongHoc_CoSo FOREIGN KEY (ma_co_so) REFERENCES dbo.CoSo(ma_co_so),
        CONSTRAINT CK_PhongHoc_suc_chua CHECK (suc_chua > 0),
        CONSTRAINT CK_PhongHoc_trang_thai CHECK (trang_thai IN ('hoat_dong', 'bao_tri'))
    );

    CREATE TABLE dbo.LopHoc
    (
        ma_lop            VARCHAR(24)    NOT NULL,
        ma_co_so          VARCHAR(10)    NOT NULL,
        ma_khoa_hoc       VARCHAR(30)    NOT NULL,
        ma_giao_vien      VARCHAR(24)    NOT NULL,
        ma_phong          VARCHAR(24)    NOT NULL,
        ten_lop           NVARCHAR(120)  NOT NULL,
        si_so_toi_da      SMALLINT       NOT NULL,
        si_so_hien_tai    SMALLINT       NOT NULL CONSTRAINT DF_LopHoc_si_so DEFAULT (0),
        ngay_khai_giang   DATE           NOT NULL,
        ngay_ket_thuc     DATE           NULL,
        lich_hoc          NVARCHAR(100)  NOT NULL,
        gio_bat_dau       TIME(0)        NOT NULL,
        gio_ket_thuc      TIME(0)        NOT NULL,
        trang_thai        VARCHAR(20)    NOT NULL CONSTRAINT DF_LopHoc_trang_thai DEFAULT ('sap_mo'),
        CONSTRAINT PK_LopHoc PRIMARY KEY (ma_lop),
        CONSTRAINT UQ_LopHoc_ma_va_co_so UNIQUE (ma_lop, ma_co_so),
        CONSTRAINT FK_LopHoc_CoSo FOREIGN KEY (ma_co_so) REFERENCES dbo.CoSo(ma_co_so),
        CONSTRAINT FK_LopHoc_KhoaHoc FOREIGN KEY (ma_khoa_hoc) REFERENCES dbo.KhoaHoc(ma_khoa_hoc),
        CONSTRAINT FK_LopHoc_GiaoVienCungCoSo FOREIGN KEY (ma_giao_vien, ma_co_so)
            REFERENCES dbo.GiaoVien(ma_giao_vien, ma_co_so),
        CONSTRAINT FK_LopHoc_PhongCungCoSo FOREIGN KEY (ma_phong, ma_co_so)
            REFERENCES dbo.PhongHoc(ma_phong, ma_co_so),
        CONSTRAINT CK_LopHoc_si_so CHECK (si_so_toi_da > 0 AND si_so_hien_tai >= 0 AND si_so_hien_tai <= si_so_toi_da),
        CONSTRAINT CK_LopHoc_ngay CHECK (ngay_ket_thuc IS NULL OR ngay_ket_thuc >= ngay_khai_giang),
        CONSTRAINT CK_LopHoc_gio CHECK (gio_ket_thuc > gio_bat_dau),
        CONSTRAINT CK_LopHoc_trang_thai CHECK (trang_thai IN ('sap_mo', 'dang_hoc', 'ket_thuc', 'huy'))
    );

    CREATE TABLE dbo.BuoiHoc
    (
        ma_buoi       VARCHAR(24)    NOT NULL,
        ma_co_so      VARCHAR(10)    NOT NULL,
        ma_lop        VARCHAR(24)    NOT NULL,
        so_thu_tu     SMALLINT       NOT NULL,
        ngay_hoc      DATE           NOT NULL,
        gio_bat_dau   TIME(0)        NOT NULL,
        gio_ket_thuc  TIME(0)        NOT NULL,
        ma_phong      VARCHAR(24)    NOT NULL,
        ma_giao_vien  VARCHAR(24)    NOT NULL,
        trang_thai    VARCHAR(20)    NOT NULL CONSTRAINT DF_BuoiHoc_trang_thai DEFAULT ('du_kien'),
        ghi_chu       NVARCHAR(500)  NULL,
        CONSTRAINT PK_BuoiHoc PRIMARY KEY (ma_buoi),
        CONSTRAINT UQ_BuoiHoc_ma_va_co_so UNIQUE (ma_buoi, ma_co_so),
        CONSTRAINT UQ_BuoiHoc_lop_thu_tu UNIQUE (ma_lop, so_thu_tu),
        CONSTRAINT FK_BuoiHoc_LopCungCoSo FOREIGN KEY (ma_lop, ma_co_so)
            REFERENCES dbo.LopHoc(ma_lop, ma_co_so),
        CONSTRAINT FK_BuoiHoc_PhongCungCoSo FOREIGN KEY (ma_phong, ma_co_so)
            REFERENCES dbo.PhongHoc(ma_phong, ma_co_so),
        CONSTRAINT FK_BuoiHoc_GiaoVienCungCoSo FOREIGN KEY (ma_giao_vien, ma_co_so)
            REFERENCES dbo.GiaoVien(ma_giao_vien, ma_co_so),
        CONSTRAINT CK_BuoiHoc_so_thu_tu CHECK (so_thu_tu > 0),
        CONSTRAINT CK_BuoiHoc_gio CHECK (gio_ket_thuc > gio_bat_dau),
        CONSTRAINT CK_BuoiHoc_trang_thai CHECK (trang_thai IN ('du_kien', 'da_hoc', 'nghi', 'doi_lich'))
    );

    CREATE TABLE dbo.DangKy
    (
        ma_dang_ky    VARCHAR(24)    NOT NULL,
        ma_co_so      VARCHAR(10)    NOT NULL,
        ma_hoc_vien   VARCHAR(24)    NOT NULL,
        ma_lop        VARCHAR(24)    NOT NULL,
        ngay_dang_ky  DATETIME2(0)   NOT NULL CONSTRAINT DF_DangKy_ngay DEFAULT (SYSUTCDATETIME()),
        trang_thai    VARCHAR(20)    NOT NULL CONSTRAINT DF_DangKy_trang_thai DEFAULT ('da_dang_ky'),
        CONSTRAINT PK_DangKy PRIMARY KEY (ma_dang_ky),
        CONSTRAINT UQ_DangKy_ma_va_co_so UNIQUE (ma_dang_ky, ma_co_so),
        CONSTRAINT UQ_DangKy_hoc_vien_lop UNIQUE (ma_hoc_vien, ma_lop),
        CONSTRAINT FK_DangKy_HocVienCungCoSo FOREIGN KEY (ma_hoc_vien, ma_co_so)
            REFERENCES dbo.HocVien(ma_hoc_vien, ma_co_so),
        CONSTRAINT FK_DangKy_LopCungCoSo FOREIGN KEY (ma_lop, ma_co_so)
            REFERENCES dbo.LopHoc(ma_lop, ma_co_so),
        CONSTRAINT CK_DangKy_trang_thai CHECK (trang_thai IN ('da_dang_ky', 'dang_hoc', 'hoan_thanh', 'huy', 'chuyen_di'))
    );

    CREATE TABLE dbo.HocPhi
    (
        ma_hoc_phi        VARCHAR(24)    NOT NULL,
        ma_co_so          VARCHAR(10)    NOT NULL,
        ma_dang_ky        VARCHAR(24)    NOT NULL,
        so_tien_phai_dong DECIMAL(18, 0) NOT NULL,
        giam_gia          DECIMAL(18, 0) NOT NULL CONSTRAINT DF_HocPhi_giam_gia DEFAULT (0),
        so_tien_da_dong   DECIMAL(18, 0) NOT NULL CONSTRAINT DF_HocPhi_da_dong DEFAULT (0),
        trang_thai        VARCHAR(20)    NOT NULL CONSTRAINT DF_HocPhi_trang_thai DEFAULT ('chua_dong'),
        CONSTRAINT PK_HocPhi PRIMARY KEY (ma_hoc_phi),
        CONSTRAINT UQ_HocPhi_dang_ky UNIQUE (ma_dang_ky),
        CONSTRAINT UQ_HocPhi_ma_va_co_so UNIQUE (ma_hoc_phi, ma_co_so),
        CONSTRAINT FK_HocPhi_DangKyCungCoSo FOREIGN KEY (ma_dang_ky, ma_co_so)
            REFERENCES dbo.DangKy(ma_dang_ky, ma_co_so),
        CONSTRAINT CK_HocPhi_so_tien CHECK
            (so_tien_phai_dong >= 0 AND giam_gia >= 0 AND so_tien_da_dong >= 0
             AND so_tien_da_dong <= so_tien_phai_dong - giam_gia),
        CONSTRAINT CK_HocPhi_giam_gia CHECK (giam_gia <= so_tien_phai_dong),
        CONSTRAINT CK_HocPhi_trang_thai CHECK (trang_thai IN ('chua_dong', 'dong_mot_phan', 'da_dong', 'hoan_tien'))
    );

    CREATE TABLE dbo.DotHocPhi
    (
        ma_dot_hoc_phi    VARCHAR(24)    NOT NULL,
        ma_co_so          VARCHAR(10)    NOT NULL,
        ma_hoc_phi        VARCHAR(24)    NOT NULL,
        so_thu_tu         SMALLINT       NOT NULL,
        ngay_den_han      DATE           NOT NULL,
        so_tien_phai_dong DECIMAL(18, 0) NOT NULL,
        so_tien_da_dong   DECIMAL(18, 0) NOT NULL CONSTRAINT DF_DotHocPhi_da_dong DEFAULT (0),
        trang_thai        VARCHAR(20)    NOT NULL CONSTRAINT DF_DotHocPhi_trang_thai DEFAULT ('chua_dong'),
        CONSTRAINT PK_DotHocPhi PRIMARY KEY (ma_dot_hoc_phi),
        CONSTRAINT UQ_DotHocPhi_hoc_phi_thu_tu UNIQUE (ma_hoc_phi, so_thu_tu),
        CONSTRAINT FK_DotHocPhi_HocPhiCungCoSo FOREIGN KEY (ma_hoc_phi, ma_co_so)
            REFERENCES dbo.HocPhi(ma_hoc_phi, ma_co_so),
        CONSTRAINT CK_DotHocPhi_so_thu_tu CHECK (so_thu_tu >= 1),
        CONSTRAINT CK_DotHocPhi_so_tien CHECK
            (so_tien_phai_dong >= 0 AND so_tien_da_dong >= 0 AND so_tien_da_dong <= so_tien_phai_dong),
        CONSTRAINT CK_DotHocPhi_trang_thai CHECK (trang_thai IN ('chua_dong', 'dong_mot_phan', 'da_dong'))
    );

    /* Đề nghị, quyết định và trạng thái điều phối chỉ tồn tại tại CSDL site nguồn. */
    CREATE TABLE dbo.GiaoDichChuyenCoSo
    (
        ma_chuyen               VARCHAR(24)    NOT NULL,
        ma_hoc_vien              VARCHAR(24)    NOT NULL,
        co_so_nguon              VARCHAR(10)    NOT NULL,
        co_so_dich               VARCHAR(10)    NOT NULL,
        trang_thai               VARCHAR(20)    NOT NULL CONSTRAINT DF_GiaoDichChuyenCoSo_trang_thai DEFAULT ('cho_duyet'),
        buoc_cuoi                 VARCHAR(30)    NOT NULL CONSTRAINT DF_GiaoDichChuyenCoSo_buoc DEFAULT ('cho_duyet'),
        khoa_chong_lap            UNIQUEIDENTIFIER NULL,
        ma_tai_khoan_de_nghi     VARCHAR(24)    NOT NULL,
        ma_tai_khoan_quyet_dinh  VARCHAR(24)    NULL,
        ly_do_de_nghi             NVARCHAR(500)  NOT NULL,
        ly_do_tu_choi             NVARCHAR(500)  NULL,
        ngay_tao                  DATETIME2(0)   NOT NULL CONSTRAINT DF_GiaoDichChuyenCoSo_ngay_tao DEFAULT (SYSUTCDATETIME()),
        ngay_quyet_dinh           DATETIME2(0)   NULL,
        cap_nhat_luc              DATETIME2(0)   NOT NULL CONSTRAINT DF_GiaoDichChuyenCoSo_cap_nhat DEFAULT (SYSUTCDATETIME()),
        loi_cuoi                  NVARCHAR(1000) NULL,
        phien_ban                 ROWVERSION     NOT NULL,
        khoa_chong_trung_chuyen  AS (CASE WHEN trang_thai IN ('cho_duyet', 'dang_xu_ly') THEN 'HV:' + ma_hoc_vien ELSE 'CC:' + ma_chuyen END) PERSISTED,
        CONSTRAINT PK_GiaoDichChuyenCoSo PRIMARY KEY (ma_chuyen),
        CONSTRAINT FK_GiaoDichChuyenCoSo_HocVienNguon FOREIGN KEY (ma_hoc_vien, co_so_nguon)
            REFERENCES dbo.HocVien(ma_hoc_vien, ma_co_so),
        CONSTRAINT FK_GiaoDichChuyenCoSo_CoSoNguon FOREIGN KEY (co_so_nguon) REFERENCES dbo.CoSo(ma_co_so),
        CONSTRAINT FK_GiaoDichChuyenCoSo_CoSoDich FOREIGN KEY (co_so_dich) REFERENCES dbo.CoSo(ma_co_so),
        CONSTRAINT FK_GiaoDichChuyenCoSo_TaiKhoanDeNghi FOREIGN KEY (ma_tai_khoan_de_nghi) REFERENCES dbo.TaiKhoan(ma_tai_khoan),
        CONSTRAINT FK_GiaoDichChuyenCoSo_TaiKhoanQuyetDinh FOREIGN KEY (ma_tai_khoan_quyet_dinh) REFERENCES dbo.TaiKhoan(ma_tai_khoan),
        CONSTRAINT CK_GiaoDichChuyenCoSo_khac_site CHECK (co_so_nguon <> co_so_dich),
        CONSTRAINT CK_GiaoDichChuyenCoSo_trang_thai CHECK (trang_thai IN ('cho_duyet', 'dang_xu_ly', 'tu_choi', 'hoan_tat', 'that_bai')),
        CONSTRAINT CK_GiaoDichChuyenCoSo_buoc CHECK (buoc_cuoi IN ('cho_duyet', 'da_tiep_nhan', 'da_tao_ho_so_dich', 'da_cap_nhat_nguon', 'hoan_tat', 'tu_choi')),
        CONSTRAINT CK_GiaoDichChuyenCoSo_quyet_dinh CHECK
        (
            (trang_thai = 'cho_duyet' AND buoc_cuoi = 'cho_duyet' AND ma_tai_khoan_quyet_dinh IS NULL AND ngay_quyet_dinh IS NULL AND ly_do_tu_choi IS NULL)
            OR (trang_thai = 'tu_choi' AND buoc_cuoi = 'tu_choi' AND ma_tai_khoan_quyet_dinh IS NOT NULL AND ngay_quyet_dinh IS NOT NULL AND NULLIF(LTRIM(RTRIM(ly_do_tu_choi)), N'') IS NOT NULL)
            OR (trang_thai IN ('dang_xu_ly', 'hoan_tat', 'that_bai') AND buoc_cuoi NOT IN ('cho_duyet', 'tu_choi') AND ma_tai_khoan_quyet_dinh IS NOT NULL AND ngay_quyet_dinh IS NOT NULL AND ly_do_tu_choi IS NULL)
        ),
        CONSTRAINT CK_GiaoDichChuyenCoSo_hoan_tat CHECK (trang_thai <> 'hoan_tat' OR buoc_cuoi = 'hoan_tat'),
        CONSTRAINT CK_GiaoDichChuyenCoSo_that_bai CHECK (trang_thai <> 'that_bai' OR buoc_cuoi = 'da_tiep_nhan')
    );

    CREATE TABLE dbo.LichSuChuyenCoSo
    (
        ma_su_kien               VARCHAR(24)    NOT NULL,
        ma_chuyen                VARCHAR(24)    NOT NULL,
        ma_hoc_vien               VARCHAR(24)    NOT NULL,
        co_so_nguon               VARCHAR(10)    NOT NULL,
        co_so_dich                VARCHAR(10)    NOT NULL,
        site_ghi                  VARCHAR(10)    NOT NULL,
        su_kien                   VARCHAR(30)    NOT NULL,
        thoi_diem                 DATETIME2(0)   NOT NULL CONSTRAINT DF_LichSuChuyenCoSo_thoi_diem DEFAULT (SYSUTCDATETIME()),
        ma_tai_khoan_thuc_hien   VARCHAR(24)    NULL,
        chi_tiet                  NVARCHAR(1000) NULL,
        CONSTRAINT PK_LichSuChuyenCoSo PRIMARY KEY (ma_su_kien),
        CONSTRAINT FK_LichSuChuyenCoSo_CoSoNguon FOREIGN KEY (co_so_nguon) REFERENCES dbo.CoSo(ma_co_so),
        CONSTRAINT FK_LichSuChuyenCoSo_CoSoDich FOREIGN KEY (co_so_dich) REFERENCES dbo.CoSo(ma_co_so),
        CONSTRAINT FK_LichSuChuyenCoSo_SiteGhi FOREIGN KEY (site_ghi) REFERENCES dbo.CoSo(ma_co_so),
        CONSTRAINT FK_LichSuChuyenCoSo_TaiKhoan FOREIGN KEY (ma_tai_khoan_thuc_hien) REFERENCES dbo.TaiKhoan(ma_tai_khoan),
        CONSTRAINT CK_LichSuChuyenCoSo_khac_site CHECK (co_so_nguon <> co_so_dich),
        CONSTRAINT CK_LichSuChuyenCoSo_su_kien CHECK (su_kien IN ('de_nghi', 'duyet', 'tu_choi', 'tao_ho_so_dich', 'xac_nhan_ho_so_dich', 'cap_nhat_ho_so_nguon', 'hoan_tat', 'that_bai', 'phuc_hoi'))
    );

    CREATE TABLE dbo.PhieuThu
    (
        ma_phieu       VARCHAR(24)    NOT NULL,
        ma_co_so       VARCHAR(10)    NOT NULL,
        ma_hoc_phi     VARCHAR(24)    NOT NULL,
        loai           VARCHAR(10)    NOT NULL,
        so_tien        DECIMAL(18, 0) NOT NULL,
        hinh_thuc      VARCHAR(20)    NOT NULL,
        ngay_thu       DATETIME2(0)   NOT NULL CONSTRAINT DF_PhieuThu_ngay DEFAULT (SYSUTCDATETIME()),
        ma_nhan_vien   VARCHAR(24)    NOT NULL,
        ghi_chu        NVARCHAR(500)  NULL,
        CONSTRAINT PK_PhieuThu PRIMARY KEY (ma_phieu),
        CONSTRAINT FK_PhieuThu_HocPhiCungCoSo FOREIGN KEY (ma_hoc_phi, ma_co_so)
            REFERENCES dbo.HocPhi(ma_hoc_phi, ma_co_so),
        CONSTRAINT FK_PhieuThu_NhanVienCungCoSo FOREIGN KEY (ma_nhan_vien, ma_co_so)
            REFERENCES dbo.NhanVien(ma_nhan_vien, ma_co_so),
        CONSTRAINT CK_PhieuThu_loai CHECK (loai IN ('thu', 'hoan')),
        CONSTRAINT CK_PhieuThu_so_tien CHECK (so_tien > 0),
        CONSTRAINT CK_PhieuThu_hinh_thuc CHECK (hinh_thuc IN ('tien_mat', 'chuyen_khoan', 'the'))
    );

    CREATE TABLE dbo.Diem
    (
        ma_diem             VARCHAR(24)    NOT NULL,
        ma_co_so            VARCHAR(10)    NOT NULL,
        ma_dang_ky          VARCHAR(24)    NOT NULL,
        loai_diem           VARCHAR(20)    NOT NULL,
        diem_so             DECIMAL(4, 2)  NOT NULL,
        ngay_nhap           DATETIME2(0)   NOT NULL CONSTRAINT DF_Diem_ngay DEFAULT (SYSUTCDATETIME()),
        ma_giao_vien_nhap   VARCHAR(24)    NOT NULL,
        CONSTRAINT PK_Diem PRIMARY KEY (ma_diem),
        CONSTRAINT UQ_Diem_dang_ky_loai UNIQUE (ma_dang_ky, loai_diem),
        CONSTRAINT FK_Diem_DangKyCungCoSo FOREIGN KEY (ma_dang_ky, ma_co_so)
            REFERENCES dbo.DangKy(ma_dang_ky, ma_co_so),
        CONSTRAINT FK_Diem_GiaoVienCungCoSo FOREIGN KEY (ma_giao_vien_nhap, ma_co_so)
            REFERENCES dbo.GiaoVien(ma_giao_vien, ma_co_so),
        CONSTRAINT CK_Diem_loai CHECK (loai_diem IN ('giua_ky', 'cuoi_ky', 'nghe', 'noi', 'doc', 'viet')),
        CONSTRAINT CK_Diem_so CHECK (diem_so >= 0 AND diem_so <= 10)
    );

    CREATE TABLE dbo.DiemDanh
    (
        ma_diem_danh       VARCHAR(24)    NOT NULL,
        ma_co_so           VARCHAR(10)    NOT NULL,
        ma_buoi            VARCHAR(24)    NOT NULL,
        ma_dang_ky         VARCHAR(24)    NOT NULL,
        trang_thai         VARCHAR(30)    NOT NULL,
        ghi_chu            NVARCHAR(500)  NULL,
        ma_tai_khoan_ghi   VARCHAR(24)    NOT NULL,
        CONSTRAINT PK_DiemDanh PRIMARY KEY (ma_diem_danh),
        CONSTRAINT UQ_DiemDanh_buoi_dang_ky UNIQUE (ma_buoi, ma_dang_ky),
        CONSTRAINT FK_DiemDanh_BuoiCungCoSo FOREIGN KEY (ma_buoi, ma_co_so)
            REFERENCES dbo.BuoiHoc(ma_buoi, ma_co_so),
        CONSTRAINT FK_DiemDanh_DangKyCungCoSo FOREIGN KEY (ma_dang_ky, ma_co_so)
            REFERENCES dbo.DangKy(ma_dang_ky, ma_co_so),
        CONSTRAINT FK_DiemDanh_TaiKhoan FOREIGN KEY (ma_tai_khoan_ghi) REFERENCES dbo.TaiKhoan(ma_tai_khoan),
        CONSTRAINT CK_DiemDanh_trang_thai CHECK (trang_thai IN ('co_mat', 'tre', 'vang_co_phep', 'vang_khong_phep'))
    );

    CREATE TABLE dbo.TokenDatLaiMatKhau
    (
        ma_token      VARCHAR(30)    NOT NULL,
        ma_tai_khoan  VARCHAR(24)    NOT NULL,
        token_bam     NVARCHAR(255)  NOT NULL,
        ngay_tao      DATETIME2(3)   NOT NULL CONSTRAINT DF_Token_ngay_tao DEFAULT (SYSUTCDATETIME()),
        het_han       DATETIME2(3)   NOT NULL,
        da_dung       BIT            NOT NULL CONSTRAINT DF_Token_da_dung DEFAULT (0),
        so_lan_sai    TINYINT        NOT NULL CONSTRAINT DF_Token_so_lan_sai DEFAULT (0),
        ip_yeu_cau    VARCHAR(45)    NULL,
        CONSTRAINT PK_TokenDatLaiMatKhau PRIMARY KEY (ma_token),
        CONSTRAINT UQ_TokenDatLaiMatKhau_token_bam UNIQUE (token_bam),
        CONSTRAINT FK_TokenDatLaiMatKhau_TaiKhoan FOREIGN KEY (ma_tai_khoan) REFERENCES dbo.TaiKhoan(ma_tai_khoan),
        CONSTRAINT CK_TokenDatLaiMatKhau_han CHECK (het_han > ngay_tao),
        CONSTRAINT CK_TokenDatLaiMatKhau_so_lan_sai CHECK (so_lan_sai <= 5)
    );

    /* Reset requests and OTP verification attempts are private coordinator state. */
    CREATE TABLE dbo.SuKienQuenMatKhau
    (
        ma_su_kien       UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_SuKienQuenMatKhau_id DEFAULT (NEWID()),
        dinh_danh_bam    CHAR(64)         NOT NULL,
        ip_bam           CHAR(64)         NOT NULL,
        ma_token         VARCHAR(30)      NULL,
        loai_su_kien     VARCHAR(20)      NOT NULL,
        thoi_diem_utc    DATETIME2(3)     NOT NULL CONSTRAINT DF_SuKienQuenMatKhau_thoi_diem DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT PK_SuKienQuenMatKhau PRIMARY KEY (ma_su_kien),
        CONSTRAINT CK_SuKienQuenMatKhau_loai CHECK (loai_su_kien IN ('yeu_cau', 'otp_sai', 'dat_lai'))
    );

    CREATE INDEX IX_SuKienQuenMatKhau_ip_thoi_diem
        ON dbo.SuKienQuenMatKhau (ip_bam, loai_su_kien, thoi_diem_utc);
    CREATE INDEX IX_SuKienQuenMatKhau_dinh_danh_ip_thoi_diem
        ON dbo.SuKienQuenMatKhau (dinh_danh_bam, ip_bam, loai_su_kien, thoi_diem_utc);
    CREATE INDEX IX_SuKienQuenMatKhau_token
        ON dbo.SuKienQuenMatKhau (ma_token, loai_su_kien, thoi_diem_utc)
        WHERE ma_token IS NOT NULL;

    EXEC sys.sp_executesql N'
        CREATE TRIGGER dbo.TR_SuKienQuenMatKhau_AppendOnly
        ON dbo.SuKienQuenMatKhau
        INSTEAD OF UPDATE, DELETE
        AS
        BEGIN
            SET NOCOUNT ON;
            ;THROW 51034, ''SuKienQuenMatKhau chỉ được thêm mới.'', 1;
        END;';

    CREATE TABLE dbo.GiaoDichDatLaiMatKhau
    (
        ma_giao_dich       UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_GiaoDichDatLaiMatKhau_id DEFAULT (NEWID()),
        ma_tai_khoan       VARCHAR(24)      NOT NULL,
        mat_khau_moi_bam   NVARCHAR(255)    NULL,
        trang_thai         VARCHAR(20)      NOT NULL CONSTRAINT DF_GiaoDichDatLaiMatKhau_trang_thai DEFAULT ('dang_xu_ly'),
        tao_luc_utc        DATETIME2(3)     NOT NULL CONSTRAINT DF_GiaoDichDatLaiMatKhau_tao DEFAULT (SYSUTCDATETIME()),
        cap_nhat_luc_utc   DATETIME2(3)     NOT NULL CONSTRAINT DF_GiaoDichDatLaiMatKhau_cap_nhat DEFAULT (SYSUTCDATETIME()),
        hoan_tat_luc_utc   DATETIME2(3)     NULL,
        CONSTRAINT PK_GiaoDichDatLaiMatKhau PRIMARY KEY (ma_giao_dich),
        CONSTRAINT FK_GiaoDichDatLaiMatKhau_TaiKhoan FOREIGN KEY (ma_tai_khoan) REFERENCES dbo.TaiKhoan(ma_tai_khoan),
        CONSTRAINT CK_GiaoDichDatLaiMatKhau_trang_thai CHECK (trang_thai IN ('dang_xu_ly', 'hoan_tat')),
        CONSTRAINT CK_GiaoDichDatLaiMatKhau_noi_dung CHECK
            ((trang_thai = 'dang_xu_ly' AND mat_khau_moi_bam IS NOT NULL AND hoan_tat_luc_utc IS NULL)
             OR (trang_thai = 'hoan_tat' AND mat_khau_moi_bam IS NULL AND hoan_tat_luc_utc IS NOT NULL))
    );

    CREATE UNIQUE INDEX UX_GiaoDichDatLaiMatKhau_dang_xu_ly
        ON dbo.GiaoDichDatLaiMatKhau (ma_tai_khoan)
        WHERE trang_thai = 'dang_xu_ly';
    CREATE INDEX IX_GiaoDichDatLaiMatKhau_trang_thai
        ON dbo.GiaoDichDatLaiMatKhau (trang_thai, tao_luc_utc)
        INCLUDE (ma_tai_khoan);

    CREATE TABLE dbo.NhatKyHeThong
    (
        ma_nhat_ky     VARCHAR(24)    NOT NULL,
        thoi_diem      DATETIME2(0)   NOT NULL CONSTRAINT DF_NhatKyHeThong_thoi_diem DEFAULT (SYSUTCDATETIME()),
        ma_co_so       VARCHAR(10)    NOT NULL,
        ma_tai_khoan   VARCHAR(24)    NULL,
        hanh_dong      VARCHAR(40)    NOT NULL,
        bang_tac_dong  VARCHAR(50)    NULL,
        ma_ban_ghi     VARCHAR(100)   NULL,
        du_lieu_cu     NVARCHAR(MAX)  NULL,
        du_lieu_moi    NVARCHAR(MAX)  NULL,
        ip             VARCHAR(45)    NULL,
        ket_qua        VARCHAR(20)    NOT NULL,
        ghi_chu        NVARCHAR(1000) NULL,
        CONSTRAINT PK_NhatKyHeThong PRIMARY KEY (ma_nhat_ky),
        CONSTRAINT FK_NhatKyHeThong_CoSo FOREIGN KEY (ma_co_so) REFERENCES dbo.CoSo(ma_co_so),
        CONSTRAINT FK_NhatKyHeThong_TaiKhoan FOREIGN KEY (ma_tai_khoan) REFERENCES dbo.TaiKhoan(ma_tai_khoan),
        CONSTRAINT CK_NhatKyHeThong_ket_qua CHECK (ket_qua IN ('thanh_cong', 'that_bai'))
    );

    CREATE TABLE dbo.NhatKyDongBo
    (
        ma_dong_bo      VARCHAR(24)    NOT NULL,
        thoi_diem       DATETIME2(0)   NOT NULL CONSTRAINT DF_NhatKyDongBo_thoi_diem DEFAULT (SYSUTCDATETIME()),
        bang            VARCHAR(50)    NOT NULL,
        ma_ban_ghi      VARCHAR(100)   NOT NULL,
        hanh_dong       VARCHAR(10)    NOT NULL,
        site_dich       VARCHAR(10)    NOT NULL,
        trang_thai      VARCHAR(20)    NOT NULL,
        thong_bao_loi   NVARCHAR(1000) NULL,
        CONSTRAINT PK_NhatKyDongBo PRIMARY KEY (ma_dong_bo),
        CONSTRAINT FK_NhatKyDongBo_CoSo FOREIGN KEY (site_dich) REFERENCES dbo.CoSo(ma_co_so),
        CONSTRAINT CK_NhatKyDongBo_hanh_dong CHECK (hanh_dong IN ('them', 'sua', 'xoa')),
        CONSTRAINT CK_NhatKyDongBo_trang_thai CHECK (trang_thai IN ('thanh_cong', 'that_bai'))
    );

    /* Sequence cấp số; Django/API thêm mã site và mã loại để tạo mã bản ghi. */
    CREATE SEQUENCE dbo.Seq_TK    AS BIGINT START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 999999 NO CYCLE;
    CREATE SEQUENCE dbo.Seq_AD    AS BIGINT START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 999999 NO CYCLE;
    CREATE SEQUENCE dbo.Seq_HV    AS BIGINT START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 999999 NO CYCLE;
    CREATE SEQUENCE dbo.Seq_GV    AS BIGINT START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 999999 NO CYCLE;
    CREATE SEQUENCE dbo.Seq_NV    AS BIGINT START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 999999 NO CYCLE;
    CREATE SEQUENCE dbo.Seq_PH    AS BIGINT START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 999999 NO CYCLE;
    CREATE SEQUENCE dbo.Seq_LH    AS BIGINT START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 999999 NO CYCLE;
    CREATE SEQUENCE dbo.Seq_BH    AS BIGINT START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 999999 NO CYCLE;
    CREATE SEQUENCE dbo.Seq_DK    AS BIGINT START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 999999 NO CYCLE;
    CREATE SEQUENCE dbo.Seq_HP    AS BIGINT START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 999999 NO CYCLE;
    CREATE SEQUENCE dbo.Seq_DH    AS BIGINT START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 999999 NO CYCLE;
    CREATE SEQUENCE dbo.Seq_PT    AS BIGINT START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 999999 NO CYCLE;
    CREATE SEQUENCE dbo.Seq_DM    AS BIGINT START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 999999 NO CYCLE;
    CREATE SEQUENCE dbo.Seq_DD    AS BIGINT START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 999999 NO CYCLE;
    CREATE SEQUENCE dbo.Seq_CC    AS BIGINT START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 999999 NO CYCLE;
    CREATE SEQUENCE dbo.Seq_LS    AS BIGINT START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 999999 NO CYCLE;
    CREATE SEQUENCE dbo.Seq_TOKEN AS BIGINT START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 999999 NO CYCLE;
    CREATE SEQUENCE dbo.Seq_NK    AS BIGINT START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 999999 NO CYCLE;
    CREATE SEQUENCE dbo.Seq_DB    AS BIGINT START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 999999 NO CYCLE;

    CREATE INDEX IX_HocVien_trang_thai ON dbo.HocVien(trang_thai, ho_ten);
    CREATE UNIQUE INDEX UX_GiaoVien_ma_tai_khoan ON dbo.GiaoVien(ma_tai_khoan) WHERE ma_tai_khoan IS NOT NULL;
    CREATE UNIQUE INDEX UX_NhanVien_ma_tai_khoan ON dbo.NhanVien(ma_tai_khoan) WHERE ma_tai_khoan IS NOT NULL;
    CREATE INDEX IX_LopHoc_trang_thai_ngay ON dbo.LopHoc(trang_thai, ngay_khai_giang);
    CREATE INDEX IX_DangKy_lop_trang_thai ON dbo.DangKy(ma_lop, trang_thai);
    CREATE INDEX IX_DangKy_hoc_vien ON dbo.DangKy(ma_hoc_vien);
    CREATE INDEX IX_BuoiHoc_lop_ngay ON dbo.BuoiHoc(ma_lop, ngay_hoc);
    CREATE INDEX IX_DotHocPhi_site_han ON dbo.DotHocPhi(ma_co_so, ngay_den_han, trang_thai);
    CREATE INDEX IX_PhieuThu_hoc_phi_ngay ON dbo.PhieuThu(ma_hoc_phi, ngay_thu);
    CREATE UNIQUE INDEX UX_GiaoDichChuyenCoSo_khoa_chong_lap
        ON dbo.GiaoDichChuyenCoSo(khoa_chong_lap)
        WHERE khoa_chong_lap IS NOT NULL;
    CREATE UNIQUE INDEX UX_GiaoDichChuyenCoSo_khoa_chong_trung
        ON dbo.GiaoDichChuyenCoSo(khoa_chong_trung_chuyen);
    CREATE INDEX IX_GiaoDichChuyenCoSo_hang_cho_duyet
        ON dbo.GiaoDichChuyenCoSo(trang_thai, ngay_tao)
        INCLUDE (ma_chuyen, ma_hoc_vien, co_so_nguon, co_so_dich, ma_tai_khoan_de_nghi)
        WHERE trang_thai = 'cho_duyet';
    CREATE INDEX IX_GiaoDichChuyenCoSo_phuc_hoi
        ON dbo.GiaoDichChuyenCoSo(trang_thai, cap_nhat_luc)
        INCLUDE (ma_hoc_vien, co_so_nguon, co_so_dich, buoc_cuoi);
    CREATE INDEX IX_LichSuChuyenCoSo_ma_chuyen_thoi_diem
        ON dbo.LichSuChuyenCoSo(ma_chuyen, thoi_diem);
    CREATE INDEX IX_NhatKyHeThong_thoi_diem ON dbo.NhatKyHeThong(thoi_diem DESC);

    /* Nhật ký phân tán chỉ được thêm, không sửa/xóa. */
    EXEC sys.sp_executesql N'
        CREATE TRIGGER dbo.TR_LichSuChuyenCoSo_AppendOnly
        ON dbo.LichSuChuyenCoSo
        INSTEAD OF UPDATE, DELETE
        AS
        BEGIN
            SET NOCOUNT ON;
            ;THROW 51030, ''LichSuChuyenCoSo chỉ được thêm mới.'', 1;
        END;';

    EXEC sys.sp_executesql N'
        CREATE TRIGGER dbo.TR_NhatKyHeThong_AppendOnly
        ON dbo.NhatKyHeThong
        INSTEAD OF UPDATE, DELETE
        AS
        BEGIN
            SET NOCOUNT ON;
            ;THROW 51031, ''NhatKyHeThong chỉ được thêm mới.'', 1;
        END;';

    EXEC sys.sp_executesql N'
        CREATE TRIGGER dbo.TR_NhatKyDongBo_AppendOnly
        ON dbo.NhatKyDongBo
        INSTEAD OF UPDATE, DELETE
        AS
        BEGIN
            SET NOCOUNT ON;
            ;THROW 51032, ''NhatKyDongBo chỉ được thêm mới.'', 1;
        END;';

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
