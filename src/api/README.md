# Django API

Thư mục này chứa API và Coordinator của hệ thống CSDL phân tán. Frontend Next.js nằm ở `../web`; trình duyệt chỉ gọi HTTP API và không kết nối trực tiếp tới SQL Server.

## Chạy lần đầu trên Windows

Mở PowerShell tại `D:\laragon\www\language-center-management\src\api`:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Nếu môi trường đã có Python khác tương thích, thay `py -3.13` bằng launcher/version tương ứng. Không cài package vào Python toàn máy; dependency được cài trong `.venv` của API. Cần cài driver SQL Server tương thích nếu máy API kết nối SQL Server qua ODBC.

## Swagger / OpenAPI

Giao diện tài liệu được **sinh từ API bằng `drf-spectacular`**; source không tự dựng một trang Swagger riêng. Gói `drf-spectacular[sidecar]` phục vụ asset Swagger UI từ dependency đã cài, không cần tải giao diện từ CDN.

Khi `API_DOCS_ENABLED=true` (mặc định theo `DJANGO_DEBUG`):

- Swagger UI: <http://127.0.0.1:8000/api/docs/swagger/>
- ReDoc: <http://127.0.0.1:8000/api/docs/redoc/>
- OpenAPI JSON/YAML: <http://127.0.0.1:8000/api/schema/> (thêm `?format=json` để yêu cầu JSON)
- Liveness API: <http://127.0.0.1:8000/api/v1/health/>

Đặt `API_DOCS_ENABLED=false` để gỡ Swagger, ReDoc và schema endpoint khỏi URL khi triển khai. Không bật debug trên môi trường công khai.

## CSDL phân tán và kết nối site

Mỗi cơ sở có CSDL SQL Server riêng. Cấu hình chỉ tạo một alias/kết nối riêng cho từng entry trong `SITE_DATABASES_JSON`; không tạo CSDL nghiệp vụ trung tâm và không có alias mặc định dùng để lưu dữ liệu (`default` dùng dummy backend). Ví dụ máy demo hiện tại có thể khai báo ba DB riêng cùng SQL Server host; khi demo trên nhiều máy, `host` của mỗi entry là địa chỉ VPN/LAN của máy chứa CSDL đó.

Sửa `.env` (file này đã bị Git bỏ qua) và thay thông tin mẫu bằng giá trị môi trường thật:

```dotenv
SITE_DATABASES_JSON={"Q1":{"name":"QLTTNN_Q1","host":"127.0.0.1","port":1433,"user":"qlttnn_api","password":"THAY_BANG_SECRET_RIENG"},"Q7":{"name":"QLTTNN_Q7","host":"127.0.0.1","port":1433,"user":"qlttnn_api","password":"THAY_BANG_SECRET_RIENG"},"TD":{"name":"QLTTNN_TD","host":"127.0.0.1","port":1433,"user":"qlttnn_api","password":"THAY_BANG_SECRET_RIENG"}}
```

Không commit `.env`, mật khẩu SQL, hoặc địa chỉ kết nối riêng của nhóm. `SQL_SERVER_TRUST_SERVER_CERTIFICATE=yes` chỉ phù hợp khi phát triển với chứng chỉ tự ký; triển khai thật cần chứng chỉ được tin cậy và đặt `SQL_SERVER_TRUST_SERVER_CERTIFICATE=no`. Mã cơ sở được đọc từ cấu hình, không có vòng lặp cố định ba site.

`core.sites.connections.get_site_connection(site_code)` chỉ phân giải một mã site tin cậy sang đúng alias riêng đã cấu hình. Chưa có API nghiệp vụ để tự phát hiện site đang `hoat_dong` từ bảng `CoSo`; việc đó sẽ thuộc Site Router/Coordinator khi triển khai nghiệp vụ. Mã site phải đến từ danh tính đã xác thực hoặc ngữ cảnh server, không tin mã/alias database do client tự gửi.

Global Query về sau phải truy vấn từng CSDL site riêng trong phạm vi quyền, tổng hợp tại tầng API và báo site lỗi; không thực hiện `JOIN`/khóa ngoại xuyên site, không sao chép dữ liệu nghiệp vụ vào một DB chung. Các nghiệp vụ `LOCAL`, `GLOBAL`, `REPLICATED-WRITE` và `DISTRIBUTED-TX` phải theo `../../README.md`, `../../docs/DATABASE_SCHEMA.md` và `../../specs/api.md`.

## Phạm vi đã khởi tạo

Hiện có scaffold Django REST Framework, OpenAPI/Swagger UI sinh tự động, cấu hình an toàn mặc định cho quyền endpoint, bcrypt password hasher, giờ Việt Nam, CORS theo cấu hình và tiện ích định tuyến tới kết nối site. Endpoint duy nhất hiện hoạt động là liveness check. Endpoint này chỉ xác nhận tiến trình API còn chạy, **không** kiểm tra kết nối SQL Server.

Chưa triển khai đăng nhập, tài khoản Admin Big/Admin Small, giáo viên/học viên, đăng ký khóa học, xếp lớp, thu học phí, quản lý điểm, đề nghị/duyệt/chuyển cơ sở, Global Query hoặc đồng bộ bảng dùng chung. Chưa có migration Django hay CSDL trung tâm. Các luồng đó phải được triển khai theo schema SQL Server hiện có và kiểm thử với từng site trước khi được xem là hoàn tất. Chỉ endpoint đã triển khai và kiểm thử mới xuất hiện như API hoạt động trong Swagger.
