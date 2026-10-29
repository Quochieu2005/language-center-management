:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

/*
    Chạy ở SQLCMD Mode một lần trên từng CSDL site: QLTTNN_Q1, QLTTNN_Q7, QLTTNN_TD.
    Gộp bốn loại nhật ký vào dbo.Logs; giữ lại các dòng lịch sử cũ trước khi xóa bảng nguồn.
    Bỏ trạng thái đọc thông báo theo yêu cầu: không lưu tài khoản nào đã đọc thông báo nào.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_PADDING ON;
SET ANSI_WARNINGS ON;
SET ARITHABORT ON;
SET CONCAT_NULL_YIELDS_NULL ON;

IF DB_ID(DB_NAME()) <= 4
    THROW 51260, N'Hãy chọn một CSDL site, không chạy trong system database.', 1;
IF OBJECT_ID(N'dbo.CoSo', N'U') IS NULL OR OBJECT_ID(N'dbo.TaiKhoan', N'U') IS NULL
    THROW 51261, N'Thiếu bảng CoSo hoặc TaiKhoan; hãy cài schema trước.', 1;
GO

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.Logs', N'U') IS NULL
    BEGIN
        CREATE TABLE dbo.Logs
        (
            ma_log            NVARCHAR(120)  NOT NULL,
            loai_log          VARCHAR(24)    NOT NULL,
            thoi_diem_utc     DATETIME2(3)   NOT NULL CONSTRAINT DF_Logs_thoi_diem DEFAULT (SYSUTCDATETIME()),
            ma_co_so          VARCHAR(10)    NULL,
            ma_tai_khoan      VARCHAR(24)    NULL,
            hanh_dong         VARCHAR(50)    NULL,
            bang_tac_dong     VARCHAR(50)    NULL,
            ma_ban_ghi        VARCHAR(100)   NULL,
            du_lieu_cu        NVARCHAR(MAX)  NULL,
            du_lieu_moi       NVARCHAR(MAX)  NULL,
            ip                VARCHAR(45)    NULL,
            dinh_danh_bam     CHAR(64)       NULL,
            ip_bam            CHAR(64)       NULL,
            ket_qua           VARCHAR(20)    NULL,
            site_dich         VARCHAR(10)    NULL,
            ma_token          VARCHAR(30)    NULL,
            ghi_chu           NVARCHAR(1000) NULL,
            thong_bao_loi     NVARCHAR(1000) NULL,
            CONSTRAINT PK_Logs PRIMARY KEY (ma_log),
            CONSTRAINT CK_Logs_loai CHECK (loai_log IN ('login', 'password_reset', 'system', 'sync')),
            CONSTRAINT CK_Logs_ket_qua CHECK (ket_qua IS NULL OR ket_qua IN ('thanh_cong', 'that_bai'))
        );
    END;

    IF OBJECT_ID(N'dbo.TR_Logs_AppendOnly', N'TR') IS NULL
        EXEC sys.sp_executesql N'
            CREATE TRIGGER dbo.TR_Logs_AppendOnly
            ON dbo.Logs
            AFTER UPDATE, DELETE
            AS
            BEGIN
                SET NOCOUNT ON;
                IF EXISTS (SELECT 1 FROM inserted)
                    THROW 51262, N''Logs không được cập nhật.'', 1;
                IF EXISTS (SELECT 1 FROM deleted)
                   AND ISNULL(TRY_CONVERT(bit, SESSION_CONTEXT(N''qlttnn_student_purge'')), 0) <> 1
                    THROW 51263, N''Chỉ luồng xóa dữ liệu học viên được xóa log liên quan.'', 1;
            END;';

    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.Logs') AND name = N'IX_Logs_login_ip_time')
        CREATE INDEX IX_Logs_login_ip_time
            ON dbo.Logs (loai_log, ip_bam, thoi_diem_utc)
            INCLUDE (dinh_danh_bam, ket_qua)
            WHERE loai_log = 'login';
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.Logs') AND name = N'IX_Logs_login_identity_ip_result_time')
        CREATE INDEX IX_Logs_login_identity_ip_result_time
            ON dbo.Logs (loai_log, ip_bam, dinh_danh_bam, ket_qua, thoi_diem_utc)
            WHERE loai_log = 'login';
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.Logs') AND name = N'IX_Logs_reset_ip_action_time')
        CREATE INDEX IX_Logs_reset_ip_action_time
            ON dbo.Logs (loai_log, ip_bam, hanh_dong, thoi_diem_utc)
            WHERE loai_log = 'password_reset';
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.Logs') AND name = N'IX_Logs_reset_identity_action_time')
        CREATE INDEX IX_Logs_reset_identity_action_time
            ON dbo.Logs (loai_log, dinh_danh_bam, hanh_dong, thoi_diem_utc)
            WHERE loai_log = 'password_reset';
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.Logs') AND name = N'IX_Logs_reset_token_action_time')
        CREATE INDEX IX_Logs_reset_token_action_time
            ON dbo.Logs (loai_log, ma_token, hanh_dong, thoi_diem_utc)
            WHERE loai_log = 'password_reset' AND ma_token IS NOT NULL;
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.Logs') AND name = N'IX_Logs_sync_lookup')
        CREATE INDEX IX_Logs_sync_lookup
            ON dbo.Logs (loai_log, bang_tac_dong, ma_ban_ghi, site_dich, hanh_dong, ket_qua)
            WHERE loai_log = 'sync';
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.Logs') AND name = N'IX_Logs_system_lookup')
        CREATE INDEX IX_Logs_system_lookup
            ON dbo.Logs (loai_log, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong, ma_ban_ghi, ket_qua)
            WHERE loai_log = 'system';

    IF OBJECT_ID(N'dbo.SuKienDangNhap', N'U') IS NOT NULL
        EXEC sys.sp_executesql N'
            INSERT INTO dbo.Logs
                (ma_log, loai_log, thoi_diem_utc, hanh_dong, dinh_danh_bam, ip_bam, ket_qua)
            SELECT CONVERT(NVARCHAR(120), e.ma_su_kien), ''login'', e.thoi_diem_utc,
                   ''dang_nhap'', e.dinh_danh_bam, e.ip_bam, e.ket_qua
            FROM dbo.SuKienDangNhap AS e
            WHERE NOT EXISTS
                (SELECT 1 FROM dbo.Logs AS l
                 WHERE l.ma_log = CONVERT(NVARCHAR(120), e.ma_su_kien) AND l.loai_log = ''login'');';

    IF OBJECT_ID(N'dbo.SuKienQuenMatKhau', N'U') IS NOT NULL
        EXEC sys.sp_executesql N'
            INSERT INTO dbo.Logs
                (ma_log, loai_log, thoi_diem_utc, hanh_dong, dinh_danh_bam, ip_bam, ma_token, ket_qua)
            SELECT CONVERT(NVARCHAR(120), e.ma_su_kien), ''password_reset'', e.thoi_diem_utc,
                   e.loai_su_kien, e.dinh_danh_bam, e.ip_bam, e.ma_token,
                   CASE WHEN e.loai_su_kien = ''otp_sai'' THEN ''that_bai'' ELSE ''thanh_cong'' END
            FROM dbo.SuKienQuenMatKhau AS e
            WHERE NOT EXISTS
                (SELECT 1 FROM dbo.Logs AS l
                 WHERE l.ma_log = CONVERT(NVARCHAR(120), e.ma_su_kien) AND l.loai_log = ''password_reset'');';

    IF OBJECT_ID(N'dbo.NhatKyHeThong', N'U') IS NOT NULL
        EXEC sys.sp_executesql N'
            INSERT INTO dbo.Logs
                (ma_log, loai_log, thoi_diem_utc, ma_co_so, ma_tai_khoan, hanh_dong,
                 bang_tac_dong, ma_ban_ghi, du_lieu_cu, du_lieu_moi, ip, ket_qua, ghi_chu)
            SELECT CONVERT(NVARCHAR(120), e.ma_nhat_ky), ''system'', e.thoi_diem,
                   e.ma_co_so, e.ma_tai_khoan, e.hanh_dong, e.bang_tac_dong,
                   e.ma_ban_ghi, e.du_lieu_cu, e.du_lieu_moi, e.ip, e.ket_qua, e.ghi_chu
            FROM dbo.NhatKyHeThong AS e
            WHERE NOT EXISTS
                (SELECT 1 FROM dbo.Logs AS l
                 WHERE l.ma_log = CONVERT(NVARCHAR(120), e.ma_nhat_ky) AND l.loai_log = ''system'');';

    IF OBJECT_ID(N'dbo.NhatKyDongBo', N'U') IS NOT NULL
        EXEC sys.sp_executesql N'
            INSERT INTO dbo.Logs
                (ma_log, loai_log, thoi_diem_utc, hanh_dong, bang_tac_dong,
                 ma_ban_ghi, site_dich, ket_qua, thong_bao_loi)
            SELECT CONVERT(NVARCHAR(120), e.ma_dong_bo), ''sync'', e.thoi_diem,
                   e.hanh_dong, e.bang, e.ma_ban_ghi, e.site_dich, e.trang_thai, e.thong_bao_loi
            FROM dbo.NhatKyDongBo AS e
            WHERE NOT EXISTS
                (SELECT 1 FROM dbo.Logs AS l
                 WHERE l.ma_log = CONVERT(NVARCHAR(120), e.ma_dong_bo) AND l.loai_log = ''sync'');';

    /* Chỉ bỏ bảng nguồn sau khi mọi dòng cũ đã có bản ghi tương ứng trong Logs. */
    IF OBJECT_ID(N'dbo.SuKienDangNhap', N'U') IS NOT NULL
        EXEC sys.sp_executesql N'
            IF EXISTS (SELECT 1 FROM dbo.SuKienDangNhap AS e
                       WHERE NOT EXISTS (SELECT 1 FROM dbo.Logs AS l
                         WHERE l.ma_log = CONVERT(NVARCHAR(120), e.ma_su_kien) AND l.loai_log = ''login''))
                THROW 51264, N''Không đủ dữ liệu đăng nhập đã chuyển sang Logs.'', 1;';
    IF OBJECT_ID(N'dbo.SuKienQuenMatKhau', N'U') IS NOT NULL
        EXEC sys.sp_executesql N'
            IF EXISTS (SELECT 1 FROM dbo.SuKienQuenMatKhau AS e
                       WHERE NOT EXISTS (SELECT 1 FROM dbo.Logs AS l
                         WHERE l.ma_log = CONVERT(NVARCHAR(120), e.ma_su_kien) AND l.loai_log = ''password_reset''))
                THROW 51265, N''Không đủ dữ liệu OTP đã chuyển sang Logs.'', 1;';
    IF OBJECT_ID(N'dbo.NhatKyHeThong', N'U') IS NOT NULL
        EXEC sys.sp_executesql N'
            IF EXISTS (SELECT 1 FROM dbo.NhatKyHeThong AS e
                       WHERE NOT EXISTS (SELECT 1 FROM dbo.Logs AS l
                         WHERE l.ma_log = CONVERT(NVARCHAR(120), e.ma_nhat_ky) AND l.loai_log = ''system''))
                THROW 51266, N''Không đủ nhật ký hệ thống đã chuyển sang Logs.'', 1;';
    IF OBJECT_ID(N'dbo.NhatKyDongBo', N'U') IS NOT NULL
        EXEC sys.sp_executesql N'
            IF EXISTS (SELECT 1 FROM dbo.NhatKyDongBo AS e
                       WHERE NOT EXISTS (SELECT 1 FROM dbo.Logs AS l
                         WHERE l.ma_log = CONVERT(NVARCHAR(120), e.ma_dong_bo) AND l.loai_log = ''sync''))
                THROW 51267, N''Không đủ nhật ký đồng bộ đã chuyển sang Logs.'', 1;';

    IF OBJECT_ID(N'dbo.SuKienDangNhap', N'U') IS NOT NULL DROP TABLE dbo.SuKienDangNhap;
    IF OBJECT_ID(N'dbo.SuKienQuenMatKhau', N'U') IS NOT NULL DROP TABLE dbo.SuKienQuenMatKhau;
    IF OBJECT_ID(N'dbo.NhatKyHeThong', N'U') IS NOT NULL DROP TABLE dbo.NhatKyHeThong;
    IF OBJECT_ID(N'dbo.NhatKyDongBo', N'U') IS NOT NULL DROP TABLE dbo.NhatKyDongBo;
    IF OBJECT_ID(N'dbo.TrangThaiDocThongBao', N'U') IS NOT NULL DROP TABLE dbo.TrangThaiDocThongBao;

    IF DATABASE_PRINCIPAL_ID(N'qlttnn_api') IS NOT NULL
        EXEC(N'DENY UPDATE ON OBJECT::dbo.Logs TO qlttnn_api');

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

SELECT DB_NAME() AS database_da_cap_nhat,
       OBJECT_ID(N'dbo.Logs', N'U') AS bang_logs,
       OBJECT_ID(N'dbo.SuKienDangNhap', N'U') AS bang_su_kien_dang_nhap,
       OBJECT_ID(N'dbo.SuKienQuenMatKhau', N'U') AS bang_su_kien_quen_mat_khau,
       OBJECT_ID(N'dbo.NhatKyHeThong', N'U') AS bang_nhat_ky_he_thong,
       OBJECT_ID(N'dbo.NhatKyDongBo', N'U') AS bang_nhat_ky_dong_bo,
       OBJECT_ID(N'dbo.TrangThaiDocThongBao', N'U') AS bang_trang_thai_doc_thong_bao;
SELECT loai_log, COUNT_BIG(*) AS so_dong
FROM dbo.Logs
GROUP BY loai_log
ORDER BY loai_log;
GO
