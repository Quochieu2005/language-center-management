/* Validate the existing local FK; do not delete or rewrite orphaned courses. */
SET NOCOUNT ON;
SET XACT_ABORT ON;
IF LEFT(DB_NAME(), 7) <> N'QLTTNN_' OR LEN(DB_NAME()) <= 7 OR LEN(DB_NAME()) > 17
    THROW 51440, N'Hãy chọn database QLTTNN_<SITE>.', 1;
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys
               WHERE parent_object_id = OBJECT_ID(N'dbo.KhoaHoc')
                 AND referenced_object_id = OBJECT_ID(N'dbo.MonHoc')
                 AND name = N'FK_KhoaHoc_MonHoc')
    THROW 51441, N'Thiếu FK_KhoaHoc_MonHoc; đối soát schema trước.', 1;

BEGIN TRY
    BEGIN TRANSACTION;
    IF EXISTS (SELECT 1 FROM dbo.KhoaHoc kh
               LEFT JOIN dbo.MonHoc mh ON mh.ma_mon = kh.ma_mon
               WHERE mh.ma_mon IS NULL)
        THROW 51442, N'Có khóa học thiếu môn cha; dừng để đối soát, không xóa dữ liệu.', 1;

    /* Restored Subscriber FKs may still have NOT FOR REPLICATION set. */
    IF EXISTS (SELECT 1 FROM sys.foreign_keys
               WHERE object_id = OBJECT_ID(N'dbo.FK_KhoaHoc_MonHoc')
                 AND is_not_for_replication = 1)
    BEGIN
        IF EXISTS (SELECT 1 FROM sys.foreign_keys
                   WHERE object_id = OBJECT_ID(N'dbo.FK_KhoaHoc_MonHoc')
                     AND (delete_referential_action <> 0 OR update_referential_action <> 0))
           OR (SELECT COUNT(*) FROM sys.foreign_key_columns
               WHERE constraint_object_id = OBJECT_ID(N'dbo.FK_KhoaHoc_MonHoc')) <> 1
           OR NOT EXISTS (SELECT 1 FROM sys.foreign_key_columns
                          WHERE constraint_object_id = OBJECT_ID(N'dbo.FK_KhoaHoc_MonHoc')
                            AND COL_NAME(parent_object_id, parent_column_id) = N'ma_mon'
                            AND COL_NAME(referenced_object_id, referenced_column_id) = N'ma_mon')
            THROW 51443, N'FK có ánh xạ/cascade khác schema; cần đối soát trước.', 1;
        ALTER TABLE dbo.KhoaHoc DROP CONSTRAINT FK_KhoaHoc_MonHoc;
        ALTER TABLE dbo.KhoaHoc WITH CHECK ADD CONSTRAINT FK_KhoaHoc_MonHoc
            FOREIGN KEY (ma_mon) REFERENCES dbo.MonHoc(ma_mon);
    END;
    ALTER TABLE dbo.KhoaHoc WITH CHECK CHECK CONSTRAINT FK_KhoaHoc_MonHoc;
    IF EXISTS (SELECT 1 FROM sys.foreign_keys
               WHERE object_id = OBJECT_ID(N'dbo.FK_KhoaHoc_MonHoc')
                 AND (is_disabled = 1 OR is_not_trusted = 1))
        THROW 51444, N'FK vẫn chưa trusted; không báo migration hoàn tất.', 1;
    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
