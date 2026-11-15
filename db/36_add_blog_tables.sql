:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_ID(DB_NAME()) <= 4
BEGIN
    ;THROW 51100, N'Không chạy migration Blog trong system database.', 1;
END;

IF OBJECT_ID(N'dbo.DanhMucBlog', N'U') IS NOT NULL
   AND OBJECT_ID(N'dbo.BaiVietBlog', N'U') IS NOT NULL
BEGIN
    PRINT N'Các bảng Blog đã tồn tại; không thay đổi dữ liệu.';
    RETURN;
END;

IF OBJECT_ID(N'dbo.DanhMucBlog', N'U') IS NOT NULL
   OR OBJECT_ID(N'dbo.BaiVietBlog', N'U') IS NOT NULL
BEGIN
    ;THROW 51101, N'Trạng thái bảng Blog không đầy đủ; cần đối soát trước khi chạy.', 1;
END;

BEGIN TRY
    BEGIN TRANSACTION;

    CREATE TABLE dbo.DanhMucBlog
    (
        ma_danh_muc_blog BIGINT IDENTITY(1, 1) NOT NULL,
        slug             VARCHAR(120)    NOT NULL,
        ten_danh_muc     NVARCHAR(100)   NOT NULL,
        mo_ta            NVARCHAR(500)   NULL,
        trang_thai       VARCHAR(20)     NOT NULL CONSTRAINT DF_DanhMucBlog_trang_thai DEFAULT ('hoat_dong'),
        ngay_tao_utc     DATETIME2(0)    NOT NULL CONSTRAINT DF_DanhMucBlog_ngay_tao DEFAULT (SYSUTCDATETIME()),
        cap_nhat_luc_utc DATETIME2(0)    NOT NULL CONSTRAINT DF_DanhMucBlog_cap_nhat DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT PK_DanhMucBlog PRIMARY KEY (ma_danh_muc_blog),
        CONSTRAINT UQ_DanhMucBlog_slug UNIQUE (slug),
        CONSTRAINT CK_DanhMucBlog_trang_thai CHECK (trang_thai IN ('hoat_dong', 'ngung')),
        CONSTRAINT CK_DanhMucBlog_slug CHECK (LEN(slug) BETWEEN 1 AND 120)
    );

    CREATE TABLE dbo.BaiVietBlog
    (
        ma_bai_viet_blog BIGINT IDENTITY(1, 1) NOT NULL,
        ma_danh_muc_blog BIGINT          NOT NULL,
        slug             VARCHAR(160)    NOT NULL,
        tieu_de          NVARCHAR(200)   NOT NULL,
        tom_tat          NVARCHAR(500)   NOT NULL,
        noi_dung         NVARCHAR(MAX)   NOT NULL,
        so_phut_doc      SMALLINT        NOT NULL,
        trang_thai       VARCHAR(20)     NOT NULL CONSTRAINT DF_BaiVietBlog_trang_thai DEFAULT ('nhap'),
        ngay_xuat_ban_utc DATETIME2(0)   NULL,
        ngay_tao_utc     DATETIME2(0)    NOT NULL CONSTRAINT DF_BaiVietBlog_ngay_tao DEFAULT (SYSUTCDATETIME()),
        cap_nhat_luc_utc DATETIME2(0)    NOT NULL CONSTRAINT DF_BaiVietBlog_cap_nhat DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT PK_BaiVietBlog PRIMARY KEY (ma_bai_viet_blog),
        CONSTRAINT UQ_BaiVietBlog_slug UNIQUE (slug),
        CONSTRAINT FK_BaiVietBlog_DanhMucBlog FOREIGN KEY (ma_danh_muc_blog)
            REFERENCES dbo.DanhMucBlog(ma_danh_muc_blog),
        CONSTRAINT CK_BaiVietBlog_trang_thai CHECK (trang_thai IN ('nhap', 'da_xuat_ban', 'an')),
        CONSTRAINT CK_BaiVietBlog_so_phut_doc CHECK (so_phut_doc BETWEEN 1 AND 240),
        CONSTRAINT CK_BaiVietBlog_slug CHECK (LEN(slug) BETWEEN 1 AND 160),
        CONSTRAINT CK_BaiVietBlog_noi_dung CHECK (LEN(LTRIM(RTRIM(noi_dung))) > 0)
    );

    CREATE INDEX IX_BaiVietBlog_danh_muc_cong_khai
        ON dbo.BaiVietBlog(ma_danh_muc_blog, trang_thai, ngay_xuat_ban_utc)
        INCLUDE (slug, tieu_de, tom_tat, so_phut_doc);

    INSERT INTO dbo.DanhMucBlog (slug, ten_danh_muc, mo_ta)
    VALUES
        ('bat-dau', N'BẮT ĐẦU', N'Gợi ý dành cho người mới học ngoại ngữ.'),
        ('ky-nang', N'KỸ NĂNG', N'Các cách rèn luyện kỹ năng ngôn ngữ.'),
        ('phuong-phap', N'PHƯƠNG PHÁP', N'Phương pháp học và ôn tập có chủ đích.');

    INSERT INTO dbo.BaiVietBlog
    (
        ma_danh_muc_blog, slug, tieu_de, tom_tat, noi_dung,
        so_phut_doc, trang_thai, ngay_xuat_ban_utc
    )
    SELECT category.ma_danh_muc_blog, article.slug, article.tieu_de,
           article.tom_tat, article.noi_dung, article.so_phut_doc,
           'da_xuat_ban', NULL
    FROM
    (
        VALUES
        (
            'bat-dau-hoc-ngoai-ngu', 'bat-dau',
            N'Bắt đầu học ngoại ngữ khi lịch trình đã bận',
            N'Một mục tiêu nhỏ và lịch học thực tế giúp việc bắt đầu bớt nặng nề.',
            CAST(N'Khi lịch trình đã kín, lời khuyên học thật nhiều mỗi ngày thường khó duy trì. Hãy bắt đầu bằng một khoảng thời gian ngắn mà bạn có thể lặp lại trong tuần.' + NCHAR(13) + NCHAR(10) + NCHAR(13) + NCHAR(10) + N'Chọn một tình huống cụ thể muốn sử dụng ngôn ngữ: giới thiệu bản thân, hỏi đường, hay đọc một đoạn hướng dẫn. Mục tiêu càng rõ, bạn càng dễ chọn tài liệu và nhận ra tiến bộ.' + NCHAR(13) + NCHAR(10) + NCHAR(13) + NCHAR(10) + N'Cuối mỗi tuần, dành vài phút xem lại điều đã làm được rồi điều chỉnh nhịp học. Sự đều đặn thường hữu ích hơn một kế hoạch quá nặng.' AS NVARCHAR(MAX)),
            4
        ),
        (
            'luyen-nghe-moi-ngay', 'ky-nang',
            N'Luyện nghe ngắn, nhưng nghe có chủ đích',
            N'Một cách đơn giản để biến vài phút nghe thành thời gian luyện tập chủ động.',
            CAST(N'Chọn một đoạn ghi âm ngắn phù hợp với trình độ hiện tại. Ở lượt đầu, nghe để nắm chủ đề chung thay vì dừng lại ở từng từ mới.' + NCHAR(13) + NCHAR(10) + NCHAR(13) + NCHAR(10) + N'Ở lượt tiếp theo, ghi lại những cụm từ bạn nhận ra và thử nghe lại phần còn chưa rõ. Bạn có thể đọc bản chép lời sau khi đã tự nghe, rồi bật lại một lần nữa.' + NCHAR(13) + NCHAR(10) + NCHAR(13) + NCHAR(10) + N'Điều quan trọng là dùng nguồn nội dung phù hợp với khả năng và lặp lại phương pháp này theo nhịp có thể duy trì.' AS NVARCHAR(MAX)),
            3
        ),
        (
            'on-tu-vung-theo-ngu-canh', 'phuong-phap',
            N'Ôn từ vựng theo ngữ cảnh thay vì học rời',
            N'Gắn từ mới với một câu và tình huống để dễ nhớ cách dùng.',
            CAST(N'Một danh sách dài có thể giúp bạn gặp nhiều từ, nhưng không phải lúc nào cũng cho biết từ đó được dùng ra sao. Khi ghi từ mới, hãy lưu cùng một câu ngắn hoặc tình huống bạn gặp nó.' + NCHAR(13) + NCHAR(10) + NCHAR(13) + NCHAR(10) + N'Thử tự đặt một câu có liên quan đến đời sống của mình. Sau đó ôn lại theo khoảng cách thời gian, ưu tiên những từ bạn chưa nhớ chắc.' + NCHAR(13) + NCHAR(10) + NCHAR(13) + NCHAR(10) + N'Nếu một từ có nhiều nghĩa, hãy ghi lại nghĩa đúng với ngữ cảnh đang học trước; bạn có thể mở rộng thêm khi gặp cách dùng khác.' AS NVARCHAR(MAX)),
            5
        )
    ) AS article(slug, category_slug, tieu_de, tom_tat, noi_dung, so_phut_doc)
    INNER JOIN dbo.DanhMucBlog AS category ON category.slug = article.category_slug;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
