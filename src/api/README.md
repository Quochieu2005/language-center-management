# Django API

Dùng [mục lục tài liệu](../../README.md#tai-lieu-du-an) và [đối chiếu học phần](../../docs/QLTTNN-De-Cuong-Bao-Cao.md#tai-lieu-giang-vien) để lần từ yêu cầu tới source. Số DB không phải số instance; MonHoc ghi một Publisher rồi SQL Server truyền bản sao, Global Query hỏi từng DB và gộp tại Django. Không dùng unit test thay kiểm chứng nhiều máy.

Thư mục này chứa API và Coordinator của hệ thống CSDL phân tán. Frontend Next.js nằm ở `../web`; trình duyệt chỉ gọi HTTP API và không kết nối trực tiếp tới SQL Server.

## Chạy lần đầu trên Windows

Mở PowerShell tại `D:\laragon\www\language-center-management\src\api`:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8001
```

Nếu môi trường đã có Python khác tương thích, thay `py -3.13` bằng launcher/version tương ứng. Không cài package vào Python toàn máy; dependency được cài trong `.venv` của API. Cần cài driver SQL Server tương thích nếu máy API kết nối SQL Server qua ODBC.

Khi mở repository ở thư mục gốc bằng VS Code, terminal tích hợp CMD mặc định bắt đầu tại thư mục gốc. Sau khi đã tạo `src/api/.venv`, có thể vào API theo từng bước rồi chạy lệnh như bình thường:

```cmd
cd src
cd api
python manage.py runserver 127.0.0.1:8001
```

Profile trong `.vscode/settings.json` tự kích hoạt `.venv` khi `cd` vào thư mục có `Scripts/activate.bat`. Cấu hình này chỉ áp dụng cho terminal tích hợp của VS Code khi mở repository; cửa sổ CMD mở bên ngoài VS Code không đọc cấu hình workspace. Nếu profile chưa đổi sau khi cập nhật, chạy **Developer: Reload Window**, đóng terminal cũ và mở terminal mới.

## Swagger / OpenAPI

Giao diện tài liệu được **sinh từ API bằng `drf-spectacular`**; source không tự dựng một trang Swagger riêng. Gói `drf-spectacular[sidecar]` phục vụ asset Swagger UI từ dependency đã cài, không cần tải giao diện từ CDN.

Khi `API_DOCS_ENABLED=true` (mặc định theo `DJANGO_DEBUG`):

- Swagger UI: <http://127.0.0.1:8001/api/docs>
- OpenAPI JSON/YAML: <http://127.0.0.1:8001/api/schema/> (thêm `?format=json` để yêu cầu JSON)
- Liveness API: <http://127.0.0.1:8001/api/v1/health/>

Đặt `API_DOCS_ENABLED=false` để gỡ Swagger và schema endpoint khỏi URL khi triển khai. Không bật debug trên môi trường công khai.

## CSDL phân tán và kết nối site

**Yêu cầu chung:** đồ án dùng 3 site trong giới hạn 2–4; phải chứng minh ít nhất một phương pháp phân mảnh, một phương pháp replication, một distributed transaction, một tình huống concurrency, một distributed query và đồng bộ dữ liệu. Đọc [yêu cầu chung và kịch bản demo trong README chính](../../README.md#yêu-cầu-chung-áp-dụng-cho-mọi-đề-tài) cùng [API spec](../../specs/api.md) trước khi triển khai module nghiệp vụ.

API/Coordinator có Site Router, service replication `MonHoc`/`KhoaHoc`, luồng chuyển cơ sở có retry, kiểm soát sức chứa và Global Query có `missing_sites`. Các cơ chế này cần kiểm chứng theo TC-REP-01/TC-SYNC-01, TC-DTX-01, TC-CON-01 và TC-DQ-01 trên SQL Server test trước khi ghi đạt; xem [ma trận trạng thái](../../docs/Trang-Thai-Trien-Khai.md).

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

Các biến đã có trong `.env.example`: `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`, `EMAIL_TIMEOUT`, `WEB_APP_BASE_URL`, `PASSWORD_RESET_TIMEOUT` (mặc định 120 giây) và `ACCOUNT_ACTIVATION_TIMEOUT`. Thông tin SMTP thật chỉ đặt trong `.env` cục bộ hoặc secret store; không gửi giá trị bí mật trong chat. Khi chưa có SMTP, có thể dùng `django.core.mail.backends.console.EmailBackend` trong môi trường phát triển.

API hiện có gửi email thông tin cấp tài khoản Admin Small/giáo viên và OTP đặt lại mật khẩu cho tài khoản quản trị. Reset dùng `TokenDatLaiMatKhau` cùng ledger phục hồi `GiaoDichDatLaiMatKhau`; hạn OTP mặc định là 120 giây. Cấu hình thật phụ thuộc SMTP trong môi trường chạy. Không ghi giá trị bí mật vào tài liệu hoặc Git; việc có code gửi thư không chứng minh SMTP đã gửi thành công ở môi trường của nhóm.

Các luồng gửi thư dùng `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` và `DEFAULT_FROM_EMAIL`. Email gửi thật phụ thuộc cấu hình SMTP, DNS/mạng và chấp nhận từ mail provider; kiểm tra cấu hình qua luồng nghiệp vụ trong môi trường phát triển, không thêm endpoint thử chỉ để gửi email.

`core.sites.connections.get_site_connection(site_code)` phân giải mã site đã kiểm tra sang alias riêng. Danh sách site hoạt động được đọc từ `CoSo` qua các database đã cấu hình; Coordinator đối chiếu dữ liệu và kết nối, không cố định vòng lặp Q1/Q7/TD. API lấy site từ phiên/quyền hoặc xác thực bộ lọc theo vai trò; client không chọn alias hay database tùy ý.

Global Query hiện truy vấn từng CSDL site riêng trong phạm vi quyền, tổng hợp tại tầng API và trả site thiếu; không thực hiện `JOIN`/khóa ngoại xuyên site, không sao chép dữ liệu nghiệp vụ vào một DB chung. Các nghiệp vụ `LOCAL`, `GLOBAL`, `REPLICATED-WRITE` và `DISTRIBUTED-TX` phải theo `../../README.md`, `../../docs/DATABASE_SCHEMA.md` và `../../specs/api.md`.

## Cloudinary và cách xếp thư mục ảnh

`src/api/.env.example` khai báo placeholders cho Cloud Name, API Key, API Secret và `CLOUDINARY_ROOT_FOLDER=language-center-management`. Sau khi tạo API secret mới trong Cloudinary, đặt credentials thật vào `src/api/.env` (đã bị Git bỏ qua); không đưa secret vào frontend, source, log hoặc PR.

API hiện có upload intent và hoàn tất upload Cloudinary cho ảnh đại diện Admin, Admin Small, giáo viên và nhân viên mới. Django ký intent ngắn hạn, giới hạn tài khoản/bản ghi, xác minh asset rồi cập nhật `TaiKhoan.avatar_public_id` và `TaiKhoan.avatar_secure_url`; bytes ảnh gửi thẳng tới Cloudinary. Cấu hình vẫn cần secret Cloudinary của môi trường chạy. Chưa có API MediaAsset tổng quát cho ảnh khóa học/cơ sở hoặc bằng chứng upload thật trong môi trường nhóm.

## Phạm vi đã khởi tạo

## Module API hiện có

`core.urls.py` là danh mục route trong source. Các view gọi service theo domain; route xuất hiện trong OpenAPI chứng minh route được khai báo, không chứng minh database site hay tích hợp ngoài đang sẵn sàng.

| Module | Trách nhiệm |
|---|---|
| `core/sites/connections.py` | Đọc cấu hình kết nối riêng từng site và chọn alias qua Site Router |
| `core/auth/` | Đăng nhập, phiên có thể thu hồi, CSRF, idle timeout, hồ sơ, đổi/reset mật khẩu, OAuth học viên và vòng đời Admin Small |
| `core/catalog/` | Danh mục môn/khóa học, danh sách khóa học công khai và ghi danh mục dùng chung |
| `core/blog/` | API công khai đọc danh mục và chi tiết Blog theo slug bằng Global Query; đối chiếu bản sao từng site và báo site thiếu/lệch |
| `core/classes/` | Phòng/lớp/buổi, đăng ký công khai và đăng ký/xếp lớp cục bộ |
| `core/academics/` | Chuyển cơ sở, học phí/phiếu thu/kỳ đóng, nhắc phí, báo cáo, điểm danh/điểm và SePay |
| `core/students/` | Danh sách hồ sơ, cấp tài khoản, portal đọc dữ liệu và xóa hồ sơ theo tiến trình nhiều site |
| `core/teachers/`, `core/employees/` | Quản lý hồ sơ, tài khoản và trạng thái giáo viên/nhân viên |
| `core/notifications/`, `core/audit/` | Thông báo quản trị và truy vấn nhật ký có giới hạn quyền/site |
| `core/media/` | Intent upload và hoàn tất ảnh đại diện Cloudinary |

Các nghiệp vụ bắt buộc của đề tài đã có route/service tương ứng trong source: đăng ký khóa học, xếp lớp, chuyển cơ sở, thu học phí tại quầy, quản lý điểm và thống kê học viên theo cơ sở. Chuyển cơ sở điều phối nhiều transaction cục bộ với phục hồi tiến về phía trước sau khi đích commit; không phải ACID nguyên tử xuyên database. Cơ chế khóa/transaction đăng ký bảo vệ chỗ cuối ở một site; phải chạy hai phiên SQL Server để chứng minh TC-CON-01.

Blog có hai route đọc công khai: `GET /api/v1/blog/categories/` và `GET /api/v1/blog/{slug}/`. Admin Big có đầy đủ quyền đọc/tạo/sửa/xóa danh mục và bài viết dưới `/api/v1/admin/blog/`; Tư vấn & xếp lớp được đọc danh mục/bài và tạo/sửa/xuất bản bài, không sửa/xóa danh mục hoặc xóa bài. Bài viết dùng `REPLICATED-WRITE`: từng database site có transaction cục bộ và ACK trong `Logs`; request ghi cần `Idempotency-Key`, site lỗi sau khi đã commit một phần trả incomplete để retry cùng key. Chạy migration 36 trên từng DB trước khi gọi API; chi tiết hợp đồng, quyền và giới hạn commit ở `specs/api.md`.

Quản lý nhân viên có `GET/POST /api/v1/admin/employees/`, `GET/PATCH/DELETE /api/v1/admin/employees/{slug}/`, `PATCH /api/v1/admin/employees/{slug}/status/` và `POST /api/v1/admin/employees/{account_id}/credential-email/`; ảnh tạo ban đầu dùng `/avatar/upload-intents/` và `/avatar/complete/`. POST tạo không gửi email; Admin Big/Admin Small bấm gửi ở bảng để cấp mật khẩu một lần, trạng thái lưu trong `Logs` cục bộ. PATCH hồ sơ chỉ sửa họ tên, điện thoại, chức vụ tại site; endpoint status chỉ chuyển `active` → `inactive` và thu hồi phiên; DELETE xóa tài khoản nhân bản, phiên/token và ảnh. Nếu `PhieuThu` tham chiếu hồ sơ thì giữ `NhanVien` rời tài khoản, nếu không thì xóa hồ sơ; giữ phiếu thu và Logs. Admin Big chọn một site; Admin Small chỉ dùng site của mình. Form chỉ tạo `ke_toan` (Kế toán & Lễ tân) và `tu_van` (Tư vấn & xếp lớp); chạy migration 37 rồi 41 trên mọi site trước khi triển khai code gộp. Tạo/xóa/ảnh tài khoản có thành phần `REPLICATED-WRITE` và không phải ACID xuyên site; chi tiết trường, bảng, quyền và giới hạn nằm trong FS-EMP-01, schema và API spec.

Học viên/portal và thanh toán SePay có code cùng schema nhưng **không được hiểu là đã được nhóm duyệt vào phạm vi môn học**. SePay mặc định tắt bằng `SEPAY_ENABLED=false`; không coi tích hợp là chạy thật khi chưa cấu hình merchant/webhook và kiểm chứng trên môi trường được cấp phép.

Trạng thái source, giới hạn phạm vi và bằng chứng còn thiếu được tổng hợp tại [Trạng thái triển khai](../../docs/Trang-Thai-Trien-Khai.md). Yêu cầu môn học và kết quả TC nằm trong [ma trận kiểm chứng](../../docs/QLTTNN-Yeu-Cau-Chung-Va-Kiem-Chung.md). Không đánh dấu đạt từ việc có code, Swagger, seed hoặc unit test mô phỏng.
