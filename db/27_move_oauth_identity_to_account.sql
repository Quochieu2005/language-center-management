:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

/*
    Move active Google/Facebook identity subjects onto the existing TaiKhoan row.
    The migration is safe to rerun. It preserves revoked-link audit facts in Logs
    without copying provider subjects, then removes the obsolete link table.
    Run separately on every site database after Logs exists.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_ID(DB_NAME()) <= 4
    THROW 51271, N'Hãy chọn một CSDL site, không chạy trong system database.', 1;

IF OBJECT_ID(N'dbo.TaiKhoan', N'U') IS NULL
    THROW 51272, N'Thiếu dbo.TaiKhoan; hãy cài schema trước.', 1;

BEGIN TRY
    BEGIN TRANSACTION;

    IF COL_LENGTH(N'dbo.TaiKhoan', N'google_subject') IS NULL
        ALTER TABLE dbo.TaiKhoan ADD google_subject NVARCHAR(255) NULL;

    IF COL_LENGTH(N'dbo.TaiKhoan', N'facebook_subject') IS NULL
        ALTER TABLE dbo.TaiKhoan ADD facebook_subject NVARCHAR(255) NULL;

    IF EXISTS
    (
        SELECT 1 FROM dbo.TaiKhoan
        WHERE (google_subject IS NOT NULL AND LTRIM(RTRIM(google_subject)) = N'')
           OR (facebook_subject IS NOT NULL AND LTRIM(RTRIM(facebook_subject)) = N'')
    )
        THROW 51278, N'TaiKhoan có provider subject rỗng; cần đối soát trước khi tạo ràng buộc.', 1;

    IF NOT EXISTS
       (SELECT 1 FROM sys.check_constraints WHERE parent_object_id = OBJECT_ID(N'dbo.TaiKhoan')
        AND name = N'CK_TaiKhoan_google_subject')
        ALTER TABLE dbo.TaiKhoan WITH CHECK ADD CONSTRAINT CK_TaiKhoan_google_subject
            CHECK (google_subject IS NULL OR LEN(LTRIM(RTRIM(google_subject))) > 0);

    IF NOT EXISTS
       (SELECT 1 FROM sys.check_constraints WHERE parent_object_id = OBJECT_ID(N'dbo.TaiKhoan')
        AND name = N'CK_TaiKhoan_facebook_subject')
        ALTER TABLE dbo.TaiKhoan WITH CHECK ADD CONSTRAINT CK_TaiKhoan_facebook_subject
            CHECK (facebook_subject IS NULL OR LEN(LTRIM(RTRIM(facebook_subject))) > 0);

    IF OBJECT_ID(N'dbo.TaiKhoanLienKetOAuth', N'U') IS NOT NULL
    BEGIN
        IF COL_LENGTH(N'dbo.TaiKhoanLienKetOAuth', N'ma_lien_ket') IS NULL
           OR COL_LENGTH(N'dbo.TaiKhoanLienKetOAuth', N'ma_tai_khoan') IS NULL
           OR COL_LENGTH(N'dbo.TaiKhoanLienKetOAuth', N'nha_cung_cap') IS NULL
           OR COL_LENGTH(N'dbo.TaiKhoanLienKetOAuth', N'provider_subject') IS NULL
           OR COL_LENGTH(N'dbo.TaiKhoanLienKetOAuth', N'trang_thai') IS NULL
           OR COL_LENGTH(N'dbo.TaiKhoanLienKetOAuth', N'ngay_thu_hoi') IS NULL
           OR COL_LENGTH(N'dbo.TaiKhoanLienKetOAuth', N'cap_nhat_luc') IS NULL
            THROW 51273, N'Bảng OAuth cũ thiếu cột cần để chuyển dữ liệu; không có dữ liệu nào bị xóa.', 1;

        IF EXISTS
        (
            SELECT 1 FROM dbo.TaiKhoanLienKetOAuth
            WHERE nha_cung_cap NOT IN ('google', 'facebook')
               OR trang_thai NOT IN ('hoat_dong', 'da_thu_hoi')
               OR (trang_thai = 'hoat_dong' AND LTRIM(RTRIM(provider_subject)) = N'')
        )
            THROW 51274, N'Bảng OAuth cũ có nhà cung cấp, trạng thái hoặc subject không hợp lệ; cần đối soát trước.', 1;

        IF EXISTS
        (
            SELECT 1
            FROM dbo.TaiKhoanLienKetOAuth AS o
            INNER JOIN dbo.TaiKhoan AS a ON a.ma_tai_khoan = o.ma_tai_khoan
            WHERE o.trang_thai = 'hoat_dong'
              AND ((o.nha_cung_cap = 'google' AND a.google_subject IS NOT NULL
                    AND a.google_subject <> o.provider_subject)
                OR (o.nha_cung_cap = 'facebook' AND a.facebook_subject IS NOT NULL
                    AND a.facebook_subject <> o.provider_subject))
        )
            THROW 51275, N'TaiKhoan đã có provider subject khác với bảng OAuth cũ; dừng để tránh ghi đè.', 1;

        UPDATE a
        SET google_subject = o.provider_subject
        FROM dbo.TaiKhoan AS a
        INNER JOIN dbo.TaiKhoanLienKetOAuth AS o ON o.ma_tai_khoan = a.ma_tai_khoan
        WHERE o.nha_cung_cap = 'google'
          AND o.trang_thai = 'hoat_dong'
          AND a.google_subject IS NULL;

        UPDATE a
        SET facebook_subject = o.provider_subject
        FROM dbo.TaiKhoan AS a
        INNER JOIN dbo.TaiKhoanLienKetOAuth AS o ON o.ma_tai_khoan = a.ma_tai_khoan
        WHERE o.nha_cung_cap = 'facebook'
          AND o.trang_thai = 'hoat_dong'
          AND a.facebook_subject IS NULL;

        IF EXISTS
        (
            SELECT 1
            FROM dbo.TaiKhoanLienKetOAuth AS o
            LEFT JOIN dbo.TaiKhoan AS a ON a.ma_tai_khoan = o.ma_tai_khoan
            WHERE o.trang_thai = 'hoat_dong'
              AND (a.ma_tai_khoan IS NULL
                OR (o.nha_cung_cap = 'google' AND a.google_subject <> o.provider_subject)
                OR (o.nha_cung_cap = 'facebook' AND a.facebook_subject <> o.provider_subject))
        )
            THROW 51276, N'Có liên kết OAuth đang hoạt động chưa được chuyển đầy đủ; bảng cũ được giữ nguyên.', 1;

        IF EXISTS (SELECT 1 FROM dbo.TaiKhoanLienKetOAuth WHERE trang_thai = 'da_thu_hoi')
        BEGIN
            IF OBJECT_ID(N'dbo.Logs', N'U') IS NULL
               OR COL_LENGTH(N'dbo.Logs', N'ma_log') IS NULL
               OR COL_LENGTH(N'dbo.Logs', N'loai_log') IS NULL
               OR COL_LENGTH(N'dbo.Logs', N'ma_tai_khoan') IS NULL
               OR COL_LENGTH(N'dbo.Logs', N'hanh_dong') IS NULL
               OR COL_LENGTH(N'dbo.Logs', N'du_lieu_cu') IS NULL
                THROW 51277, N'Có liên kết OAuth đã thu hồi nhưng Logs chưa sẵn sàng để giữ dấu vết; bảng cũ được giữ nguyên.', 1;

            INSERT INTO dbo.Logs
                (ma_log, loai_log, thoi_diem_utc, ma_co_so, ma_tai_khoan,
                 hanh_dong, bang_tac_dong, ma_ban_ghi, du_lieu_cu, ket_qua, ghi_chu)
            SELECT
                CONCAT(N'oauth-unlinked-', CONVERT(NVARCHAR(36), o.ma_lien_ket)),
                'system',
                COALESCE(o.ngay_thu_hoi, o.cap_nhat_luc, SYSUTCDATETIME()),
                a.ma_co_so,
                o.ma_tai_khoan,
                'oauth_identity_revoked',
                'TaiKhoan',
                o.ma_tai_khoan,
                CONCAT(N'{"provider":"', o.nha_cung_cap, N'","status":"da_thu_hoi"}'),
                'thanh_cong',
                N'Dấu vết liên kết OAuth cũ; provider subject đã bị loại khỏi bản ghi đăng nhập.'
            FROM dbo.TaiKhoanLienKetOAuth AS o
            LEFT JOIN dbo.TaiKhoan AS a ON a.ma_tai_khoan = o.ma_tai_khoan
            WHERE o.trang_thai = 'da_thu_hoi'
              AND NOT EXISTS
                  (SELECT 1 FROM dbo.Logs AS l
                   WHERE l.ma_log = CONCAT(N'oauth-unlinked-', CONVERT(NVARCHAR(36), o.ma_lien_ket)));
        END;

        DROP TABLE dbo.TaiKhoanLienKetOAuth;
    END;

    IF NOT EXISTS
       (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.TaiKhoan')
        AND name = N'UX_TaiKhoan_google_subject')
        CREATE UNIQUE INDEX UX_TaiKhoan_google_subject ON dbo.TaiKhoan (google_subject)
            WHERE google_subject IS NOT NULL;

    IF NOT EXISTS
       (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.TaiKhoan')
        AND name = N'UX_TaiKhoan_facebook_subject')
        CREATE UNIQUE INDEX UX_TaiKhoan_facebook_subject ON dbo.TaiKhoan (facebook_subject)
            WHERE facebook_subject IS NOT NULL;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

SELECT DB_NAME() AS database_dang_cap_nhat,
       COL_LENGTH(N'dbo.TaiKhoan', N'google_subject') AS do_dai_google_subject,
       COL_LENGTH(N'dbo.TaiKhoan', N'facebook_subject') AS do_dai_facebook_subject,
       OBJECT_ID(N'dbo.TaiKhoanLienKetOAuth', N'U') AS bang_oauth_cu_phai_null;
GO
