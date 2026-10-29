:setvar DatabaseName "QLTTNN_Q1"
USE [$(DatabaseName)];
GO

/*
    Tạo database roles, không tạo SQL login hay mật khẩu.
    Chạy trên từng CSDL sau khi đã tạo schema.
*/
SET NOCOUNT ON;

IF DB_ID(DB_NAME()) <= 4
BEGIN
    ;THROW 51050, N'Hãy chọn một CSDL site, không chạy trong system database.', 1;
END;

IF OBJECT_ID(N'dbo.LichSuChuyenCoSo', N'U') IS NULL
   OR OBJECT_ID(N'dbo.GiaoDichChuyenCoSo', N'U') IS NULL
   OR (OBJECT_ID(N'dbo.Logs', N'U') IS NULL
       AND (OBJECT_ID(N'dbo.NhatKyHeThong', N'U') IS NULL
            OR OBJECT_ID(N'dbo.NhatKyDongBo', N'U') IS NULL))
BEGIN
    ;THROW 51051, N'Chưa tạo đủ schema. Hãy chạy 01_create_schema.sql trước.', 1;
END;

IF DATABASE_PRINCIPAL_ID(N'qlttnn_api') IS NULL
    EXEC(N'CREATE ROLE qlttnn_api AUTHORIZATION dbo');

IF DATABASE_PRINCIPAL_ID(N'qlttnn_readonly') IS NULL
    EXEC(N'CREATE ROLE qlttnn_readonly AUTHORIZATION dbo');
GO

GRANT SELECT, INSERT, UPDATE, DELETE ON SCHEMA::dbo TO qlttnn_api;
GRANT SELECT ON SCHEMA::dbo TO qlttnn_readonly;

/* Bảo vệ lịch sử: Logs không được UPDATE; trigger chỉ cho DELETE trong luồng xóa học viên. */
DENY UPDATE, DELETE ON OBJECT::dbo.LichSuChuyenCoSo TO qlttnn_api;
IF OBJECT_ID(N'dbo.Logs', N'U') IS NOT NULL
    EXEC(N'DENY UPDATE ON OBJECT::dbo.Logs TO qlttnn_api');
ELSE
BEGIN
    IF OBJECT_ID(N'dbo.NhatKyHeThong', N'U') IS NOT NULL
        EXEC(N'DENY UPDATE, DELETE ON OBJECT::dbo.NhatKyHeThong TO qlttnn_api');
    IF OBJECT_ID(N'dbo.NhatKyDongBo', N'U') IS NOT NULL
        EXEC(N'DENY UPDATE, DELETE ON OBJECT::dbo.NhatKyDongBo TO qlttnn_api');
END;
DENY DELETE ON OBJECT::dbo.GiaoDichChuyenCoSo TO qlttnn_api;
GO

/*
    Sau khi DBA tạo database user từ SQL login an toàn, gán user vào một role:
    ALTER ROLE qlttnn_api ADD MEMBER [ten_database_user_cua_api];
    ALTER ROLE qlttnn_readonly ADD MEMBER [ten_database_user_bao_cao];

    Thực hiện riêng trong từng CSDL site. Không dùng tài khoản db_owner cho API.
    Admin Big/Admin Small và các vai trò nghiệp vụ được Django API kiểm tra;
    SQL Server role này chỉ giới hạn quyền của danh tính kết nối database.
*/
