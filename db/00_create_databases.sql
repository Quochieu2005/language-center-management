/*
    Tạo ba CSDL riêng trên cùng một SQL Server instance.
    Chạy bằng tài khoản có quyền CREATE DATABASE.
    Không xóa hoặc sửa CSDL đã tồn tại.
*/
SET NOCOUNT ON;

IF DB_ID(N'QLTTNN_Q1') IS NULL
    EXEC(N'CREATE DATABASE [QLTTNN_Q1]');
GO

IF DB_ID(N'QLTTNN_Q7') IS NULL
    EXEC(N'CREATE DATABASE [QLTTNN_Q7]');
GO

IF DB_ID(N'QLTTNN_TD') IS NULL
    EXEC(N'CREATE DATABASE [QLTTNN_TD]');
GO

SELECT
    name AS ten_cSDL,
    state_desc AS trang_thai,
    recovery_model_desc AS che_do_khoi_phuc
FROM sys.databases
WHERE name IN (N'QLTTNN_Q1', N'QLTTNN_Q7', N'QLTTNN_TD')
ORDER BY name;
GO
