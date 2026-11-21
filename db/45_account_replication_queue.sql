-- Run only on the configured authentication authority (Q1 in this deployment).
-- The queue and its account mutation commit together. No passwords in the queue.
SET XACT_ABORT ON;
GO
IF OBJECT_ID(N'dbo.TrangThaiKhoEmail', N'U') IS NULL
    CREATE TABLE dbo.TrangThaiKhoEmail (
        id int PRIMARY KEY CHECK (id = 1),
        san_sang bit NOT NULL DEFAULT 0
    );
IF NOT EXISTS (SELECT 1 FROM dbo.TrangThaiKhoEmail WHERE id = 1)
    INSERT dbo.TrangThaiKhoEmail(id, san_sang) VALUES (1, 0);
GO
IF OBJECT_ID(N'dbo.DatChoEmailHocVien', N'U') IS NULL
    CREATE TABLE dbo.DatChoEmailHocVien (
        email_bam char(64) PRIMARY KEY,
        ma_co_so varchar(12) NOT NULL,
        ma_hoc_vien nvarchar(24) NULL,
        tao_luc_utc datetime2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
GO
IF OBJECT_ID(N'dbo.DongBoTaiKhoan', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.DongBoTaiKhoan (
        ma_su_kien bigint IDENTITY PRIMARY KEY,
        ma_tai_khoan nvarchar(24) NOT NULL,
        site_dich varchar(12) NOT NULL,
        tao_luc_utc datetime2 NOT NULL DEFAULT SYSUTCDATETIME(),
        thu_lai_luc_utc datetime2 NOT NULL DEFAULT SYSUTCDATETIME(),
        so_lan_thu int NOT NULL DEFAULT 0,
        loi varchar(64) NULL
    );
    CREATE INDEX IX_DongBoTaiKhoan_retry ON dbo.DongBoTaiKhoan(thu_lai_luc_utc, ma_su_kien);
END;
GO
CREATE OR ALTER TRIGGER dbo.TR_TaiKhoan_queue_replication
ON dbo.TaiKhoan AFTER INSERT, UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    INSERT dbo.DongBoTaiKhoan(ma_tai_khoan, site_dich)
    SELECT a.ma_tai_khoan, c.ma_co_so
    FROM (SELECT ma_tai_khoan FROM inserted UNION SELECT ma_tai_khoan FROM deleted) a
    CROSS JOIN dbo.CoSo c
    WHERE c.trang_thai = 'hoat_dong';
END;
GO
-- Seed the existing accounts without modifying them. A retry may safely enqueue twice.
INSERT dbo.DongBoTaiKhoan(ma_tai_khoan, site_dich)
SELECT a.ma_tai_khoan, c.ma_co_so
FROM dbo.TaiKhoan a CROSS JOIN dbo.CoSo c
WHERE c.trang_thai = 'hoat_dong'
  AND NOT EXISTS (SELECT 1 FROM dbo.DongBoTaiKhoan q
                  WHERE q.ma_tai_khoan = a.ma_tai_khoan AND q.site_dich = c.ma_co_so);
