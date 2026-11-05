:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

/*
    Add SePay bank-transfer attempts and append-only callback events.
    Run once against each existing site database: QLTTNN_Q1, QLTTNN_Q7, QLTTNN_TD.
    This migration does not create a database or change existing tuition balances.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_ID(DB_NAME()) <= 4
    THROW 51301, N'Hãy chọn một CSDL site, không chạy trong system database.', 1;

IF OBJECT_ID(N'dbo.HocPhi', N'U') IS NULL
   OR OBJECT_ID(N'dbo.DotHocPhi', N'U') IS NULL
   OR OBJECT_ID(N'dbo.PhieuThu', N'U') IS NULL
   OR OBJECT_ID(N'dbo.TaiKhoan', N'U') IS NULL
   OR OBJECT_ID(N'dbo.CoSo', N'U') IS NULL
    THROW 51302, N'Thiếu bảng nghiệp vụ bắt buộc; hãy cài schema trước.', 1;

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.Seq_SP', N'SO') IS NULL
        CREATE SEQUENCE dbo.Seq_SP AS BIGINT START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 999999 NO CYCLE;

    IF NOT EXISTS
       (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.DotHocPhi')
        AND name = N'UX_DotHocPhi_ma_va_co_so')
        CREATE UNIQUE INDEX UX_DotHocPhi_ma_va_co_so
            ON dbo.DotHocPhi(ma_dot_hoc_phi, ma_co_so);

    IF COL_LENGTH(N'dbo.PhieuThu', N'ma_nhan_vien') IS NULL
        THROW 51303, N'Thiếu cột dbo.PhieuThu.ma_nhan_vien; dừng để đối soát schema.', 1;

    IF EXISTS
    (
        SELECT 1 FROM sys.columns
        WHERE object_id = OBJECT_ID(N'dbo.PhieuThu')
          AND name = N'ma_nhan_vien' AND is_nullable = 0
    )
        ALTER TABLE dbo.PhieuThu ALTER COLUMN ma_nhan_vien VARCHAR(24) NULL;

    IF COL_LENGTH(N'dbo.PhieuThu', N'ma_yeu_cau') IS NULL
        ALTER TABLE dbo.PhieuThu ADD ma_yeu_cau VARCHAR(24) NULL;

    IF OBJECT_ID(N'dbo.YeuCauThanhToan', N'U') IS NULL
    BEGIN
        CREATE TABLE dbo.YeuCauThanhToan
        (
            ma_yeu_cau       VARCHAR(24)    NOT NULL,
            ma_co_so         VARCHAR(10)    NOT NULL,
            ma_hoc_phi       VARCHAR(24)    NOT NULL,
            ma_dot_hoc_phi   VARCHAR(24)    NOT NULL,
            ma_tai_khoan     VARCHAR(24)    NOT NULL,
            so_tien          DECIMAL(18, 0) NOT NULL,
            ma_tham_chieu    VARCHAR(40)    NOT NULL,
            khoa_idempotency CHAR(36)       NOT NULL,
            trang_thai       VARCHAR(24)    NOT NULL CONSTRAINT DF_YeuCauThanhToan_trang_thai DEFAULT ('cho_thanh_toan'),
            tao_luc_utc      DATETIME2(3)   NOT NULL CONSTRAINT DF_YeuCauThanhToan_tao_luc DEFAULT (SYSUTCDATETIME()),
            het_han_utc      DATETIME2(3)   NOT NULL,
            cap_nhat_luc_utc DATETIME2(3)   NOT NULL CONSTRAINT DF_YeuCauThanhToan_cap_nhat DEFAULT (SYSUTCDATETIME()),
            thanh_toan_luc_utc DATETIME2(3) NULL,
            CONSTRAINT PK_YeuCauThanhToan PRIMARY KEY (ma_yeu_cau),
            CONSTRAINT UQ_YeuCauThanhToan_ma_yeu_cau_site UNIQUE (ma_yeu_cau, ma_co_so),
            CONSTRAINT UQ_YeuCauThanhToan_tham_chieu UNIQUE (ma_tham_chieu),
            CONSTRAINT UQ_YeuCauThanhToan_idempotency UNIQUE (khoa_idempotency),
            CONSTRAINT FK_YeuCauThanhToan_HocPhiCungCoSo FOREIGN KEY (ma_hoc_phi, ma_co_so)
                REFERENCES dbo.HocPhi(ma_hoc_phi, ma_co_so),
            CONSTRAINT FK_YeuCauThanhToan_DotHocPhiCungCoSo
                FOREIGN KEY (ma_dot_hoc_phi, ma_co_so)
                REFERENCES dbo.DotHocPhi(ma_dot_hoc_phi, ma_co_so),
            CONSTRAINT FK_YeuCauThanhToan_TaiKhoan FOREIGN KEY (ma_tai_khoan)
                REFERENCES dbo.TaiKhoan(ma_tai_khoan),
            CONSTRAINT CK_YeuCauThanhToan_so_tien CHECK (so_tien > 0),
            CONSTRAINT CK_YeuCauThanhToan_trang_thai CHECK
                (trang_thai IN ('cho_thanh_toan', 'da_thanh_toan', 'het_han', 'can_doi_soat', 'da_huy')),
            CONSTRAINT CK_YeuCauThanhToan_thoi_han CHECK (het_han_utc > tao_luc_utc)
        );
    END;

    IF OBJECT_ID(N'dbo.SuKienThanhToan', N'U') IS NULL
    BEGIN
        CREATE TABLE dbo.SuKienThanhToan
        (
            ma_su_kien              UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_SuKienThanhToan_id DEFAULT (NEWID()),
            ma_co_so                VARCHAR(10)      NOT NULL,
            ma_yeu_cau              VARCHAR(24)      NULL,
            ma_giao_dich_sepay      BIGINT           NOT NULL,
            ma_tham_chieu           VARCHAR(40)      NULL,
            so_tien                 DECIMAL(18, 0)   NOT NULL,
            tai_khoan_nhan          VARCHAR(34)      NULL,
            ma_tham_chieu_ngan_hang VARCHAR(100)     NULL,
            thoi_diem_giao_dich     DATETIME2(0)     NULL,
            ket_qua                 VARCHAR(24)      NOT NULL,
            thoi_diem_nhan_utc      DATETIME2(3)     NOT NULL CONSTRAINT DF_SuKienThanhToan_nhan DEFAULT (SYSUTCDATETIME()),
            CONSTRAINT PK_SuKienThanhToan PRIMARY KEY (ma_su_kien),
            CONSTRAINT UQ_SuKienThanhToan_giao_dich UNIQUE (ma_giao_dich_sepay),
            CONSTRAINT FK_SuKienThanhToan_CoSo FOREIGN KEY (ma_co_so) REFERENCES dbo.CoSo(ma_co_so),
            CONSTRAINT FK_SuKienThanhToan_YeuCauCungCoSo FOREIGN KEY (ma_yeu_cau, ma_co_so)
                REFERENCES dbo.YeuCauThanhToan(ma_yeu_cau, ma_co_so),
            CONSTRAINT CK_SuKienThanhToan_so_tien CHECK (so_tien >= 0),
            CONSTRAINT CK_SuKienThanhToan_ket_qua CHECK
                (ket_qua IN ('da_ghi_nhan', 'can_doi_soat', 'khong_tim_thay'))
        );
    END;

    IF NOT EXISTS
       (SELECT 1 FROM sys.foreign_keys WHERE name = N'FK_PhieuThu_YeuCauThanhToanCungCoSo')
        ALTER TABLE dbo.PhieuThu ADD CONSTRAINT FK_PhieuThu_YeuCauThanhToanCungCoSo
            FOREIGN KEY (ma_yeu_cau, ma_co_so)
            REFERENCES dbo.YeuCauThanhToan(ma_yeu_cau, ma_co_so);

    IF NOT EXISTS
       (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.PhieuThu')
        AND name = N'UX_PhieuThu_ma_yeu_cau')
        CREATE UNIQUE INDEX UX_PhieuThu_ma_yeu_cau
            ON dbo.PhieuThu(ma_yeu_cau) WHERE ma_yeu_cau IS NOT NULL;

    IF NOT EXISTS
       (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.YeuCauThanhToan')
        AND name = N'UX_YeuCauThanhToan_mot_yeu_cau_mo')
        CREATE UNIQUE INDEX UX_YeuCauThanhToan_mot_yeu_cau_mo
            ON dbo.YeuCauThanhToan(ma_hoc_phi, ma_co_so)
            WHERE trang_thai = 'cho_thanh_toan';

    IF NOT EXISTS
       (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.YeuCauThanhToan')
        AND name = N'IX_YeuCauThanhToan_het_han')
        CREATE INDEX IX_YeuCauThanhToan_het_han
            ON dbo.YeuCauThanhToan(trang_thai, het_han_utc);

    IF OBJECT_ID(N'dbo.TR_SuKienThanhToan_AppendOnly', N'TR') IS NOT NULL
        EXEC(N'DROP TRIGGER dbo.TR_SuKienThanhToan_AppendOnly');
    EXEC sys.sp_executesql N'
        CREATE TRIGGER dbo.TR_SuKienThanhToan_AppendOnly
        ON dbo.SuKienThanhToan
        AFTER UPDATE, DELETE
        AS
        BEGIN
            SET NOCOUNT ON;
            IF EXISTS (SELECT 1 FROM inserted)
            BEGIN
                ;THROW 51061, ''SuKienThanhToan không được cập nhật.'', 1;
            END;
            IF ISNULL(TRY_CONVERT(bit, SESSION_CONTEXT(N''qlttnn_student_purge'')), 0) <> 1
            BEGIN
                ;THROW 51062, ''Chỉ luồng xóa học viên được phép xóa sự kiện thanh toán liên quan.'', 1;
            END;
        END;';

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

SELECT DB_NAME() AS database_dang_cap_nhat,
       OBJECT_ID(N'dbo.YeuCauThanhToan', N'U') AS yeu_cau_thanh_toan_da_tao,
       OBJECT_ID(N'dbo.SuKienThanhToan', N'U') AS su_kien_thanh_toan_da_tao,
       COL_LENGTH(N'dbo.PhieuThu', N'ma_yeu_cau') AS phieu_thu_da_co_khoa_thanh_toan;
GO
