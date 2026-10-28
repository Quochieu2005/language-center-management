/*
    Run this script once on every site database: QLTTNN_Q1, QLTTNN_Q7, QLTTNN_TD.
    Notification events and read receipts remain site-local. There is no central
    business database and no cross-site foreign key.
*/
SET XACT_ABORT ON;
GO

IF OBJECT_ID(N'dbo.ThongBao', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ThongBao
    (
        slug             VARCHAR(120)   NOT NULL,
        event_key        VARCHAR(160)   NOT NULL,
        ma_co_so         VARCHAR(10)    NOT NULL,
        danh_muc         VARCHAR(30)    NOT NULL,
        muc_do           VARCHAR(12)    NOT NULL CONSTRAINT DF_ThongBao_muc_do DEFAULT ('info'),
        doi_tuong        VARCHAR(20)    NOT NULL CONSTRAINT DF_ThongBao_doi_tuong DEFAULT ('admin_all'),
        tieu_de          NVARCHAR(160)  NOT NULL,
        noi_dung         NVARCHAR(500)  NOT NULL,
        duong_dan        NVARCHAR(300)  NULL,
        tao_luc_utc      DATETIME2(3)   NOT NULL CONSTRAINT DF_ThongBao_tao_luc DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT PK_ThongBao PRIMARY KEY (slug),
        CONSTRAINT UQ_ThongBao_event_key UNIQUE (event_key),
        CONSTRAINT FK_ThongBao_CoSo FOREIGN KEY (ma_co_so) REFERENCES dbo.CoSo(ma_co_so),
        CONSTRAINT CK_ThongBao_danh_muc CHECK
            (danh_muc IN ('system', 'tuition', 'account', 'teacher', 'enrollment', 'class', 'grade', 'transfer', 'payment', 'security')),
        CONSTRAINT CK_ThongBao_muc_do CHECK (muc_do IN ('info', 'success', 'warning', 'critical')),
        CONSTRAINT CK_ThongBao_doi_tuong CHECK (doi_tuong IN ('admin_all', 'admin_big', 'admin_small'))
    );

    CREATE INDEX IX_ThongBao_site_created
        ON dbo.ThongBao (ma_co_so, tao_luc_utc DESC, slug DESC)
        INCLUDE (danh_muc, muc_do, doi_tuong, tieu_de, noi_dung, duong_dan);
END;
GO

IF OBJECT_ID(N'dbo.TrangThaiDocThongBao', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.TrangThaiDocThongBao
    (
        ma_tai_khoan    VARCHAR(24)   NOT NULL,
        slug            VARCHAR(120)  NOT NULL,
        da_doc_luc_utc  DATETIME2(3)  NOT NULL CONSTRAINT DF_TrangThaiDocThongBao_da_doc DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT PK_TrangThaiDocThongBao PRIMARY KEY (ma_tai_khoan, slug),
        CONSTRAINT FK_TrangThaiDocThongBao_TaiKhoan FOREIGN KEY (ma_tai_khoan)
            REFERENCES dbo.TaiKhoan(ma_tai_khoan),
        CONSTRAINT FK_TrangThaiDocThongBao_ThongBao FOREIGN KEY (slug)
            REFERENCES dbo.ThongBao(slug)
    );

    CREATE INDEX IX_TrangThaiDocThongBao_slug
        ON dbo.TrangThaiDocThongBao (slug, ma_tai_khoan);
END;
GO
