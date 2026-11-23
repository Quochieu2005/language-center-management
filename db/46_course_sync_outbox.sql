-- Run once on the database selected by AUTH_SESSION_SITE_CODE.
-- This stores coordinator metadata only; KhoaHoc business rows remain in each site DB.
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.GiaoDichDongBoKhoaHoc', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.GiaoDichDongBoKhoaHoc (
        ma_giao_dich char(64) NOT NULL CONSTRAINT PK_GiaoDichDongBoKhoaHoc PRIMARY KEY,
        ma_tai_khoan varchar(24) NOT NULL,
        hanh_dong varchar(10) NOT NULL,
        slug varchar(160) NOT NULL,
        ma_khoa_hoc varchar(30) NULL,
        request_hash char(64) NOT NULL,
        du_lieu_truoc nvarchar(max) NULL,
        du_lieu_moi nvarchar(max) NOT NULL,
        site_muc_tieu nvarchar(max) NOT NULL,
        site_cho_dong_bo nvarchar(max) NOT NULL,
        trang_thai varchar(20) NOT NULL CONSTRAINT DF_GiaoDichDongBoKhoaHoc_trang_thai DEFAULT ('cho_dong_bo'),
        loi nvarchar(500) NULL,
        tao_luc_utc datetime2(3) NOT NULL CONSTRAINT DF_GiaoDichDongBoKhoaHoc_tao_luc DEFAULT (SYSUTCDATETIME()),
        cap_nhat_luc_utc datetime2(3) NOT NULL CONSTRAINT DF_GiaoDichDongBoKhoaHoc_cap_nhat_luc DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT CK_GiaoDichDongBoKhoaHoc_hanh_dong CHECK (hanh_dong IN ('tao', 'sua', 'xoa')),
        CONSTRAINT CK_GiaoDichDongBoKhoaHoc_trang_thai CHECK (trang_thai IN ('cho_dong_bo', 'hoan_tat', 'can_doi_soat')),
        CONSTRAINT CK_GiaoDichDongBoKhoaHoc_json CHECK (
            ISJSON(du_lieu_moi) = 1 AND ISJSON(site_muc_tieu) = 1 AND ISJSON(site_cho_dong_bo) = 1
            AND (du_lieu_truoc IS NULL OR ISJSON(du_lieu_truoc) = 1)
        )
    );
    CREATE INDEX IX_GiaoDichDongBoKhoaHoc_retry
        ON dbo.GiaoDichDongBoKhoaHoc(trang_thai, tao_luc_utc)
        INCLUDE (ma_giao_dich, hanh_dong, slug, ma_khoa_hoc);
END;
GO
