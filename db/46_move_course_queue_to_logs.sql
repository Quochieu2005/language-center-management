-- Migrate the temporary KhoaHoc outbox to the existing append-only Logs table.
-- Run once on AUTH_SESSION_SITE_CODE. This script never creates a table.
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.GiaoDichDongBoKhoaHoc', N'U') IS NOT NULL
BEGIN
    IF OBJECT_ID(N'dbo.Logs', N'U') IS NULL
    BEGIN
        ;THROW 51070, N'Không tìm thấy dbo.Logs để giữ các yêu cầu KhoaHoc đang chờ.', 1;
    END;

    BEGIN TRY
        BEGIN TRANSACTION;

        INSERT dbo.Logs
            (ma_log, loai_log, ma_tai_khoan, hanh_dong, bang_tac_dong,
             ma_ban_ghi, du_lieu_cu, du_lieu_moi, dinh_danh_bam, ket_qua)
        SELECT
            N'KHINT-' + o.ma_giao_dich,
            'sync', o.ma_tai_khoan, o.hanh_dong, 'KhoaHoc',
            LEFT(COALESCE(o.ma_khoa_hoc, o.slug), 100), o.du_lieu_truoc,
            payload.du_lieu_moi, o.request_hash, NULL
        FROM dbo.GiaoDichDongBoKhoaHoc AS o
        CROSS APPLY (
            SELECT
                'course_sync' AS queue_kind,
                o.ma_giao_dich AS operation_id,
                o.slug AS slug,
                o.ma_khoa_hoc AS course_id,
                JSON_QUERY(o.du_lieu_moi) AS [after],
                JSON_QUERY(o.site_muc_tieu) AS target_sites,
                JSON_QUERY(o.site_cho_dong_bo) AS pending_sites,
                o.loi AS detail
            FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES
        ) AS payload(du_lieu_moi)
        WHERE NOT EXISTS (
            SELECT 1 FROM dbo.Logs AS existing
            WHERE existing.ma_log = N'KHINT-' + o.ma_giao_dich
        );

        INSERT dbo.Logs
            (ma_log, loai_log, hanh_dong, bang_tac_dong, ma_ban_ghi,
             du_lieu_moi, ket_qua)
        SELECT
            N'KHFIN-' + o.ma_giao_dich, 'sync', 'hoan_tat', 'KhoaHoc',
            LEFT(COALESCE(o.ma_khoa_hoc, o.slug), 100),
            N'{"operation_id":"' + o.ma_giao_dich + N'","pending_sites":[]}', 'thanh_cong'
        FROM dbo.GiaoDichDongBoKhoaHoc AS o
        WHERE o.trang_thai = 'hoan_tat'
          AND NOT EXISTS (
              SELECT 1 FROM dbo.Logs AS existing
              WHERE existing.ma_log = N'KHFIN-' + o.ma_giao_dich
          );

        INSERT dbo.Logs
            (ma_log, loai_log, hanh_dong, bang_tac_dong, ma_ban_ghi,
             du_lieu_moi, ket_qua)
        SELECT
            N'KHREV-' + o.ma_giao_dich + N'-migrate', 'sync', 'can_doi_soat', 'KhoaHoc',
            LEFT(COALESCE(o.ma_khoa_hoc, o.slug), 100),
            payload.du_lieu_moi, 'that_bai'
        FROM dbo.GiaoDichDongBoKhoaHoc AS o
        CROSS APPLY (
            SELECT
                o.ma_giao_dich AS operation_id,
                JSON_QUERY(o.site_cho_dong_bo) AS pending_sites,
                o.loi AS detail
            FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES
        ) AS payload(du_lieu_moi)
        WHERE o.trang_thai = 'can_doi_soat'
          AND NOT EXISTS (
              SELECT 1 FROM dbo.Logs AS existing
              WHERE existing.ma_log = N'KHREV-' + o.ma_giao_dich + N'-migrate'
          );

        DROP TABLE dbo.GiaoDichDongBoKhoaHoc;
        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;
GO
