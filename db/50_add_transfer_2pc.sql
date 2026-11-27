:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

/*
  Chuyển cơ sở bằng giao dịch phân tán (2PC qua MS DTC) — đường tùy chọn bên cạnh đường "phục hồi tiến về phía trước".

  Chạy trên MỌI site (mỗi site có thể là nguồn hoặc đích). Idempotent (CREATE OR ALTER).

  - dbo.sp_chuyen_co_so_nhan_2pc : chạy ở site ĐÍCH; tạo hoặc kích hoạt hồ sơ học viên, sự kiện, nhật ký, thông báo.
  - dbo.sp_chuyen_co_so_2pc      : chạy ở site NGUỒN; mở BEGIN DISTRIBUTED TRANSACTION, cập nhật nguồn, gọi thủ tục
                                    đích qua Linked Server, rồi COMMIT. Lỗi ở bất kỳ site nào ⇒ hủy cả hai.

  Điều kiện: Linked Server tới site đích có RPC OUT = true; MS DTC chạy và cho phép giao dịch mạng giữa hai máy.
  Chỉ chạy cho giao dịch đang `dang_xu_ly` và còn ở bước `da_tiep_nhan` (chưa chạy dở theo đường cũ).
*/

SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_ID(DB_NAME()) <= 4
    THROW 51500, N'Hãy chọn một CSDL site, không chạy trong system database.', 1;
IF OBJECT_ID(N'dbo.GiaoDichChuyenCoSo', N'U') IS NULL OR OBJECT_ID(N'dbo.LichSuChuyenCoSo', N'U') IS NULL
    THROW 51501, N'Thiếu bảng chuyển cơ sở; hãy chạy schema trước.', 1;
GO

CREATE OR ALTER PROCEDURE dbo.sp_chuyen_co_so_nhan_2pc
    @ma_chuyen          VARCHAR(24),
    @ma_hoc_vien        VARCHAR(24),
    @co_so_nguon        VARCHAR(10),
    @co_so_dich         VARCHAR(10),
    @slug_goc           VARCHAR(160),
    @slug_nguon         VARCHAR(160),
    @co_so_goc          VARCHAR(10),
    @ma_tai_khoan       VARCHAR(24),
    @ho_ten             NVARCHAR(150),
    @ngay_sinh          DATE,
    @gioi_tinh          NVARCHAR(20),
    @sdt                VARCHAR(20),
    @email              NVARCHAR(254),
    @dia_chi            NVARCHAR(300),
    @ngay_nhap_hoc      DATE,
    @avatar_public_id   NVARCHAR(255),
    @avatar_secure_url  NVARCHAR(1024),
    @actor              VARCHAR(24)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @@TRANCOUNT = 0
        THROW 51510, N'Thủ tục nhận hồ sơ chỉ được gọi bên trong giao dịch phân tán của site nguồn.', 1;
    IF NOT EXISTS (SELECT 1 FROM dbo.CoSo WHERE ma_co_so = @co_so_dich AND trang_thai = 'hoat_dong')
        THROW 51511, N'Cơ sở đích không hoạt động hoặc không khớp CSDL này.', 1;
    IF @co_so_nguon = @co_so_dich
        THROW 51512, N'Cơ sở nguồn và đích phải khác nhau.', 1;
    IF EXISTS (SELECT 1 FROM dbo.LichSuChuyenCoSo WHERE ma_chuyen = @ma_chuyen AND site_ghi = @co_so_dich)
        THROW 51513, N'Giao dịch này đã có sự kiện ở đích (đã chạy theo đường khác); cần đối soát, không chạy lại.', 1;

    DECLARE @resource NVARCHAR(255) = CONCAT(N'qlttnn:academic:transfer-destination:', @co_so_dich, N':', @ma_chuyen), @lock INT;
    EXEC @lock = sys.sp_getapplock @Resource = @resource, @LockMode = 'Exclusive', @LockOwner = 'Transaction', @LockTimeout = 5000;
    IF @lock < 0 THROW 51514, N'Không lấy được khóa giao dịch ở đích.', 1;

    DECLARE @cur_trang_thai VARCHAR(20), @cur_co_so_goc VARCHAR(10), @cur_tai_khoan VARCHAR(24), @returning BIT = 0;
    SELECT @cur_trang_thai = trang_thai, @cur_co_so_goc = co_so_goc, @cur_tai_khoan = ma_tai_khoan
    FROM dbo.HocVien WITH (UPDLOCK, HOLDLOCK)
    WHERE ma_hoc_vien = @ma_hoc_vien AND ma_co_so = @co_so_dich;

    IF @@ROWCOUNT = 0
    BEGIN
        DECLARE @slug VARCHAR(160) = @slug_goc, @n INT = 1, @cat VARCHAR(160);
        WHILE EXISTS (SELECT 1 FROM dbo.HocVien WITH (UPDLOCK, HOLDLOCK) WHERE slug = @slug)
        BEGIN
            SET @n += 1;
            -- giống available_student_slug: cắt gốc cho vừa chỗ hậu tố, bỏ dấu '-' ở cuối, rồi thêm -N
            SET @cat = LEFT(@slug_goc, 159 - LEN(CAST(@n AS VARCHAR(10))));
            WHILE LEN(@cat) > 1 AND RIGHT(@cat, 1) = '-' SET @cat = LEFT(@cat, LEN(@cat) - 1);
            SET @slug = CONCAT(@cat, '-', @n);
        END;
        INSERT INTO dbo.HocVien
            (ma_hoc_vien, slug, ma_co_so, co_so_goc, ma_tai_khoan, ho_ten, ngay_sinh, gioi_tinh, sdt, email,
             dia_chi, ngay_nhap_hoc, avatar_public_id, avatar_secure_url, trang_thai)
        VALUES
            (@ma_hoc_vien, @slug, @co_so_dich, @co_so_goc, @ma_tai_khoan, @ho_ten, @ngay_sinh, @gioi_tinh, @sdt, @email,
             @dia_chi, @ngay_nhap_hoc, @avatar_public_id, @avatar_secure_url, 'dang_hoc');
    END
    ELSE IF @cur_trang_thai = 'da_chuyen_di'
    BEGIN
        -- Học viên quay lại cơ sở cũ: dùng lại hồ sơ cũ đúng danh tính, không mở lại đăng ký cũ.
        IF @cur_co_so_goc <> @co_so_goc OR (@cur_tai_khoan IS NOT NULL AND @cur_tai_khoan <> @ma_tai_khoan)
            THROW 51515, N'Hồ sơ cũ không khớp danh tính học viên chuyển về.', 1;
        IF NOT EXISTS (SELECT 1 FROM dbo.LichSuChuyenCoSo
                       WHERE ma_hoc_vien = @ma_hoc_vien AND site_ghi = @co_so_dich AND co_so_nguon = @co_so_dich
                         AND su_kien = 'cap_nhat_ho_so_nguon')
            THROW 51516, N'Chưa xác nhận hồ sơ cũ đã rời cơ sở này trước đó.', 1;
        IF EXISTS (SELECT 1 FROM dbo.GiaoDichChuyenCoSo
                   WHERE ma_hoc_vien = @ma_hoc_vien AND co_so_nguon = @co_so_dich AND trang_thai IN ('cho_duyet', 'dang_xu_ly'))
            THROW 51517, N'Học viên còn giao dịch chuyển đang mở tại cơ sở đích.', 1;
        UPDATE dbo.HocVien
        SET ma_tai_khoan = @ma_tai_khoan, ho_ten = @ho_ten, ngay_sinh = @ngay_sinh, gioi_tinh = @gioi_tinh, sdt = @sdt,
            email = @email, dia_chi = @dia_chi, ngay_nhap_hoc = @ngay_nhap_hoc,
            avatar_public_id = @avatar_public_id, avatar_secure_url = @avatar_secure_url, trang_thai = 'dang_hoc'
        WHERE ma_hoc_vien = @ma_hoc_vien AND ma_co_so = @co_so_dich AND trang_thai = 'da_chuyen_di';
        IF @@ROWCOUNT <> 1 THROW 51518, N'Hồ sơ cũ vừa thay đổi; hãy thử lại.', 1;
        SET @returning = 1;
    END
    ELSE
        THROW 51519, N'Đã tồn tại hồ sơ khác tại cơ sở đích; cần đối soát trước khi chuyển.', 1;

    DECLARE @id_su_kien VARCHAR(24), @id_log VARCHAR(24);
    SET @id_su_kien = CONCAT(@co_so_dich, '-LS-', RIGHT(CONCAT('000000', CAST(NEXT VALUE FOR dbo.Seq_LS AS VARCHAR(20))), 6));
    INSERT INTO dbo.LichSuChuyenCoSo (ma_su_kien, ma_chuyen, ma_hoc_vien, co_so_nguon, co_so_dich, site_ghi, su_kien, ma_tai_khoan_thuc_hien, chi_tiet)
    VALUES (@id_su_kien, @ma_chuyen, @ma_hoc_vien, @co_so_nguon, @co_so_dich, @co_so_dich, 'tao_ho_so_dich', @actor, N'2PC');
    SET @id_su_kien = CONCAT(@co_so_dich, '-LS-', RIGHT(CONCAT('000000', CAST(NEXT VALUE FOR dbo.Seq_LS AS VARCHAR(20))), 6));
    INSERT INTO dbo.LichSuChuyenCoSo (ma_su_kien, ma_chuyen, ma_hoc_vien, co_so_nguon, co_so_dich, site_ghi, su_kien, ma_tai_khoan_thuc_hien, chi_tiet)
    VALUES (@id_su_kien, @ma_chuyen, @ma_hoc_vien, @co_so_nguon, @co_so_dich, @co_so_dich, 'hoan_tat', @actor, N'2PC');

    SET @id_log = CONCAT(@co_so_dich, '-NK-', RIGHT(CONCAT('000000', CAST(NEXT VALUE FOR dbo.Seq_NK AS VARCHAR(20))), 6));
    INSERT INTO dbo.Logs (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong, ma_ban_ghi, du_lieu_cu, du_lieu_moi, ip, ket_qua)
    VALUES (@id_log, 'system', @co_so_dich, @actor,
            CASE WHEN @returning = 1 THEN 'tiep_nhan_lai_hoc_vien_2pc' ELSE 'tao_ho_so_hoc_vien_chuyen_den_2pc' END,
            'GiaoDichChuyenCoSo', @ma_chuyen,
            CASE WHEN @returning = 1 THEN N'{"student_status": "da_chuyen_di"}' ELSE NULL END,
            CONCAT(N'{"student_id": "', STRING_ESCAPE(@ma_hoc_vien, 'json'), N'", "student_status": "dang_hoc", "mechanism": "2PC"}'),
            '', 'thanh_cong');

    DECLARE @event_key VARCHAR(160) = CONCAT('transfer-received:', @ma_chuyen);
    IF NOT EXISTS (SELECT 1 FROM dbo.ThongBao WITH (UPDLOCK, HOLDLOCK) WHERE event_key = @event_key)
        INSERT INTO dbo.ThongBao (slug, event_key, ma_co_so, danh_muc, muc_do, doi_tuong, tieu_de, noi_dung, duong_dan)
        VALUES (CONCAT(LOWER(@co_so_dich), '-transfer-', LEFT(CONVERT(VARCHAR(64), HASHBYTES('SHA2_256', @event_key), 2), 32)),
                @event_key, @co_so_dich, 'transfer', 'success', 'site_staff', N'Học viên mới đã chuyển đến',
                LEFT(CONCAT(@ho_ten, N' (', @slug_nguon, N') đã chuyển đến từ ', @co_so_nguon,
                            N'. Tư vấn & xếp lớp vui lòng chọn lớp và phòng phù hợp.'), 500),
                N'/admin/classes');
END;
GO

CREATE OR ALTER PROCEDURE dbo.sp_chuyen_co_so_2pc
    @ma_chuyen       VARCHAR(24),
    @linked_server   SYSNAME,
    @db_dich         SYSNAME,
    @slug_goc        VARCHAR(160),
    @actor           VARCHAR(24)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;    -- bắt buộc với giao dịch phân tán: lỗi ở bất kỳ site nào ⇒ rollback toàn bộ

    -- Tên Linked Server và database chỉ được lấy từ danh sách đã đăng ký, không nhận chuỗi tùy ý.
    IF NOT EXISTS (SELECT 1 FROM sys.servers WHERE name = @linked_server AND is_linked = 1 AND is_rpc_out_enabled = 1)
        THROW 51520, N'Linked Server không tồn tại hoặc chưa bật RPC OUT.', 1;
    IF @db_dich LIKE N'%[^A-Za-z0-9_]%' OR LEN(@db_dich) = 0
        THROW 51521, N'Tên database đích không hợp lệ.', 1;

    DECLARE @co_so_nguon VARCHAR(10), @co_so_dich VARCHAR(10), @ma_hoc_vien VARCHAR(24),
            @trang_thai VARCHAR(20), @buoc VARCHAR(30);
    SELECT @co_so_nguon = co_so_nguon, @co_so_dich = co_so_dich, @ma_hoc_vien = ma_hoc_vien,
           @trang_thai = trang_thai, @buoc = buoc_cuoi
    FROM dbo.GiaoDichChuyenCoSo WHERE ma_chuyen = @ma_chuyen;
    IF @ma_hoc_vien IS NULL THROW 51522, N'Không tìm thấy giao dịch chuyển cơ sở.', 1;
    IF @trang_thai <> 'dang_xu_ly' OR @buoc <> 'da_tiep_nhan'
        THROW 51523, N'Chỉ chạy 2PC cho giao dịch đã duyệt, đang xử lý và chưa chạy bước nào theo đường khác.', 1;
    IF NOT EXISTS (SELECT 1 FROM dbo.CoSo WHERE ma_co_so = @co_so_nguon AND trang_thai = 'hoat_dong')
        THROW 51524, N'Cơ sở nguồn không hoạt động.', 1;

    DECLARE @call NVARCHAR(600) = CONCAT(QUOTENAME(@linked_server), N'.', QUOTENAME(@db_dich), N'.dbo.sp_chuyen_co_so_nhan_2pc');
    DECLARE @lock INT, @resource NVARCHAR(255);

    BEGIN DISTRIBUTED TRANSACTION;

        SET @resource = CONCAT(N'qlttnn:academic:student-transfer:', @co_so_nguon, N':', @ma_hoc_vien);
        EXEC @lock = sys.sp_getapplock @Resource = @resource, @LockMode = 'Exclusive', @LockOwner = 'Transaction', @LockTimeout = 5000;
        IF @lock < 0 THROW 51525, N'Không lấy được khóa chuyển học viên ở nguồn.', 1;

        -- khóa và kiểm tra lại giao dịch và hồ sơ nguồn trong giao dịch
        IF NOT EXISTS (SELECT 1 FROM dbo.GiaoDichChuyenCoSo WITH (UPDLOCK, HOLDLOCK)
                       WHERE ma_chuyen = @ma_chuyen AND trang_thai = 'dang_xu_ly' AND buoc_cuoi = 'da_tiep_nhan')
            THROW 51526, N'Giao dịch đã đổi trạng thái; không chạy 2PC.', 1;

        DECLARE @ho_ten NVARCHAR(150), @ngay_sinh DATE, @gioi_tinh NVARCHAR(20), @sdt VARCHAR(20), @email NVARCHAR(254),
                @dia_chi NVARCHAR(300), @ngay_nhap_hoc DATE, @avatar_public_id NVARCHAR(255), @avatar_secure_url NVARCHAR(1024),
                @co_so_goc VARCHAR(10), @ma_tai_khoan VARCHAR(24), @slug_nguon VARCHAR(160), @hv_trang_thai VARCHAR(20);
        SELECT @ho_ten = ho_ten, @ngay_sinh = ngay_sinh, @gioi_tinh = gioi_tinh, @sdt = sdt, @email = email, @dia_chi = dia_chi,
               @ngay_nhap_hoc = ngay_nhap_hoc, @avatar_public_id = avatar_public_id, @avatar_secure_url = avatar_secure_url,
               @co_so_goc = co_so_goc, @ma_tai_khoan = ma_tai_khoan, @slug_nguon = slug, @hv_trang_thai = trang_thai
        FROM dbo.HocVien WITH (UPDLOCK, HOLDLOCK)
        WHERE ma_hoc_vien = @ma_hoc_vien AND ma_co_so = @co_so_nguon;
        IF @@ROWCOUNT <> 1 THROW 51527, N'Không tìm thấy hồ sơ nguồn.', 1;
        IF @hv_trang_thai <> 'dang_hoc' THROW 51528, N'Hồ sơ nguồn không còn ở trạng thái đang học.', 1;
        IF (CASE WHEN @avatar_public_id IS NULL THEN 1 ELSE 0 END) <> (CASE WHEN @avatar_secure_url IS NULL THEN 1 ELSE 0 END)
            THROW 51529, N'Metadata ảnh học viên chưa đầy đủ; cần đối soát trước khi chuyển.', 1;

        -- (1) ĐÍCH: tạo hoặc kích hoạt hồ sơ qua Linked Server (tham gia cùng giao dịch phân tán)
        EXEC @call
            @ma_chuyen = @ma_chuyen, @ma_hoc_vien = @ma_hoc_vien, @co_so_nguon = @co_so_nguon, @co_so_dich = @co_so_dich,
            @slug_goc = @slug_goc, @slug_nguon = @slug_nguon, @co_so_goc = @co_so_goc, @ma_tai_khoan = @ma_tai_khoan,
            @ho_ten = @ho_ten, @ngay_sinh = @ngay_sinh, @gioi_tinh = @gioi_tinh, @sdt = @sdt, @email = @email,
            @dia_chi = @dia_chi, @ngay_nhap_hoc = @ngay_nhap_hoc, @avatar_public_id = @avatar_public_id,
            @avatar_secure_url = @avatar_secure_url, @actor = @actor;

        -- (2) NGUỒN: đối soát sĩ số, trả chỗ lớp, đóng đăng ký, đánh dấu đã chuyển đi
        CREATE TABLE #lop (ma_lop VARCHAR(24) PRIMARY KEY, so_dk INT NOT NULL);
        INSERT INTO #lop (ma_lop, so_dk)
        SELECT d.ma_lop, COUNT_BIG(*)
        FROM dbo.DangKy AS d WITH (UPDLOCK, HOLDLOCK)
        WHERE d.ma_co_so = @co_so_nguon AND d.ma_hoc_vien = @ma_hoc_vien AND d.trang_thai IN ('da_dang_ky', 'dang_hoc')
        GROUP BY d.ma_lop;

        IF EXISTS (
            SELECT 1 FROM #lop AS t
            INNER JOIN dbo.LopHoc AS l WITH (UPDLOCK, HOLDLOCK) ON l.ma_co_so = @co_so_nguon AND l.ma_lop = t.ma_lop
            WHERE l.si_so_hien_tai <> (SELECT COUNT_BIG(*) FROM dbo.DangKy AS x WITH (UPDLOCK, HOLDLOCK)
                                       WHERE x.ma_co_so = @co_so_nguon AND x.ma_lop = t.ma_lop AND x.trang_thai IN ('da_dang_ky', 'dang_hoc'))
               OR l.si_so_hien_tai < t.so_dk)
            THROW 51530, N'Sĩ số lớp nguồn không khớp số đăng ký còn hiệu lực; cần đối soát.', 1;

        UPDATE l SET si_so_hien_tai = l.si_so_hien_tai - t.so_dk
        FROM dbo.LopHoc AS l WITH (UPDLOCK, HOLDLOCK)
        INNER JOIN #lop AS t ON l.ma_co_so = @co_so_nguon AND l.ma_lop = t.ma_lop;

        UPDATE dbo.DangKy SET trang_thai = 'chuyen_di'
        WHERE ma_co_so = @co_so_nguon AND ma_hoc_vien = @ma_hoc_vien AND trang_thai IN ('da_dang_ky', 'dang_hoc');

        UPDATE dbo.HocVien SET trang_thai = 'da_chuyen_di'
        WHERE ma_co_so = @co_so_nguon AND ma_hoc_vien = @ma_hoc_vien AND trang_thai = 'dang_hoc';
        IF @@ROWCOUNT <> 1 THROW 51531, N'Hồ sơ nguồn vừa thay đổi; giao dịch đã được hủy.', 1;

        DECLARE @id VARCHAR(24);
        SET @id = CONCAT(@co_so_nguon, '-LS-', RIGHT(CONCAT('000000', CAST(NEXT VALUE FOR dbo.Seq_LS AS VARCHAR(20))), 6));
        INSERT INTO dbo.LichSuChuyenCoSo (ma_su_kien, ma_chuyen, ma_hoc_vien, co_so_nguon, co_so_dich, site_ghi, su_kien, ma_tai_khoan_thuc_hien, chi_tiet)
        VALUES (@id, @ma_chuyen, @ma_hoc_vien, @co_so_nguon, @co_so_dich, @co_so_nguon, 'xac_nhan_ho_so_dich', @actor, N'2PC');
        SET @id = CONCAT(@co_so_nguon, '-LS-', RIGHT(CONCAT('000000', CAST(NEXT VALUE FOR dbo.Seq_LS AS VARCHAR(20))), 6));
        INSERT INTO dbo.LichSuChuyenCoSo (ma_su_kien, ma_chuyen, ma_hoc_vien, co_so_nguon, co_so_dich, site_ghi, su_kien, ma_tai_khoan_thuc_hien, chi_tiet)
        VALUES (@id, @ma_chuyen, @ma_hoc_vien, @co_so_nguon, @co_so_dich, @co_so_nguon, 'cap_nhat_ho_so_nguon', @actor, N'2PC');
        SET @id = CONCAT(@co_so_nguon, '-LS-', RIGHT(CONCAT('000000', CAST(NEXT VALUE FOR dbo.Seq_LS AS VARCHAR(20))), 6));
        INSERT INTO dbo.LichSuChuyenCoSo (ma_su_kien, ma_chuyen, ma_hoc_vien, co_so_nguon, co_so_dich, site_ghi, su_kien, ma_tai_khoan_thuc_hien, chi_tiet)
        VALUES (@id, @ma_chuyen, @ma_hoc_vien, @co_so_nguon, @co_so_dich, @co_so_nguon, 'hoan_tat', @actor, N'2PC');

        SET @id = CONCAT(@co_so_nguon, '-NK-', RIGHT(CONCAT('000000', CAST(NEXT VALUE FOR dbo.Seq_NK AS VARCHAR(20))), 6));
        INSERT INTO dbo.Logs (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong, ma_ban_ghi, du_lieu_cu, du_lieu_moi, ip, ket_qua)
        VALUES (@id, 'system', @co_so_nguon, @actor, 'chuyen_co_so_2pc_hoan_tat', 'GiaoDichChuyenCoSo', @ma_chuyen,
                N'{"student_status": "dang_hoc"}',
                N'{"student_status": "da_chuyen_di", "enrollments": "chuyen_di", "mechanism": "2PC"}', '', 'thanh_cong');

        UPDATE dbo.GiaoDichChuyenCoSo
        SET trang_thai = 'hoan_tat', buoc_cuoi = 'hoan_tat', loi_cuoi = NULL, cap_nhat_luc = SYSUTCDATETIME()
        WHERE ma_chuyen = @ma_chuyen AND trang_thai = 'dang_xu_ly' AND buoc_cuoi = 'da_tiep_nhan';
        IF @@ROWCOUNT <> 1 THROW 51532, N'Giao dịch vừa đổi trạng thái; đã hủy.', 1;

    COMMIT TRANSACTION;

    SELECT @ma_chuyen AS ma_chuyen, 'hoan_tat' AS trang_thai, 'hoan_tat' AS buoc_cuoi;
END;
GO

PRINT N'Đã tạo sp_chuyen_co_so_nhan_2pc và sp_chuyen_co_so_2pc.';
GO
