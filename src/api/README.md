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

**Yêu cầu chung:** đồ án dùng 3 site trong giới hạn 2–4; phải chứng minh ít nhất một phương pháp phân mảnh, một phương pháp replication, một distributed transaction, một tình huống concurrency, một distributed query và đồng bộ dữ liệu. Đọc [yêu cầu chung và kịch bản demo trong README chính](../../README.md#yêu-cầu-chung-áp-dụng-cho-mọi-đề-tài) cùng [API spec](../../specs/api.md) trước khi triển khai module nghiệp vụ.

API/Coordinator phải cung cấp định tuyến mảnh, một điểm vào replication, trạng thái/phục hồi chuyển cơ sở, bảo vệ chỗ cuối của lớp và Global Query có thông tin site thiếu. Kết nối alias, liveness hoặc Swagger hoạt động chưa chứng minh các yêu cầu này; chạy TC-REP-01/TC-SYNC-01, TC-DTX-01, TC-CON-01 và TC-DQ-01 trên SQL Server test trước khi ghi đạt. Các cơ chế còn mở phải được chốt theo README/FS; đây là yêu cầu phải làm, không phải xác nhận đã triển khai.

Mỗi cơ sở có CSDL SQL Server riêng. Cấu hình chỉ tạo một alias/kết nối riêng cho từng entry trong `SITE_DATABASES_JSON`; không tạo CSDL nghiệp vụ trung tâm và không có alias mặc định dùng để lưu dữ liệu (`default` dùng dummy backend). Ví dụ máy demo hiện tại có thể khai báo ba DB riêng cùng SQL Server host; khi demo trên nhiều máy, `host` của mỗi entry là địa chỉ VPN/LAN của máy chứa CSDL đó.

Sửa `.env` (file này đã bị Git bỏ qua) và thay thông tin mẫu bằng giá trị môi trường thật:

```dotenv
SITE_DATABASES_JSON={"Q1":{"name":"QLTTNN_Q1","host":"127.0.0.1","port":1433,"user":"qlttnn_api","password":"THAY_BANG_SECRET_RIENG"},"Q7":{"name":"QLTTNN_Q7","host":"127.0.0.1","port":1433,"user":"qlttnn_api","password":"THAY_BANG_SECRET_RIENG"},"TD":{"name":"QLTTNN_TD","host":"127.0.0.1","port":1433,"user":"qlttnn_api","password":"THAY_BANG_SECRET_RIENG"}}
```

Không commit `.env`, mật khẩu SQL, hoặc địa chỉ kết nối riêng của nhóm. `SQL_SERVER_TRUST_SERVER_CERTIFICATE=yes` chỉ phù hợp khi phát triển với chứng chỉ tự ký; triển khai thật cần chứng chỉ được tin cậy và đặt `SQL_SERVER_TRUST_SERVER_CERTIFICATE=no`. Mã cơ sở được đọc từ cấu hình, không có vòng lặp cố định ba site.

## Hiệu năng API và truy vấn site

Khi endpoint chậm, đo tách thời gian xử lý Django và từng truy vấn SQL/site bằng millisecond. Dùng `request_id` để nối log giữa các tầng; nếu chưa có, bổ sung correlation ID an toàn. Đây là hướng dẫn triển khai, không xác nhận middleware đo thời gian đã có. Không ghi bí mật hoặc dữ liệu nhạy cảm. Tránh truy vấn N+1, chỉ lấy trường cần thiết, lọc và phân trang tại SQL Server. Chỉ thêm index sau khi xem query plan và thời gian truy vấn thực tế. Xem [README chính mục 12](../../README.md#12-tốc-độ-tải-trang-và-dữ-liệu) trước khi tối ưu page/API.

Với `GLOBAL`, chỉ hỏi các site cần thiết qua kết nối riêng. Nếu truy vấn độc lập và driver/kết nối cho phép, dùng fan-out có giới hạn đồng thời và timeout; không chờ tuần tự từng site nếu không có lý do nghiệp vụ. Trả trạng thái đầy đủ và `missing_sites` chính xác khi thiếu site. Không chuyển dữ liệu vào DB trung tâm, không JOIN xuyên site, không âm thầm bỏ site lỗi và không tự retry thao tác ghi khi chưa đối soát trạng thái.

## Email kích hoạt tài khoản và khôi phục mật khẩu

Cấu hình SMTP nằm trong `src/api/.env`; Django chỉ đọc cấu hình ở backend. Gmail dùng `smtp.gmail.com`, cổng `587`, STARTTLS; `EMAIL_HOST_USER` là địa chỉ Gmail gửi thư và `EMAIL_HOST_PASSWORD` là **Google App Password mới**. Nếu App Password cũ đã bị lộ, hãy thu hồi trước khi dùng cấu hình này. Không dùng App Password cho đăng nhập Google OAuth, không đưa nó vào frontend, Swagger, log hoặc Git.

Các biến đã có trong `.env.example`: `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`, `EMAIL_TIMEOUT`, `WEB_APP_BASE_URL`, `PASSWORD_RESET_TIMEOUT` (mặc định 15 phút) và `ACCOUNT_ACTIVATION_TIMEOUT` (mặc định 24 giờ). Thay địa chỉ gửi bằng Gmail thật và dán App Password mới trực tiếp vào `.env` trên máy cá nhân; không gửi giá trị bí mật trong chat. Khi chưa có thông tin gửi thư, dùng `django.core.mail.backends.console.EmailBackend` để chỉ in thư ra console trong môi trường phát triển.

SMTP đã được khai báo trong settings, nhưng **chưa có endpoint tạo tài khoản, gửi thư, kích hoạt tài khoản hay quên mật khẩu**; vì vậy cấu hình này chưa tự gửi email. Khi triển khai nghiệp vụ, Admin Big nên tạo Admin Small/giáo viên ở trạng thái chưa kích hoạt và gửi liên kết đặt mật khẩu ban đầu dùng một lần; không tự đặt rồi gửi mật khẩu qua email. Quên mật khẩu nên gửi liên kết chứa token ngẫu nhiên dùng một lần, hết hạn sau 15 phút; chỉ lưu hash token tại site xử lý, trả cùng thông báo dù email tồn tại hay không, giới hạn tốc độ và thu hồi token sau khi dùng. Schema hiện có `TokenDatLaiMatKhau` cho reset; luồng kích hoạt tài khoản cần được thiết kế/cập nhật schema trước khi bật.

Để kiểm tra cấu hình sau khi nhập email gửi và App Password mới, khởi động API rồi dùng một endpoint email thử nghiệm chỉ trong môi trường phát triển (endpoint này hiện chưa có); không đưa thông tin SMTP vào request hoặc Swagger. Chưa thể kiểm thử gửi thật khi `EMAIL_HOST_USER` và `EMAIL_HOST_PASSWORD` còn trống.

`core.sites.connections.get_site_connection(site_code)` chỉ phân giải một mã site tin cậy sang đúng alias riêng đã cấu hình. Chưa có API nghiệp vụ để tự phát hiện site đang `hoat_dong` từ bảng `CoSo`; việc đó sẽ thuộc Site Router/Coordinator khi triển khai nghiệp vụ. Mã site phải đến từ danh tính đã xác thực hoặc ngữ cảnh server, không tin mã/alias database do client tự gửi.

Global Query về sau phải truy vấn từng CSDL site riêng trong phạm vi quyền, tổng hợp tại tầng API và báo site lỗi; không thực hiện `JOIN`/khóa ngoại xuyên site, không sao chép dữ liệu nghiệp vụ vào một DB chung. Các nghiệp vụ `LOCAL`, `GLOBAL`, `REPLICATED-WRITE` và `DISTRIBUTED-TX` phải theo `../../README.md`, `../../docs/DATABASE_SCHEMA.md` và `../../specs/api.md`.

## Cloudinary và cách xếp thư mục ảnh

`src/api/.env.example` khai báo placeholders cho Cloud Name, API Key, API Secret và `CLOUDINARY_ROOT_FOLDER=language-center-management`. Sau khi tạo API secret mới trong Cloudinary, đặt credentials thật vào `src/api/.env` (đã bị Git bỏ qua); không đưa secret vào frontend, source, log hoặc PR.

Folder path được dựng từ loại tài nguyên và dữ liệu đã được API xác thực, ví dụ `language-center-management/hoc-vien/Q1/Q1-HV-000001/anh/<uuid>/`. Mỗi ảnh có UUID riêng; ảnh học viên/giáo viên có phân đoạn site, còn ảnh khóa học/cơ sở dùng nhánh `dung-chung`. Hàm `core.media.folders.build_asset_folder` chỉ tạo đường dẫn an toàn, chưa upload file. API upload chưa được triển khai vì schema metadata ảnh và các luồng xác thực/quyền chưa hoàn tất. Cloudinary Dynamic folders dùng `asset_folder`; cần kiểm tra chế độ folder của Product Environment trước khi bật luồng upload.

## Phạm vi đã khởi tạo

Hiện có scaffold Django REST Framework, OpenAPI/Swagger UI sinh tự động, cấu hình an toàn mặc định cho quyền endpoint, bcrypt password hasher, giờ Việt Nam, CORS theo cấu hình và tiện ích định tuyến tới kết nối site. Endpoint duy nhất hiện hoạt động là liveness check. Endpoint này chỉ xác nhận tiến trình API còn chạy, **không** kiểm tra kết nối SQL Server.

Chưa triển khai đăng nhập, tài khoản Admin Big/Admin Small, giáo viên/học viên, đăng ký khóa học, xếp lớp, thu học phí, quản lý điểm, đề nghị/duyệt/chuyển cơ sở, Global Query hoặc đồng bộ bảng dùng chung. Chưa có migration Django hay CSDL trung tâm. Các luồng đó phải được triển khai theo schema SQL Server hiện có và kiểm thử với từng site trước khi được xem là hoàn tất. Chỉ endpoint đã triển khai và kiểm thử mới xuất hiện như API hoạt động trong Swagger.

Đăng nhập thường và Google/Facebook hiện mới có đặc tả; các endpoint chưa hoạt động và không được coi là đã tích hợp. Trước khi bật cần triển khai xác thực, callback/kiểm tra danh tính, liên kết tài khoản đã xác thực, cơ chế phiên có thể thu hồi, rate limit và test với OAuth apps thật. Mỗi phiên phải hết hạn sau 3600 giây không có hoạt động thật; API phải từ chối phiên quá hạn, frontend tự đưa người dùng về đăng nhập, còn polling nền không được kéo dài phiên. Chưa có session backend hoặc nơi lưu trạng thái phiên trong schema; phải chốt cách lưu tương thích mô hình CSDL riêng từng site trước khi bật auth. Với OAuth, cần chạy `db/06_add_oauth_identity_table.sql` trên các CSDL cũ (hoặc tạo schema mới). Không điền client secret vào `.env.example`, Git hoặc gửi trong chat; chỉ đặt secret mới trong `.env` cục bộ/secret store.
