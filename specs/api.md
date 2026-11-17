
# Đặc tả API

> Trạng thái: API Django có xác thực, quản trị và các nghiệp vụ chính trong source. Tài liệu gồm quy tắc yêu cầu, thiết kế endpoint và một số route đã triển khai; route thực tế nằm trong `src/api/core/urls.py`. Đối chiếu [ma trận trạng thái triển khai](../docs/Trang-Thai-Trien-Khai.md); OpenAPI/Swagger hoặc code không phải bằng chứng nghiệm thu phân tán.

File này mô tả giao diện gọi API thế nào và API phải xử lý quyền, site, dữ liệu cùng lỗi ra sao. Yêu cầu màn hình nằm ở [`ui-ux.md`](ui-ux.md); luồng nghiệp vụ chuẩn nằm trong [`README.md`](../README.md); định nghĩa bảng nằm trong [`docs/DATABASE_SCHEMA.md`](../docs/DATABASE_SCHEMA.md).

## Quy tắc bắt buộc

1. Giao diện chỉ gọi API. API xác thực tài khoản, kiểm tra vai trò/phạm vi, kiểm tra dữ liệu nghiệp vụ rồi mới truy cập CSDL qua Site Router.
2. Mỗi cơ sở dùng một CSDL SQL Server riêng và một kết nối riêng. Không dùng CSDL nghiệp vụ trung tâm; không JOIN hoặc tạo khóa ngoại xuyên site.
3. Mỗi endpoint phải được gắn một kiểu: `LOCAL`, `GLOBAL`, `REPLICATED-WRITE` hoặc `DISTRIBUTED-TX`. Nếu endpoint có nhiều chặng, ghi kiểu cho từng chặng.
4. API tự xác định site từ danh tính đã xác thực, bản ghi hiện hành hoặc danh sách site đang `hoat_dong`. Không tin `ma_co_so_nguon` do trình duyệt gửi lên nếu nguồn phải lấy từ tài khoản.
5. `GLOBAL` truy vấn riêng các CSDL site trong phạm vi quyền và tổng hợp ở tầng API. Response phải chỉ rõ dữ liệu có đầy đủ không; site lỗi không được âm thầm bỏ qua.
6. `REPLICATED-WRITE` ghi theo một chính sách thống nhất tới mọi site hoạt động cần tham gia. Không trả thành công toàn phần nếu có site bắt buộc chưa được cập nhật.
7. Có hai CSDL riêng không tự bảo đảm transaction ACID nguyên tử xuyên site. Thiết kế `DISTRIBUTED-TX` hiện tại lưu tiến trình, retry/phục hồi và trả trạng thái rõ ràng; không tuyên bố bảo đảm ACID xuyên site khi chưa triển khai và kiểm thử cơ chế đó.
8. Mọi ghi cần bảo vệ khỏi dữ liệu sai, quyền không hợp lệ, gửi trùng và cập nhật đồng thời. Không ghi mật khẩu, token hoặc thông tin kết nối vào log hay response.
9. Mọi dữ liệu từ form phải được kiểm tra lại ở API. Validation frontend chỉ phục vụ trải nghiệm, không phải lớp bảo vệ.
10. Truy vấn dùng Django ORM hoặc câu SQL parameterized. Không nối chuỗi dữ liệu người dùng vào SQL, tên bảng, tên cột, `ORDER BY` hay biểu thức lọc.
11. Mật khẩu phải được băm bằng `bcrypt`; không lưu mật khẩu gốc và không “mã hóa rồi giải mã” mật khẩu. Truyền dữ liệu nhạy cảm chỉ qua HTTPS/TLS.
12. Ảnh nhị phân phải lưu ở Cloudinary, không trong source, thư mục upload của API hoặc Git. SQL Server chỉ lưu metadata/đường dẫn cần thiết tại site đúng phân mảnh.
13. Luồng đăng nhập, đăng ký (nếu được bật) và quên mật khẩu phải có rate limit, chống dò tài khoản, audit an toàn và response không tiết lộ tài khoản tồn tại.
14. Khi viết endpoint phải chạy kiểm tra thật với API và SQL Server test: quyền, dữ liệu sau CRUD, rollback, phân tán, lỗi bảo mật và độ trễ; không đánh dấu hoàn tất chỉ vì code biên dịch.
15. Đăng nhập Google/Facebook chỉ xác thực tài khoản nội bộ đã được liên kết trước. Không tự tạo tài khoản, không tự ghép theo email và không lưu access/refresh token của nhà cung cấp.

## Yêu cầu chung và hợp đồng kiểm chứng phân tán

Môn học yêu cầu **2–4 site**, có phân mảnh, replication, transaction và đồng bộ; chứng minh ít nhất **1 phương pháp phân mảnh + 1 phương pháp replication + 1 distributed transaction + 1 tình huống concurrency + 1 distributed query**. Nhóm chọn 3 site Q1/Q7/TD; danh sách site vẫn lấy từ dữ liệu/cấu hình. Không bắt buộc mọi nhóm dùng cùng kiểu phân mảnh.

| Mã yêu cầu | Trách nhiệm API và cách kiểm tra |
|---|---|
| YC-01 / YC-02 | Định tuyến đến DB riêng; đăng ký ở đúng site lớp/học viên; đọc lại `LopHoc`/`DangKy` từng site để kiểm chứng phân mảnh (TC-SITE-01, TC-FRAG-01) |
| YC-03 | Một điểm vào ghi bảng dùng chung; `PATCH /api/v1/admin/shared/subjects/{slug}/` hiện nhân bản cập nhật `MonHoc` bằng Coordinator ở tầng ứng dụng và ACK `Logs` tại từng site (TC-REP-01) |
| YC-04 | Tư vấn & xếp lớp đề nghị, Admin Big hoặc Admin Small tại site nhận duyệt rồi Coordinator mới chuyển; trạng thái/sự kiện nguồn và đích cho phép kiểm tra lỗi trước/sau commit đích (TC-DTX-01) |
| YC-05 | Bảo vệ sức chứa và tạo đăng ký/học phí trong cùng transaction site; hai phiên tranh chỗ cuối chỉ một yêu cầu thắng (TC-CON-01) |
| YC-06 | Đọc từng site và tổng hợp tại API; khi thiếu site trả `complete=false`, `missing_sites`, không thay dữ liệu thiếu bằng 0 (TC-DQ-01) |
| YC-07 | Với `MonHoc`, ACK append-only trong `Logs` cùng transaction cục bộ cho phép retry cùng key/body và chỉ ghi site chưa ACK; outage/recovery qua mạng thật vẫn cần TC-SYNC-01 |

[Hướng dẫn kiểm chứng](../docs/QLTTNN-Yeu-Cau-Chung-Va-Kiem-Chung.md) quy định điều kiện đầu vào và bằng chứng. Đồ án đã chọn replication tầng ứng dụng cho `MonHoc`; đây chưa phải replication cho mọi bảng dùng chung. Chuyển cơ sở hiện là Coordinator với các transaction cục bộ và phục hồi tiến về phía trước, không phải ACID nguyên tử xuyên DB. Swagger chỉ mô tả endpoint, không chứng minh các kịch bản đã chạy đúng trên SQL Server.

## Route đang có trong source

Prefix thực tế là `/api/v1/`; bảng dưới tóm tắt các path nghiệp vụ chính lấy từ `src/api/core/urls.py`, không thay thế danh sách đầy đủ method/path trong file đó. Đây là route có đăng ký trong Django, chưa khẳng định API/SQL Server đang chạy hoặc đã được kiểm chứng TC.

| Luồng | Path pattern hiện có |
|---|---|
| Xác thực | `/auth/csrf/`, `/auth/login/`, `/auth/session/`, `/auth/activity/`, `/auth/logout/`, `/auth/profile/{slug}/`, `/auth/password/change/`, `/auth/password/forgot/`, `/auth/password/reset/` |
| OAuth | `/auth/oauth/{provider}/start/`, `/auth/oauth/{provider}/callback/`, `/auth/oauth/connections/{slug}/` |
| Admin Small/Big | `/admin/admin-smalls/`, `/admin/admin-smalls/{account_id}/credential-email/`, `/admin/admin-smalls/{slug}/status/`, `/admin/admin-smalls/{account_id}/`, `/admin/admin-smalls/profile/{slug}/`, `/admin/admin-bigs/profile/{slug}/` |
| Giáo viên/nhân viên | `/admin/teachers/`, `/admin/teachers/{slug}/`, `/admin/teachers/{slug}/status/`, `/admin/teachers/{slug}/credential-email/`, `/teachers/profile/{slug}/`, `/admin/employees/`, `/admin/employees/{slug}/`, `/admin/employees/{slug}/status/`, `/admin/employees/{account_id}/credential-email/` |
| Avatar | `/auth/profile/{slug}/avatar/upload-intents/`, `/auth/profile/{slug}/avatar/complete/`, `/admin/admin-smalls/{slug}/avatar/upload-intents/`, `/admin/admin-smalls/{slug}/avatar/complete/`, `/admin/teachers/{slug}/avatar/upload-intents/`, `/admin/teachers/{slug}/avatar/complete/`, `/admin/employees/{slug}/avatar/upload-intents/`, `/admin/employees/{slug}/avatar/complete/` |
| Danh mục | `/admin/shared/subjects/`, `/admin/shared/subjects/{slug}/`, `/admin/courses/`, `/admin/courses/{slug}/`, `/courses/`, `/courses/{course_slug}/classes/` |
| Tuyển sinh, học viên | `/public/enrollments/`, `/admin/students/`, `/admin/students/{slug}/`, `/admin/students/{slug}/account/`, `/students/profile/{slug}/` và các route con `enrollments/`, `schedule/`, `tuition/`, `grades/` |
| Lớp, đăng ký | `/admin/classes/`, `/admin/classes/{class_id}/`, `/admin/classes/{class_id}/students/`, `/admin/classes/{class_id}/sessions/`, `/admin/classes/{class_id}/teacher/`, `/admin/teachers/assignment-options/`, `/admin/enrollments/`, `/admin/enrollments/{enrollment_id}/class/`, `/admin/rooms/`, `/admin/rooms/{room_id}/` |
| Học phí, chuyển cơ sở | `/admin/tuition/`, `/admin/tuition/{tuition_id}/installments/`, `/admin/tuition/{tuition_id}/receipts/`, `/admin/tuition/{tuition_id}/receipts/{receipt_id}/refund/`, `/admin/tuition/{tuition_id}/receipts/{receipt_id}/invoice/`, `/admin/classes/{class_id}/tuition-reminders/`, `/admin/transfers/`, `/admin/transfers/{source_site}/{transfer_id}/decision/`, `/admin/transfers/{source_site}/{transfer_id}/retry/` |
| Giáo viên | `/teacher/classes/`, `/teacher/classes/{class_id}/sessions/`, `/teacher/sessions/{session_id}/attendance/`, `/teacher/enrollments/{enrollment_id}/grades/`, `/teacher/enrollments/{enrollment_id}/grades/{grade_type}/`, `/teacher/enrollments/{enrollment_id}/grades/history/` |
| Liên hệ | `/contact/sites/`, `/contact/`, `/admin/contacts/`, `/admin/contacts/{site_code}/{request_id}/reply/` |
| Báo cáo và thông báo | `/admin/reports/students-by-site/`, `/admin/notifications/`, `/reports/audit-logs/` |
| Thanh toán SePay | `/students/profile/{slug}/tuition/{tuition_id}/payments/sepay/`, `/students/profile/{slug}/payments/{attempt_id}/`, `/webhooks/sepay/` |

Các endpoint trong những bảng thiết kế tiếp theo chưa tự động là route đang chạy: path không nằm trong inventory trên, hoặc không được ghi rõ “route source”, phải được coi là hợp đồng đề xuất. Đặc biệt, inventory không có API quản lý `CoSo`, `/admin/sites`, `/admin/dashboard`, hoặc một endpoint đăng ký tài khoản công khai.

## Múi giờ và định dạng giờ

- Múi giờ nghiệp vụ của trung tâm là **giờ Việt Nam: `Asia/Ho_Chi_Minh` (UTC+07:00)**. Các giờ học, lịch làm việc, giờ thu tiền và giờ hiển thị cho người dùng phải hiểu theo múi giờ này; ví dụ 7 giờ sáng là `07:00`, 1 giờ chiều là `13:00`, 2 giờ chiều là `14:00`.
- API dùng định dạng 24 giờ. Trường ngày giữ dạng `YYYY-MM-DD`; trường giờ lịch học riêng giữ dạng `HH:mm` hoặc `HH:mm:ss` và được hiểu là giờ địa phương Việt Nam. Trường thời điểm đầy đủ phải là ISO 8601/RFC 3339 có offset `+07:00`, ví dụ `2026-10-17T13:00:00+07:00`; không gửi thời điểm không có múi giờ hoặc hậu tố `Z` rồi coi đó là giờ Việt Nam.
- Django phải cấu hình `TIME_ZONE = "Asia/Ho_Chi_Minh"`, `USE_TZ = True` và xử lý datetime có timezone; không lấy múi giờ mặc định của Windows/Linux làm quy tắc nghiệp vụ. Nếu hệ thống lưu thời điểm UTC trong DB, API phải đổi sang `Asia/Ho_Chi_Minh` khi trả cho giao diện; nếu lưu `datetimeoffset`, phải giữ đúng thời điểm khi chuyển đổi, response API vẫn theo `+07:00`. Ngày và giờ của lịch học là giờ địa phương, không tự đổi sang ngày khác khi serialize.
- Giao diện gửi/hiển thị 07:00, 13:00, 14:00 theo đúng giờ Việt Nam, không cộng/trừ thêm 7 giờ lần nữa. Không dùng `GETDATE()`/đồng hồ hệ điều hành chưa cấu hình để quyết định ngày thu, hạn thanh toán hoặc lịch học; thời điểm tạo/cập nhật nên lấy từ clock có timezone hoặc UTC nhất quán rồi serialize kèm `+07:00`.
- Kiểm thử phải bao gồm thời điểm gần 00:00 giờ Việt Nam và máy API chạy ở múi giờ khác để phát hiện lỗi lệch ngày/giờ; dữ liệu giờ trong response vẫn phải đúng giờ trung tâm.

## Validation dữ liệu form và chống SQL injection

API dùng Django serializer/form validation làm nguồn kiểm tra cuối cùng. Frontend có thể báo lỗi sớm nhưng mọi request đều phải qua cùng quy tắc server-side trước khi truy vấn/ghi dữ liệu.

| Loại dữ liệu | Quy tắc validation |
|---|---|
| Chuỗi | Trim khoảng trắng ngoài; kiểm tra bắt buộc/tùy chọn, độ dài tối đa theo schema, ký tự hợp lệ; không cắt ngầm chuỗi quá dài |
| Email / số điện thoại | Chuẩn hóa định dạng trước khi so trùng; không dùng làm quyền hoặc tự suy ra site |
| Mã, trạng thái, chức vụ, loại điểm/thu | Chỉ chấp nhận giá trị tồn tại trong DB hoặc allowlist nghiệp vụ; client không tự đặt vai trò/trạng thái tùy ý |
| Tiền | Decimal, lớn hơn 0 khi thu/hoàn; kiểm tra số dư và giới hạn nghiệp vụ trong transaction |
| Số điểm | Trong khoảng 0–10; chỉ đúng `loai_diem` mà môn/khóa cho phép |
| Ngày và khoảng ngày | Định dạng ISO `YYYY-MM-DD`; nếu form có ngày bắt đầu và ngày kết thúc thì `ngay_ket_thuc >= ngay_bat_dau`. Giao diện khóa các ngày trước ngày bắt đầu; API vẫn phải trả lỗi validation nếu request giả gửi ngày không hợp lệ |
| Thời gian | Dùng `Asia/Ho_Chi_Minh` (UTC+07:00); giờ riêng theo `HH:mm`/`HH:mm:ss`, thời điểm đầy đủ theo ISO 8601 có `+07:00`; kiểm tra `gio_ket_thuc > gio_bat_dau`, lịch không xung đột, ngày nằm trong thời gian khóa/lớp |
| Body | Giới hạn kích thước request; từ chối trường không được hỗ trợ hoặc mass assignment như `vai_tro`, `ma_co_so`, `ma_tai_khoan` nếu API tự quyết định các giá trị đó |

Lỗi validation trả `400` hoặc `422` cùng mã trường, ví dụ `{"error":{"code":"VALIDATION_ERROR","details":{"ngay_ket_thuc":"Phải từ ngày bắt đầu trở đi."}}}`; không trả traceback, câu SQL, đường dẫn máy chủ hoặc dữ liệu bí mật.

### Bắt buộc chống SQL injection

- Dùng Django ORM cho lọc/sắp xếp; nếu bắt buộc dùng SQL thô, truyền giá trị bằng placeholder/parameters của driver, không dùng f-string, `%`, `.format()` hoặc nối chuỗi để dựng câu SQL.
- Không bind được tên bảng/cột bằng parameter: tên trường sort, hướng sort và trường lọc động phải ánh xạ qua allowlist cố định trong source. Không lấy tên bảng/cột từ request.
- Không xem escape HTML hay regex là biện pháp chống SQL injection. Validation giới hạn dữ liệu; parameterization ngăn dữ liệu bị diễn giải thành lệnh SQL.
- Có kiểm thử với payload như `' OR 1=1--`, dấu nháy, wildcard và chuỗi dài; kết quả phải bị từ chối hoặc được xem là dữ liệu thuần, không mở rộng quyền/kết quả và không thay đổi dữ liệu ngoài ý muốn.

## Bảo vệ đăng nhập, đăng ký và quên mật khẩu

### Băm mật khẩu và phiên đăng nhập

- Mật khẩu được băm bằng `bcrypt` với salt riêng từng tài khoản và work factor được cấu hình/benchmark trên máy triển khai. Có thể dùng password hasher của Django được cấu hình cho bcrypt; tuyệt đối không tự viết thuật toán hash.
- Băm không phải mã hóa: không có thao tác giải mã để lấy mật khẩu cũ. Khi đổi/reset, tạo hash mới và thu hồi phiên cũ theo chính sách.
- Không đưa mật khẩu, hash, token reset, cookie hoặc header xác thực vào response, analytics, exception hoặc log. Mọi request chứa thông tin đăng nhập đi qua HTTPS/TLS.
- Kết nối Django–SQL Server phải bật mã hóa TLS; bảo vệ dữ liệu/backup tại nơi lưu bằng cấu hình bảo mật SQL Server và quản lý khóa ngoài source. Bcrypt chỉ dành cho mật khẩu, không thay thế mã hóa đường truyền hoặc bảo vệ dữ liệu lưu trữ.
- Cookie phiên nếu dùng phải có `HttpOnly`, `Secure`, `SameSite` phù hợp; request thay đổi dữ liệu phải được bảo vệ CSRF. Không lưu mật khẩu/token lâu hạn trong `localStorage`.
- So sánh hash bằng thư viện chuẩn; xác thực sai, tài khoản không tồn tại, bị khóa hoặc vô hiệu hóa trả cùng thông báo chung. Giới hạn kích thước mật khẩu đầu vào để chống request quá lớn, không cắt mật khẩu.

### Tự hết hạn phiên sau 1 giờ không hoạt động

- Áp dụng cho mọi phiên đã xác thực của Admin Big, Admin Small, Kế toán & Lễ tân, Tư vấn & xếp lớp, giáo viên và nhân viên; nếu sau này bật tài khoản học viên thì áp dụng cùng chính sách. Mỗi phiên/trình duyệt/thiết bị được theo dõi riêng; đăng xuất do idle ở một thiết bị không tự đăng xuất thiết bị khác.
- Thời hạn idle là **3600 giây (60 phút)** kể từ hoạt động người dùng gần nhất. Thời gian được tính bằng đồng hồ phía server, lưu timestamp UTC có timezone; không dựa vào giờ hệ điều hành của trình duyệt.
- Hoạt động được tính gồm thao tác bàn phím, nhấn/chạm, cuộn trang có chủ ý và thao tác nghiệp vụ do người dùng khởi tạo. Không tính polling, refresh tự động, health check, analytics, request nền, tab còn mở hoặc timer. Reload trang không đặt lại thời hạn.
- API phải kiểm tra hết hạn ở **mọi request cần xác thực**, không chỉ dựa vào timer giao diện. Phiên cần trạng thái có thể thu hồi và `last_user_activity_at`/`idle_expires_at` do server quản lý. Chữ ký token hoặc cookie hết hạn tuyệt đối không tự chứng minh idle timeout nếu server không thể xác minh hoạt động gần nhất.
- Khi người dùng hoạt động nhưng không phát sinh request nghiệp vụ, frontend có thể gửi `POST /auth/activity` có CSRF để cập nhật phiên; chỉ gửi khi có sự kiện người dùng thật và giới hạn cập nhật tối đa một lần mỗi 60 giây. Tự động gọi endpoint này theo chu kỳ không có hoạt động người dùng sẽ làm sai chính sách và bị cấm. Request nghiệp vụ do người dùng khởi tạo có thể cập nhật hoạt động trong cùng lần xác thực.
- Khi hết 3600 giây, API từ chối phiên bằng `401` với mã ổn định `SESSION_IDLE_TIMEOUT`, thu hồi trạng thái phiên, hết hạn cookie `HttpOnly` và không xử lý nghiệp vụ. `POST /auth/logout` dùng cùng cơ chế kết thúc phiên khi logout thủ công. Nếu không thể truy cập nơi lưu trạng thái phiên, API không được coi phiên là hợp lệ; trả lỗi dịch vụ phù hợp và không cho qua kiểm tra quyền.
- Khi tải lại ứng dụng, frontend gọi `GET /auth/session/` để xác minh cookie HttpOnly và phục hồi danh tính; không dùng `GET /auth/profile/{slug}/` làm bước phục hồi vì profile có thể cần thêm tra cứu hồ sơ/ảnh trên site. Endpoint session chỉ xác thực phiên hiện tại và không gia hạn idle timeout. Trong bước phục hồi, frontend chỉ xóa trạng thái đăng nhập khi nhận `401`; lỗi mạng/5xx giữ cookie và cho phép thử lại, nhưng không cấp quyền gọi API nếu chưa xác minh được phiên.
- `POST /auth/login/`, `GET /auth/session/` và `POST /auth/activity/` trả `expires_at` UTC của phiên hiện tại. Frontend dùng thời điểm này để đặt bộ đếm tự kiểm tra phiên; request kiểm tra hết hạn không được gia hạn hoạt động. Hoạt động thật đặt lại `expires_at` qua `/auth/activity/`.
- Frontend đồng bộ hoạt động giữa các tab cùng phiên, hiển thị cảnh báo trước hạn (mặc định 5 phút) và nút “Tiếp tục phiên” chỉ khi API xác nhận phiên còn hạn. Đến hạn hoặc nhận `SESSION_IDLE_TIMEOUT`, frontend xóa trạng thái người dùng trong bộ nhớ, điều hướng về trang đăng nhập với thông báo phiên hết hạn và không giữ token trong storage.
- Chính sách cần kiểm thử: chưa hết hạn tại 59:59; hết hạn tại 60:00; tương tác thật đặt lại hạn; polling/refresh nền không đặt lại; reload/tab ngủ không kéo dài phiên; hoạt động ở tab khác được đồng bộ; logout thủ công thu hồi ngay; các role có cùng chính sách.
- **Source hiện tại:** có login/logout, `PhienDangNhap`, `SuKienDangNhap`, endpoint session/activity và idle timeout 3600 giây. Trạng thái phiên kỹ thuật lưu tại database của site cấu hình `AUTH_SESSION_SITE_CODE`; `DATABASES['default']` vẫn là dummy. Cần kiểm chứng frontend nhiều tab và phụ thuộc vận hành vào site lưu phiên.

### Rate limit và chống dò tài khoản

Các ngưỡng dưới đây là **giá trị khởi đầu đề xuất**, phải cấu hình được, ghi nhận trong môi trường test và điều chỉnh theo lưu lượng thực tế. Không dùng khóa tài khoản vĩnh viễn chỉ vì client gửi sai nhiều lần.

| Form/endpoint | Giới hạn ban đầu đề xuất | Hành vi khi vượt ngưỡng |
|---|---|---|
| Đăng nhập | Tối đa 10 request/IP/phút và 5 lần sai cho cặp tài khoản+IP trong 15 phút | Tăng thời gian chờ; yêu cầu CAPTCHA sau ngưỡng; trả `429` với `Retry-After`; không tiết lộ tên tài khoản hợp lệ |
| Bắt đầu/callback OAuth | Giới hạn riêng theo IP, provider và state; callback chỉ dùng một lần | Từ chối state/code lặp hoặc hết hạn; không cho client điều chỉnh callback URI; không log query có authorization code |
| Đăng ký, chỉ khi được nhóm bật | Tối đa 5 request/IP/giờ và 3 lần cho cùng email/giờ | Xác minh email/CAPTCHA sau ngưỡng; response trùng email không tiết lộ tài khoản đã có |
| Quên mật khẩu | Tối đa 10 request/IP/giờ và 3 lần cho cùng email/giờ | Trả cùng response `202` dù email có tồn tại hay không; không gửi nhiều email reset |
| Xác nhận reset mật khẩu | Giới hạn theo IP và token; token một lần, có hạn | Token sai/hết hạn/đã dùng không đổi dữ liệu; trả lỗi chung và ghi audit không chứa token |

IP chỉ được lấy từ proxy đã tin cậy; không tin header IP tùy ý từ client. Rate limit phải phối hợp IP, tài khoản/email đã chuẩn hóa và thời gian; CAPTCHA không thay thế rate limit. API đăng ký tài khoản công khai chưa được duyệt và không có route trong source. API ghi danh khóa học công khai (`POST /api/v1/public/enrollments/`) là nghiệp vụ khác. Phạm vi Admin CRUD hồ sơ và cấp tài khoản học viên theo thao tác riêng được mô tả tại FS-STU-01; portal học viên và thanh toán SePay vẫn chưa được duyệt.

Token reset sinh ngẫu nhiên bằng CSPRNG, đủ entropy, chỉ dùng một lần và lưu dạng hash; token gửi qua email không ghi log. Khác với mật khẩu người dùng, token ngẫu nhiên có thể lưu bằng SHA-256/HMAC hash phục vụ tra cứu an toàn; mật khẩu vẫn phải dùng bcrypt.

### Email kích hoạt tài khoản và khôi phục mật khẩu

Django gửi thư từ backend qua SMTP; thông tin kết nối chỉ nằm trong biến môi trường/secret store (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS` hoặc `EMAIL_USE_SSL`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`). Với Gmail, cấu hình mặc định là `smtp.gmail.com:587` + STARTTLS, dùng địa chỉ Gmail và Google App Password. App Password chỉ dành cho SMTP, không phải OAuth Client Secret. Không ghi thông tin này vào source, Git, log, Swagger response hoặc frontend. Chỉ báo gửi thành công sau khi SMTP chấp nhận thư; lỗi gửi thư phải có trạng thái retry an toàn và không log nội dung bí mật.

Source hiện tạo tài khoản Admin Small/giáo viên bằng mật khẩu khởi tạo từ cấu hình backend, lưu hash và gửi email cấp tài khoản; email là thông tin đăng nhập chính, username không bắt buộc. Chưa có token kích hoạt riêng. Email thật phụ thuộc SMTP và phải kiểm tra kết quả gửi. Không ghi mật khẩu/secret vào log, Git hay response.

Source hiện reset mật khẩu quản trị bằng OTP 6 số, lưu hash, giới hạn số lần sai và hết hạn theo `PASSWORD_RESET_TIMEOUT` (mặc định 120 giây). OTP dùng một lần; ledger phục hồi giữ trạng thái cập nhật mật khẩu trên các bản sao. Response yêu cầu reset không tiết lộ tài khoản tồn tại hay không. Luồng SMTP vẫn cần kiểm thử ở môi trường nhóm.

`PASSWORD_RESET_TIMEOUT` mặc định là 120 giây. `WEB_APP_BASE_URL` chỉ nhận origin đã được cấu hình; không lấy URL redirect tùy ý từ request. Source có service gửi email trong một số luồng tạo tài khoản và quên mật khẩu; giao thư thực tế vẫn phụ thuộc SMTP ở môi trường chạy.

## Ảnh và Cloudinary

Ảnh được tải lên Cloudinary; API không ghi file vào source, ổ đĩa dự án hay thư mục media local. Django giữ `api_secret` ở secret store/environment server; frontend không bao giờ nhận secret.

Thư mục gốc mặc định là `language-center-management/`. Mỗi ảnh có thư mục riêng dựa trên loại tài nguyên, site (nếu dữ liệu bị phân mảnh theo cơ sở), mã hồ sơ và UUID ảnh do API sinh:

```text
language-center-management/
├── hoc-vien/<ma_site>/<ma_hoc_vien>/anh/<uuid-anh>/
├── giao-vien/<ma_site>/<ma_giao_vien>/anh/<uuid-anh>/
├── khoa-hoc/dung-chung/<ma_khoa_hoc>/anh/<uuid-anh>/
├── co-so/dung-chung/<ma_co_so>/anh/<uuid-anh>/
└── thuong-hieu/dung-chung/<loai-tai-nguyen>/anh/<uuid-anh>/
```

Tên người, email, số điện thoại và nội dung nhạy cảm không được dùng làm tên folder hoặc `public_id`; mã site/mã hồ sơ phải lấy từ bản ghi và quyền đã xác thực ở server. Mã ảnh là UUID ngẫu nhiên riêng cho từng asset. API dự kiến dùng `asset_folder` với Cloudinary Dynamic folders để phân loại trong Media Library mà không bắt buộc đưa đường dẫn folder vào `public_id`; không dùng thư mục để thay thế kiểm soát quyền truy cập. Ảnh cá nhân cần chính sách delivery hạn chế phù hợp. Xem [Cloudinary Folder Modes](https://cloudinary.com/documentation/folder_modes) và [Upload API Reference](https://cloudinary.com/documentation/image_upload_api_reference).

Source hiện có upload intent và endpoint hoàn tất Cloudinary cho ảnh đại diện Admin, Admin Small, giáo viên, nhân viên mới và hồ sơ học viên. Avatar tài khoản cập nhật `TaiKhoan.avatar_public_id`/`avatar_secure_url` theo các bản sao tài khoản; avatar học viên cập nhật hai cột cùng tên trên `HocVien` tại site sở hữu (`LOCAL`). Luồng chuyển cơ sở cũng đọc các cột này để sao chép metadata sang site đích, nên phải áp dụng migration 38 trên mọi site trước khi triển khai source mới. Django kiểm tra quyền/asset; ảnh tải trực tiếp lên Cloudinary. Chưa có API MediaAsset tổng quát hoặc bằng chứng upload thật trên Cloudinary.

Luồng chuẩn: frontend xin upload intent từ API → API cấp chữ ký có thời hạn → frontend gửi bytes ảnh trực tiếp tới Cloudinary → frontend gửi `public_id` về API → API xác minh lại asset rồi gắn metadata vào bản ghi tại site đúng. Nếu upload Cloudinary thành công nhưng ghi metadata thất bại, không báo hoàn tất; ghi nhận asset mồ côi để dọn an toàn.

| Method và path thiết kế | Người gọi | Hành vi |
|---|---|---|
| `POST /api/v1/media/upload-intents` | Người dùng đã xác thực, có quyền sửa hồ sơ/tài nguyên tương ứng | API kiểm tra quyền/site, mục đích và loại ảnh; tạo chữ ký upload Cloudinary hết hạn ngắn, public ID do server sinh |
| `POST /api/v1/media/assets` | Người dùng vừa upload bằng intent hợp lệ | API xác minh chữ ký, public ID, loại tài nguyên, kích thước và metadata từ Cloudinary; sau đó gắn asset vào bản ghi được phép |
| `DELETE /api/v1/media/assets/{ma_media}` | Người có quyền sửa bản ghi sở hữu ảnh | Gỡ liên kết và chỉ xóa asset Cloudinary khi xác nhận không còn tham chiếu; shared asset phải xử lý theo chính sách đồng bộ |

Yêu cầu upload: chỉ MIME ảnh trong allowlist; kiểm tra cả MIME thực và phần mở rộng; giới hạn dung lượng/chiều rộng/chiều cao theo cấu hình; đổi tên bằng public ID phía server; không nhận URL tùy ý rồi tải hộ (tránh SSRF). Có thể dùng Cloudinary transformation để tạo thumbnail/responsive format. Upload intent hết hạn, gắn với tài khoản, site, mục đích và bản ghi được phép; không cho tái sử dụng để ghi đè ảnh tùy ý. Trước khi xóa asset, xác minh không còn bản ghi tham chiếu tại các site cần thiết; nếu xóa metadata/asset bị lỗi giữa chừng, trả trạng thái phục hồi và không để URL hỏng được báo là đã xóa sạch.

SQL Server chỉ lưu metadata (`avatar_public_id`, `avatar_secure_url`): trong `TaiKhoan` cho ảnh tài khoản (`REPLICATED-WRITE`) và trong `HocVien` cho ảnh hồ sơ học viên (`LOCAL` theo site sở hữu). Bytes ảnh ở Cloudinary. Schema chưa có bảng metadata tổng quát cho ảnh khóa học/cơ sở; không tạo database media trung tâm.

## Danh tính, vai trò và phạm vi site

Đây là một API dùng chung cho một frontend. Người dùng không gửi vai trò để tự chọn quyền. API xác định danh tính từ phiên đăng nhập, kiểm tra trạng thái tài khoản và dựng phạm vi trên mỗi request.

| Người dùng | Biểu diễn theo schema hiện tại | Phạm vi API |
|---|---|---|
| Admin Big | `TaiKhoan.vai_tro = admin_big`, `ma_co_so = NULL` | Toàn hệ thống; thao tác nhiều site phải được gắn `GLOBAL`, `REPLICATED-WRITE` hoặc `DISTRIBUTED-TX` rõ ràng |
| Admin Small | `TaiKhoan.vai_tro = nhan_vien`, hồ sơ `Admin.loai_admin = admin_small`, có site được gán | Một site được gán; không được chọn site khác trong query/body để mở rộng quyền |
| Kế toán & Lễ tân | `nhan_vien`, `NhanVien.chuc_vu=ke_toan` (`le_tan` cũ được chuyển bằng migration 41) | Tại site được giao: chỉ xem phòng, lớp/roster, hồ sơ học viên và công nợ; gửi email nhắc phí, xem báo cáo tài chính/phiếu thu và thu/hoàn; không ghi phòng/lớp/hồ sơ, đăng ký/xếp lớp hoặc sửa kế hoạch đóng |
| Tư vấn & xếp lớp | `nhan_vien`, `NhanVien.chuc_vu=tu_van` | Tại site được giao: CRUD hồ sơ học viên nhưng không cấp tài khoản; CRUD phòng; mở lớp, phân công, đăng ký/xếp lớp; sửa tên/sĩ số và hủy mềm lớp đủ điều kiện; xem/nhắc công nợ, chỉ sửa kế hoạch đóng; xem chuyển cơ sở/công nợ nguồn; nhận/phản hồi liên hệ; tạo/sửa/xuất bản Blog dùng chung |
| Giáo viên | `TaiKhoan.vai_tro = giao_vien`, hồ sơ `GiaoVien` tại site | Chỉ lớp/buổi được phân công; API kiểm tra phân công ở mỗi thao tác |
| Học viên | Schema/API/UI có tài khoản và portal trong source; phạm vi đồ án chưa được duyệt | Không đưa vào phạm vi nghiệm thu trước khi nhóm thống nhất và cập nhật các tài liệu liên quan |

`Admin Small` không dùng `TaiKhoan.vai_tro=admin_small`: role đăng nhập là `nhan_vien`, còn hồ sơ phân quyền là `Admin.loai_admin=admin_small`. `NhanVien.chuc_vu` mô tả nhân viên nghiệp vụ. Nếu endpoint nhận bộ lọc `ma_co_so`, API chỉ chấp nhận site đúng quyền; với Admin Big, site đích vẫn phải tồn tại và đang hoạt động. Không dùng tiền tố mã học viên để xác định site hiện hành.

## Endpoint dùng chung: Web công khai và xác thực

Các method/path được ghi là “đã có trong source” phải khớp `src/api/core/urls.py`; route chỉ là thiết kế được ghi rõ “đề xuất” thì chưa phải hợp đồng đang chạy. OAuth còn phụ thuộc cấu hình provider ở từng môi trường. Đăng ký tài khoản công khai không mở; đăng ký khóa học công khai là luồng riêng.

| Method và path | Người gọi | Kiểu truy cập | Dữ liệu đọc/ghi và hành vi |
|---|---|---|---|
| `GET /api/v1/contact/sites/` | Khách chưa đăng nhập | Đọc danh mục `CoSo` từ registry và kiểm tra site hoạt động | Trả site sẵn sàng để form chọn; có `complete`, `site_codes`, `missing_sites`; không trả hồ sơ nội bộ |
| `POST /api/v1/contact/` | Khách chưa đăng nhập | Kiểm tra site hoạt động, ghi `LOCAL` | Nhận họ tên, email, cơ sở, tiêu đề, nội dung và số điện thoại tùy chọn; ghi `YeuCauLienHe` + `Logs` tại site đã chọn trong một transaction cục bộ. Bắt buộc `Idempotency-Key`; rate limit 5/IP/giờ và 3 theo IP+email/giờ; không gửi email tự động khi nhận form |
| `GET /api/v1/public/sites` | Khách chưa đăng nhập | Đề xuất, chưa có route tương ứng trong source | Nếu nhóm cần API danh sách cơ sở công khai, phải bổ sung route theo schema; không giả định endpoint đang chạy |
| `GET /api/v1/courses/` | Khách chưa đăng nhập | `GLOBAL` đọc từng CSDL site riêng | Đọc danh mục `KhoaHoc`/`MonHoc` và số lớp đang mở theo site; trả `scope`, `complete`, `site_codes`, `missing_sites`, `inconsistent_sites`, `count`, `results`; nếu thiếu site, kết quả đánh dấu chưa đầy đủ |
| `GET /api/v1/blog/categories/` | Khách chưa đăng nhập | `GLOBAL` đọc và đối chiếu các bản Blog ở từng site | Đọc `DanhMucBlog`/`BaiVietBlog`; trả danh mục hoạt động, `post_count`, `complete`, `missing_sites`, `inconsistent_sites`; `503` nếu không đọc được site nào |
| `GET /api/v1/blog/{slug}/` | Khách chưa đăng nhập | `GLOBAL` đọc và đối chiếu bài theo slug ở từng site | Chỉ trả bài đã xuất bản nếu các bản khớp; `404` nếu không có, `409` nếu lệch, `503` nếu thiếu site |
| `GET /api/v1/courses/{course_slug}/classes/` | Khách chưa đăng nhập | Route hiện có; truy vấn theo phạm vi API | Đọc lớp công khai của khóa học; đối chiếu status/missing site theo response hiện tại trước khi dùng như hợp đồng |
| `POST /api/v1/auth/login/` | Tài khoản có trong source | `GLOBAL` tra cứu tài khoản nhân bản, xác thực ở Django | Route đã có trong source. Nhận email hoặc tên đăng nhập cùng mật khẩu; tìm danh tính trên các bản `TaiKhoan` site hoạt động, trả cookie phiên và user context, không trả hash mật khẩu hoặc chuỗi kết nối |
| `GET /api/v1/auth/oauth/{provider}/start/` | Học viên chưa đăng nhập hoặc đã xác thực để liên kết | Route hiện có; `provider` chỉ `google` hoặc `facebook` | Tạo state dùng một lần; callback chỉ đăng nhập tài khoản học viên đã liên kết, không tự tạo hoặc ghép theo email |
| `GET /api/v1/auth/oauth/{provider}/callback/` | Callback Google/Facebook | Route hiện có | Đổi authorization code ở server, xác minh provider subject; phụ thuộc OAuth configuration thật |
| `GET /api/v1/auth/oauth/connections/{slug}/` | Học viên đã đăng nhập | Đọc trạng thái liên kết tài khoản theo phiên | Chỉ trả trạng thái liên kết của chính học viên đã xác thực |
| — (không có account signup route) | Khách chưa đăng nhập | Chưa có route trong source và chưa được duyệt phạm vi | `POST /api/v1/public/enrollments/` là đăng ký khóa học công khai, không tạo tài khoản học viên |
| `GET /api/v1/auth/profile/{slug}/` | Người đã đăng nhập | Đọc hồ sơ của chính tài khoản theo slug | Slug phải khớp tài khoản trong phiên; trả vai trò và thông tin được phép hiển thị, không trả bí mật xác thực |
| `POST /api/v1/auth/logout/` | Người đã đăng nhập | Hủy phiên | Route đã có trong source; thu hồi phiên phía server và xóa cookie phiên |
| `GET /api/v1/auth/session/`, `POST /api/v1/auth/activity/` | Người đã đăng nhập | Route hiện có | Đọc session và ghi nhận hoạt động người dùng thật theo chính sách idle timeout |
| `POST /api/v1/auth/password/change/` | Người đã đăng nhập | `LOCAL` kiểm tra tài khoản; `REPLICATED-WRITE` cập nhật bản sao mật khẩu theo chính sách | Route đã có trong source; nhận mật khẩu hiện tại và mật khẩu mới; xác minh bằng bcrypt |
| `POST /api/v1/auth/password/forgot/` | Người chưa đăng nhập | Tra cứu tài khoản; tạo OTP có hạn | Route đã có trong source; luôn trả thông báo không tiết lộ tài khoản/email có tồn tại hay không |
| `POST /api/v1/auth/password/reset/` | Người có OTP đặt lại | `LOCAL` kiểm OTP; cập nhật mật khẩu theo chính sách | Route đã có trong source; mã có hạn và chỉ dùng một lần theo trạng thái lưu hiện có |
| `POST /api/v1/auth/account-activations` | Người có liên kết mời hợp lệ | Đề xuất; chưa có route/schema token kích hoạt trong source | Không dùng như endpoint đang hoạt động; quy trình source hiện cấp mật khẩu khởi tạo theo cấu hình và email thông tin tài khoản |

API không có endpoint đăng ký tài khoản công khai; source có `POST /api/v1/public/enrollments/` để gửi đăng ký khóa học, không phải tạo tài khoản. Admin Big tạo tài khoản nội bộ. Portal học viên có code/schema nhưng chưa được duyệt vào phạm vi đồ án; không bật public signup.

### Liên hệ website — form công khai và hộp thư quản trị

`GET /api/v1/contact/sites/` trả các site đang hoạt động và có kết nối để form công khai cho khách chọn. `POST /api/v1/contact/` ghi yêu cầu vào đúng CSDL site được chọn sau khi kiểm tra danh mục `CoSo`/trạng thái site; dữ liệu `YeuCauLienHe`, `Logs` không được lưu ở database trung tâm. API chuẩn hóa email, kiểm tra độ dài/định dạng, giới hạn gửi theo IP và IP+email; frontend giữ nguyên `Idempotency-Key` cùng body khi retry. Throttle dùng Django cache; cache mặc định `LocMemCache` giới hạn riêng theo worker, nên cần shared cache nếu chạy nhiều worker. Form gửi chỉ tạo yêu cầu `cho_xu_ly`, không tự gửi thư.

| Route | Người gọi | Kiểu | Hành vi |
|---|---|---|---|
| `GET /api/v1/admin/contacts/?site_code=...&status=...&search=...&limit=...&offset=...` | Admin Big/Admin Small/Tư vấn & xếp lớp | Admin Big bỏ `site_code`: `GLOBAL`; chọn site: `LOCAL`; Admin Small/Tư vấn: `LOCAL` | Đọc riêng `YeuCauLienHe` tại từng site rồi tổng hợp trong API; nhân sự site không được vượt phạm vi. Nếu thiếu site, response `503` có `complete=false`/`missing_sites` và phần kết quả đọc được |
| `POST /api/v1/admin/contacts/{site_code}/{request_id}/reply/` | Admin Big/Admin Small/Tư vấn & xếp lớp đúng site | `LOCAL` | Lấy email từ bản ghi, gửi phản hồi plain text qua SMTP; khi SMTP chấp nhận, cập nhật trạng thái/nội dung phản hồi và `Logs` trong transaction tại site đó. Lỗi SMTP trả `503` với `code=smtp_unavailable`; lỗi database báo site chưa sẵn sàng. Không ghi nội dung/email vào nhật ký; mỗi yêu cầu chỉ phản hồi một lần |

API gọi SMTP trong khi transaction tại site sở hữu đang mở, sau đó cập nhật dữ liệu; hai hệ thống không có commit nguyên tử. Nếu SMTP chấp nhận thư nhưng commit SQL lỗi, yêu cầu có thể còn `cho_xu_ly` và lần gửi lại có thể gửi trùng; transactional outbox là hướng nâng cấp nếu cần đóng khoảng hở này. Nếu SMTP chưa cấu hình hoặc báo lỗi trước khi chấp nhận, yêu cầu giữ `cho_xu_ly`. SMTP trả chấp nhận không chứng minh email đã đến inbox. Site được xác thực từ danh mục `CoSo` và Site Router; API không nhận email đích, tài khoản Admin hoặc site được phân quyền từ nội dung body reply.

### Blog — đọc công khai và CMS Admin Big/Tư vấn đã có trong source

Hai route chỉ đọc và cho phép khách chưa đăng nhập:

- `GET /api/v1/blog/categories/` trả `{scope, complete, site_codes, missing_sites, inconsistent_sites, count, results}`. Mỗi danh mục có `slug`, `name`, `description`, `post_count`. `post_count` chỉ tính bài `da_xuat_ban` đã tới thời điểm xuất bản.
- `GET /api/v1/blog/{slug}/` trả `{scope, complete, site_codes, result}`. `result` có `slug`, `title`, `excerpt`, `content` là chuỗi Markdown giới hạn, `reading_time_minutes`, `published_at` và `category: {slug, name}`. Hỗ trợ đoạn văn, tiêu đề `##`/`###`, danh sách đánh số và bảng Markdown; các khối này có thể bỏ qua.

Admin Big dùng toàn bộ route CMS; Tư vấn & xếp lớp dùng các route đọc và tạo/sửa bài viết. Phiên và vai trò phải được xác thực ở server, không nhận site hoặc role từ client:

| Route | Hành vi |
|---|---|
| `GET /api/v1/admin/blog/categories/` | Admin Big/Tư vấn: đọc mọi danh mục và trạng thái, kèm số bài đang tham chiếu; trả trạng thái đối chiếu site. |
| `POST /api/v1/admin/blog/categories/` | Tạo danh mục `{slug, name, description?, status?}`. |
| `GET /api/v1/admin/blog/categories/{slug}/` | Đọc một danh mục mọi trạng thái. |
| `PATCH /api/v1/admin/blog/categories/{slug}/` | Sửa một phần `slug`, `name`, `description`, `status`. |
| `DELETE /api/v1/admin/blog/categories/{slug}/` | Xóa danh mục chỉ khi không có bài viết tham chiếu. |
| `GET /api/v1/admin/blog/articles/` | Admin Big/Tư vấn: đọc metadata bài viết mọi trạng thái (không tải toàn bộ `content` cho danh sách); dùng route chi tiết để lấy nội dung. |
| `POST /api/v1/admin/blog/articles/` | Admin Big/Tư vấn tạo `{slug, category_slug, title, excerpt, content, reading_time_minutes, status?, published_at?}`. `content` là chuỗi Markdown giới hạn tối đa 20.000 ký tự, không phải HTML; `published_at` nhận thời điểm ISO có offset và lưu UTC tới giây. |
| `GET /api/v1/admin/blog/articles/{slug}/` | Admin Big/Tư vấn đọc một bài ở mọi trạng thái. |
| `PATCH /api/v1/admin/blog/articles/{slug}/` | Admin Big/Tư vấn sửa một phần các trường của bài viết, gồm `category_slug`, nội dung Markdown giới hạn và thời điểm ISO có offset `published_at` (lưu UTC tới giây). |
| `DELETE /api/v1/admin/blog/articles/{slug}/` | Xóa bài viết và ghi ảnh chụp trước thao tác vào ACK đồng bộ tại từng site. |

Trường `published_at` vẫn nhận ISO timestamp có offset; CMS chỉ cho chọn ngày, mặc định ngày tạo theo `Asia/Ho_Chi_Minh`, rồi gửi thời điểm 00:00 tại múi giờ này. Để trống ngày gửi `null` để xuất bản ngay khi trạng thái cho phép.

Mọi request ghi yêu cầu `Idempotency-Key` hợp lệ. Tất cả thao tác CMS thuộc `REPLICATED-WRITE`; Admin Big quản trị toàn bộ, Tư vấn & xếp lớp chỉ tạo/sửa bài viết và không xóa bài hoặc ghi danh mục. Bài viết được chia sẻ toàn hệ thống, nên quyền ghi của Tư vấn không giới hạn ở site được phân công. Coordinator lấy các site hoạt động từ dữ liệu/cấu hình, dùng transaction cục bộ trên từng database và ghi ACK `Logs` cùng dữ liệu. Không có DB trung tâm hoặc khóa ngoại/JOIN xuyên site và không tuyên bố ACID nguyên tử xuyên database. Retry phải dùng lại cùng key, cùng route/path và cùng payload; key đã dùng cho nội dung khác trả `409`. Site thiếu trước khi bắt đầu ghi trả `503`; lỗi site sau khi một phần đã commit trả `202`, `complete=false`, `missing_sites` để retry. Bản sao Blog khác nhau trả `409`; slug sai/trùng và danh mục bài viết không tồn tại/đang ngừng được từ chối. Danh mục đang được bài viết dùng không thể xóa.

Site tham gia là mọi cơ sở `hoat_dong` có cấu hình Site Router. Ghi đọc/đối chiếu `DanhMucBlog` hoặc `BaiVietBlog` tại từng site; mỗi transaction cục bộ ghi thêm `Logs` (`loai_log='sync'`) để giữ ACK/idempotency và trạng thái trước/sau. Với bài viết, `category_slug` được giải ra khóa danh mục nội bộ riêng tại từng database; không đồng bộ giá trị `IDENTITY` giữa site.

Hai route GET collection trả `{scope, complete, site_codes, missing_sites, inconsistent_sites, count, results}`; GET detail trả `{scope, complete, site_codes, result}`. Collection danh mục có `post_count` mọi trạng thái; collection bài viết trả metadata, không tải `content` toàn bộ. Nếu thiếu site, collection vẫn trả danh sách canonical kèm `complete=false`; detail cần xác nhận đủ site và trả `503` khi thiếu.

Các route đọc công khai và CMS đọc từng CSDL site riêng qua Site Router. Migration 36 tạo dữ liệu mẫu ban đầu, không phải writer replication. Public list có thể trả `200` cùng `complete=false` và site thiếu/lệch; public detail trả `404` nếu không có slug, `409` nếu bản sao khác nhau, `503` nếu không đọc đủ site. Frontend chỉ chuyển các khối Markdown được hỗ trợ thành phần tử React; HTML thô không được render hoặc thực thi. Có API CMS không đồng nghĩa đã chạy TC-REP-01/TC-SYNC-01; cần kiểm chứng thay đổi thật, lỗi site, retry và đối soát trên SQL Server thật.

### Đăng nhập và liên kết tài khoản Google/Facebook — đã có code, cần cấu hình môi trường

Đăng nhập bằng mật khẩu và các route OAuth Google/Facebook có trong source. OAuth chỉ dành cho học viên đã liên kết danh tính trước đó; không thay thế đăng nhập nội bộ, không tự đăng ký và không tự liên kết theo email. Tính sẵn sàng ở môi trường triển khai còn phụ thuộc OAuth applications, biến môi trường và kiểm chứng cấu hình.

**Luồng đăng nhập:**

1. Học viên đã liên kết bấm nhà cung cấp tương ứng; trình duyệt mở `GET /api/v1/auth/oauth/google/start/` hoặc `.../facebook/start/`. Backend chỉ nhận provider từ allowlist, tạo state ngẫu nhiên dùng một lần (và nonce cho Google), gắn với trình duyệt bằng cookie bảo mật tạm thời rồi chuyển hướng sang provider. `redirect_uri` được cấu hình cố định ở API, không lấy từ query/body.
2. Google/Facebook trả authorization code về callback đã đăng ký của API. Backend đối chiếu state/cookie, đổi code trực tiếp với provider qua HTTPS rồi xác minh; không chuyển provider token sang frontend và không ghi code/token vào log.
3. Google ID token phải được xác minh chữ ký bằng JWKS chính thức và kiểm tra `iss`, `aud`, `exp`, `iat`, `nonce`; định danh bền vững là `sub`, không phải email. Facebook access token phải được introspect server-to-server (app ID đúng, token hợp lệ, đúng subject và chưa hết hạn); sau đó lấy Facebook app-scoped user ID. Chỉ yêu cầu quyền dữ liệu tối thiểu.
4. API tìm provider subject trong `TaiKhoan.google_subject` hoặc `TaiKhoan.facebook_subject` tại từng CSDL site riêng, sau đó xác nhận các bản sao `TaiKhoan` nhất quán, tài khoản đang hoạt động và vai trò/phạm vi còn hợp lệ. Đây là `GLOBAL`; nếu site cần thiết mất kết nối hoặc các bản sao mâu thuẫn, từ chối cấp phiên và trả lỗi tạm thời, không âm thầm chọn một bản.
5. Sau khi xác minh, API tạo phiên ứng dụng riêng bằng cơ chế phiên có thể thu hồi đã chốt, đặt cookie `HttpOnly`, `Secure`, `SameSite` phù hợp và redirect về URL callback web trong allowlist. Không trả Google/Facebook token hoặc quyền do provider cung cấp về trình duyệt. Frontend gọi `GET /api/v1/auth/profile/{slug}/` với slug của chính tài khoản để nhận hồ sơ phiên; route profile theo slug đã có trong source.

Facebook có thể không trả email hoặc người dùng có thể từ chối quyền email; điều đó không ảnh hưởng xác thực vì API dùng Facebook user ID. Không yêu cầu quyền `email` chỉ để ghép tài khoản. Google email đã xác minh cũng không dùng làm khóa: chỉ subject đã liên kết mới đăng nhập được.

**Luồng liên kết:** người dùng đăng nhập bằng tài khoản nội bộ hiện hữu, xác thực lại bằng mật khẩu gần thời điểm liên kết, rồi bắt đầu OAuth trong chế độ `link`. Callback chỉ ghi subject vào cột provider tương ứng của `TaiKhoan` lấy từ phiên đã xác thực. Nếu subject đã thuộc tài khoản khác, API từ chối; không tự chuyển liên kết. Thu hồi liên kết đặt cột tương ứng về `NULL` qua Replicated-Write đủ site. Không có chức năng tự đăng ký qua Google/Facebook hoặc Admin Big gắn danh tính cho người khác.

**Redirect và lỗi:** callback URL/`return_to` chỉ lấy từ allowlist cấu hình; từ chối URL tùy ý để chống open redirect. Sai state, code hết hạn, provider lỗi, identity chưa liên kết, tài khoản bị khóa hoặc dữ liệu site không đủ đều không tạo phiên. Người dùng nhận thông báo chung; nhật ký chỉ ghi provider, mã lỗi nội bộ, kết quả và mã tài khoản nếu xác định an toàn. Không ghi authorization code, ID/access/refresh token, client secret, email hoặc provider subject.

**Phân tán:** provider subject nằm ngay trên bảng `TaiKhoan` đã nhân bản ở từng site, không có bảng OAuth riêng hoặc CSDL identity trung tâm. Liên kết/thu hồi là `REPLICATED-WRITE` qua một service duy nhất; cập nhật cột provider tương ứng tới mọi site hoạt động. Nếu một site bắt buộc lỗi, không báo thành công; lưu kết quả để retry/đối soát. Đăng nhập là `GLOBAL`, đọc từng site riêng rồi đối chiếu ở API. Không có FK/JOIN xuyên site. Vai trò và site luôn lấy từ `TaiKhoan`, không lấy từ provider profile.

**Cấu hình:** tạo OAuth application riêng cho môi trường phát triển và cấu hình được duyệt cho môi trường triển khai; khai báo callback chính xác trong Google Cloud và Meta Developers. API cần `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI`, `FACEBOOK_OAUTH_APP_ID`, `FACEBOOK_OAUTH_APP_SECRET`, `FACEBOOK_OAUTH_REDIRECT_URI` và `OAUTH_WEB_RETURN_URL`. Client secret chỉ ở Django/environment, không ở Next.js, Git, Swagger example hay log. Trước khi bật phải hoàn tất TLS, state/nonce dùng một lần, cookie/CSRF, rate limit riêng từng provider và cơ chế phiên có thể thu hồi.

Start/callback là redirect của trình duyệt, không nhận provider token từ frontend. Khi liên kết, API lấy tài khoản hiện tại từ cookie phiên, không nhận `ma_tai_khoan` từ request. Callback thành công đặt cookie phiên của ứng dụng và redirect tới trang đã cấu hình; các endpoint chỉ xuất hiện trong Swagger khi có code đã triển khai và test tích hợp.

## Endpoint quản trị theo Admin Big và Admin Small

Các quyền dưới đây phải được kiểm tra ở API, không chỉ ẩn menu. `GLOBAL` chỉ dành cho màn hình tổng hợp/tra cứu toàn cục; không có câu SQL JOIN tới database của site khác.

Với các route collection `GET /api/v1/admin/students/`, `/employees/`, `/teachers/`, `/classes/` và `/tuition/`, Admin Big bỏ `site_code` để đọc `GLOBAL` mặc định; truyền một `site_code` hoạt động để giới hạn `LOCAL`. Mỗi dòng toàn cục có `site_code`. Nếu thiếu site, trả `complete=false`, liệt kê `missing_sites` và để `count=null`; không xem site lỗi như site không có dữ liệu. Admin Small/nhân viên vẫn bị giới hạn theo site trong phiên. Các thao tác ghi hoặc đọc chi tiết cần site cụ thể và được kiểm tra quyền ở server.

| Method và path | Người gọi | Kiểu phân tán | Site và bảng chính |
|---|---|---|---|
| `GET /api/v1/admin/sites` | Admin Big | Đọc bản sao `CoSo`; tổng hợp trạng thái kết nối theo nhu cầu | `CoSo` ở bản sao tại site; không trả thông tin bí mật kết nối |
| `GET /api/v1/admin/sites/{ma_co_so}` | Admin Big | Đọc bản sao `CoSo` và trạng thái site | Chi tiết cơ sở; không trả credential/chuỗi kết nối |
| `GET /api/v1/admin/dashboard` | Admin Big | Đề xuất, chưa có route source | Dashboard web hiện tổng hợp dữ liệu từ `GET /api/v1/admin/reports/students-by-site/`; không gọi endpoint này |
| `POST /api/v1/admin/sites` | Admin Big | Điều phối cấu hình + nạp dữ liệu dùng chung | Tạo metadata và khởi chạy quy trình provisioning; không cho trình duyệt truyền credential SQL Server |
| `PATCH /api/v1/admin/sites/{ma_co_so}/status` | Admin Big | `REPLICATED-WRITE`/quy trình đóng site | Chỉ nhận trạng thái cho phép; trước khi đóng phải xử lý giao dịch chuyển và dữ liệu đang hoạt động theo README mục 5.14 |
| `GET /api/v1/admin/admins-small` | Admin Big | `GLOBAL` hoặc đọc bản sao tài khoản kèm tra cứu hồ sơ từng site | Gộp Admin Small theo site; phản hồi một phần nếu site thiếu |
| `GET /api/v1/admin/admins-small/{ma_tai_khoan}` | Admin Big | `GLOBAL` định vị rồi `LOCAL` đọc hồ sơ | Chi tiết tài khoản và cơ sở được phân công; báo rõ site thiếu |
| `GET, POST /api/v1/admin/admin-smalls/` | Admin Big | Đọc `GLOBAL`; tạo tài khoản `REPLICATED-WRITE` + hồ sơ `LOCAL` | Route source: liệt kê hoặc tạo Admin Small. Danh sách trả `avatar_secure_url` từ bản sao `TaiKhoan`; trường có thể `null`. Tài khoản có role `nhan_vien`; hồ sơ là `Admin.loai_admin = admin_small` tại site được gán, không phải `NhanVien.chuc_vu`. Request tạo dùng `full_name`, `email`, `site_code` (username/slug tùy chọn). |
| `DELETE /api/v1/admin/admin-smalls/{account_id}/` | Admin Big | `REPLICATED-WRITE` theo từng transaction cục bộ | Xóa vật lý hồ sơ `Admin`, các bản sao `TaiKhoan`, phiên/token đặt lại mật khẩu và ảnh Cloudinary; giữ `Logs`, điểm danh, lịch sử chuyển cơ sở và chứng từ. Từ chối trước khi ghi nếu còn hồ sơ nghiệp vụ, yêu cầu thanh toán hoặc giao dịch chuyển cơ sở đang mở. Có dấu tiến trình/retry; không bảo đảm ACID xuyên CSDL |
| `PATCH /api/v1/admin/admin-smalls/{slug}/status/` | Admin Big | `REPLICATED-WRITE` | Chỉ đổi trạng thái `active`/`inactive`; không xóa hồ sơ hoặc dữ liệu. Đây là thao tác riêng với DELETE |
| `GET /api/v1/admin/accounts` | Admin Big | `GLOBAL`/bản sao tài khoản | Danh sách tài khoản nội bộ, trạng thái và phạm vi; không trả hash mật khẩu |
| `GET /api/v1/admin/accounts/{ma_tai_khoan}` | Admin Big | Đọc bản sao tài khoản và tra cứu hồ sơ site cần thiết | Chi tiết tài khoản/phạm vi được phép; không trả hash hoặc secret |
| `PATCH /api/v1/admin/accounts/{ma_tai_khoan}/status` | Admin Big | `REPLICATED-WRITE` | Khóa/mở tài khoản qua dịch vụ đồng bộ chung; không cho tự khóa tài khoản Admin Big cuối cùng nếu nhóm đặt quy tắc đó |
| `GET /api/v1/admin/teachers/?site_code=...&status=...&search=...&limit=...&offset=...` | Admin Big; Admin Small đúng site | Admin Big bỏ site: `GLOBAL`; có site: `LOCAL`; Admin Small: `LOCAL` | Đọc `GiaoVien`, `TaiKhoan`, `Logs` riêng tại từng site; mỗi dòng có `site_code`; kết quả một phần có `complete=false`/`missing_sites` và `count=null`; endpoint quản lý roster chỉ dành cho Admin |
| `GET /api/v1/admin/teachers/assignment-options/?site_code=...&limit=...&offset=...` | Admin Big chọn site; Admin Small/Tư vấn & xếp lớp dùng site trong phiên | `LOCAL` | Đọc `GiaoVien` tại một site; trả giáo viên `dang_day` chỉ gồm `teacher_id` và `full_name`, không trả thông tin liên hệ/trạng thái tài khoản; nhân viên không được gửi `site_code` từ client |
| `POST /api/v1/admin/teachers/` | Admin Big hoặc Admin Small theo quyền | Tạo tài khoản `REPLICATED-WRITE` + hồ sơ `LOCAL` | Tạo tại site được chỉ rõ/được cấp; không nhận role tùy ý |
| `GET, DELETE /api/v1/admin/teachers/{slug}/?site_code=...` | Admin Big hoặc Admin Small đúng site | Đọc `LOCAL`; xóa mềm/tắt tài khoản theo các site và hồ sơ tại site | Route source: GET chi tiết; DELETE vô hiệu hóa tài khoản và chuyển hồ sơ sang nghỉ việc, giữ dữ liệu lịch sử |
| `PATCH /api/v1/admin/teachers/{slug}/status/?site_code=...` | Admin Big hoặc Admin Small đúng site | Tài khoản `REPLICATED-WRITE` + hồ sơ `LOCAL` | Route source: đổi trạng thái tài khoản/hồ sơ giáo viên, thu hồi phiên; không phải endpoint cập nhật phân công lớp |
| `GET /api/v1/admin/classes/?site_code=...&status=...&search=...&limit=...&offset=...` | Admin Big; Admin Small/Kế toán & Lễ tân/Tư vấn & xếp lớp đúng site | Admin Big bỏ site: `GLOBAL`; có site: `LOCAL`; nhân viên: `LOCAL` | Đọc `LopHoc` và đối chiếu `DangKy` tại từng CSDL site; mỗi dòng có `site_code`; site thiếu được nêu rõ |
| `POST /api/v1/admin/classes/` | Admin Big; Admin Small/Tư vấn & xếp lớp tại site | `LOCAL` | Đọc `KhoaHoc`, `GiaoVien`, `PhongHoc`; ghi `LopHoc`, `BuoiHoc`, `Logs` trong một transaction; nhân viên chỉ dùng site trong phiên |
| `PATCH /api/v1/admin/classes/{class_id}/?site_code=...` | Admin Big; Admin Small/Tư vấn & xếp lớp tại site | `LOCAL` | Sửa tên lớp/sĩ số tối đa; không sửa lớp kết thúc/hủy, không thấp hơn số đăng ký hoặc vượt sức chứa phòng; ghi `LopHoc` và `Logs` cùng transaction. Kế toán & Lễ tân chỉ đọc |
| `DELETE /api/v1/admin/classes/{class_id}/?site_code=...` | Admin Big; Admin Small/Tư vấn & xếp lớp tại site | `LOCAL` | Hủy mềm lớp `sap_mo` chưa có đăng ký và mọi buổi vẫn ở tương lai/trạng thái `du_kien`; đặt `LopHoc.trang_thai='huy'`, giữ `LopHoc`, `BuoiHoc`, `Logs`; Kế toán & Lễ tân chỉ đọc |
| `PUT /api/v1/admin/classes/{class_id}/teacher/` | Admin Big; Admin Small/Tư vấn & xếp lớp đúng site | `LOCAL` | Route source: gán giáo viên cho lớp tại site sở hữu lớp; kiểm tra giáo viên và lớp cùng site |
| `GET /api/v1/admin/tuition/?site_code=...&status=...&student_slug=...&search=...&limit=...&offset=...` | Admin Big; Admin Small/Kế toán & Lễ tân/Tư vấn tại site | Admin Big bỏ site: `GLOBAL`; có site: `LOCAL`; nhân viên: `LOCAL` | Đọc `HocPhi`, `DangKy`, `HocVien`, `LopHoc` riêng tại từng site; `status=con_no` lọc số dư dương, `search` tìm tên/mã học viên hoặc tên/mã lớp; mỗi dòng có `site_code`; nếu site lỗi trả `complete=false`/`missing_sites`, `count=null`. Tư vấn chỉ xem công nợ và gửi nhắc phí |
| `GET, PUT /api/v1/admin/tuition/{tuition_id}/installments/?site_code=...` | Admin Big; Admin Small/Tư vấn & xếp lớp tại site | `LOCAL` | Đọc hoặc cập nhật kế hoạch `DotHocPhi` tại site sở hữu khoản `HocPhi`. Tư vấn chỉ đổi kế hoạch trước lần thu đầu; không sửa tổng phí, thu/hoàn hoặc phiếu thu. Kế toán & Lễ tân chỉ xem số dư và thao tác phiếu thu/hoàn |
| `GET /api/v1/admin/shared/subjects/` | Admin Big | `GLOBAL` chỉ đọc | Đọc `MonHoc` từ từng site đang hoạt động và tổng hợp danh sách ở API. Trả `complete`, `missing_sites`, `inconsistent_sites`; không cho chọn môn nếu danh mục chưa được đối chiếu đầy đủ |
| `PATCH /api/v1/admin/shared/subjects/{slug}/` | Admin Big | `REPLICATED-WRITE` theo từng transaction cục bộ | Route đã có: cập nhật `MonHoc` trên mọi site hoạt động, ghi ACK vào `Logs`, bắt buộc `Idempotency-Key`; trả `200` khi đủ site, `202` khi còn site cần retry, `409` khi key/body hoặc bản sao xung đột. Không tạo môn mới |
| `POST /api/v1/admin/courses/` | Admin Big | `REPLICATED-WRITE` theo từng transaction cục bộ | Tạo `KhoaHoc` ở các site hoạt động; `ma_khoa_hoc` tối đa 30 ký tự, bắt đầu bằng chữ in hoa, tiếp theo là chữ in hoa/chữ số và có thể chứa các đoạn bổ sung ngăn bằng dấu gạch nối đơn (ví dụ `FG`, `HK-TOEIC-450-550`); giao diện chuẩn hóa mã nhập thành chữ in hoa. API bắt buộc `ma_mon` tồn tại và có bản sao giống nhau tại mọi site; `so_buoi` là tổng số buổi theo chương trình và được nhập riêng, không suy ra từ số tháng; thời lượng tháng nhận số thập phân tối đa 2 chữ số, thời lượng ngày phải nguyên; ghi ACK `Logs`, retry bằng cùng `Idempotency-Key` |
| `PATCH /api/v1/admin/courses/{slug}/` / `DELETE /api/v1/admin/courses/{slug}/` | Admin Big | `REPLICATED-WRITE` theo từng transaction cục bộ | Cập nhật/xóa khóa học dùng chung tại các site với cùng quy tắc thời lượng; khi đổi `ma_khoa_hoc`, áp dụng cùng quy tắc định dạng tối đa 30 ký tự (giao diện chuẩn hóa thành chữ in hoa) và đồng bộ mã cùng các tham chiếu lớp liên quan; xóa bị từ chối nếu lớp còn tham chiếu; dùng `Idempotency-Key` và xử lý retry/đối soát |
| `GET /api/v1/admin/notifications/` | Admin Big hoặc Admin Small | Admin Big: `GLOBAL`; Admin Small: `LOCAL` | Đọc `ThongBao`; kết quả toàn cục được gộp ở API, báo `complete=false`/`missing_sites` khi thiếu site; không theo dõi ai đã đọc |
| `POST /api/v1/admin/notifications/` | Admin Big hoặc Admin Small | Admin Big: `REPLICATED-WRITE`; Admin Small: `LOCAL` | Ghi `ThongBao` và `Logs` hiện có. Admin Big ghi các site hoạt động; Admin Small chỉ ghi site được gán. Bắt buộc `Idempotency-Key`; 200 đủ site, 202 còn site thiếu, 409 cùng key nhưng khác nội dung. Mỗi site có transaction cục bộ, không phải ACID xuyên site |
| `GET /api/v1/students?search=...&trang_thai=...&cursor=...&limit=...` | Admin Big; Admin Small/Kế toán & Lễ tân/Tư vấn & xếp lớp trong site | Admin Big: `GLOBAL`; nhân viên cơ sở: `LOCAL` | Tìm/lọc `HocVien`, phân trang; giới hạn kết quả theo phạm vi người gọi, không đoán site bằng tiền tố mã. Kế toán & Lễ tân chỉ đọc; quyền CRUD của Tư vấn được thực hiện qua các route `/admin/students/` bên dưới |
| `POST /api/v1/students` | Admin Small/Tư vấn & xếp lớp đúng site; luồng tiếp nhận theo quyền được nhóm chốt | `LOCAL` | Tạo `HocVien` tại site do API lấy từ tài khoản; không nhận site tùy ý từ client |
| `GET /api/v1/students/{ma_hoc_vien}` | Admin Big; Admin Small/Tư vấn & xếp lớp đúng site theo endpoint được bật | Admin Big: `GLOBAL` định vị hồ sơ hiện hành; nhân viên: `LOCAL` | Trả hồ sơ theo quyền; không JOIN xuyên CSDL |
| `PATCH /api/v1/students/{ma_hoc_vien}` | Admin Small/Tư vấn & xếp lớp đúng site; luồng cập nhật theo quyền được nhóm chốt | `LOCAL` | Chỉ cho sửa trường hồ sơ được phép; kiểm tra version để tránh ghi đè cập nhật mới |
| `GET /api/v1/classes` / `POST /api/v1/classes` | Admin Small đúng site | `LOCAL` | Đọc/tạo `LopHoc`; khi tạo lịch phải kiểm tra khóa học, giáo viên, phòng, lịch và sức chứa cùng site |
| `GET /api/v1/admin/rooms/` hoặc `?site_code=...` | Admin Big; Admin Small, Kế toán & Lễ tân, Tư vấn & xếp lớp tại site được phân công | Admin Big không truyền site: `GLOBAL`; site cụ thể/nhân viên: `LOCAL` | Đọc `PhongHoc`, `LopHoc`, `BuoiHoc`, `DangKy`, `HocVien` riêng tại site; trả số lớp/học viên theo phòng. Global Query hỏi từng CSDL site hoạt động, phân trang và gắn `site_code`; trả `complete`/`missing_sites` khi có lỗi; không lưu kết quả hay JOIN xuyên CSDL |
| `GET /api/v1/admin/rooms/{ma_phong}/?site_code=...` | Admin Big chọn site; Admin Small, Kế toán & Lễ tân, Tư vấn & xếp lớp chỉ dùng site trong phiên | `LOCAL` | Đọc phòng, lớp/buổi sử dụng phòng, học viên đăng ký hiện hành và tổng phải thu/đã thu/còn nợ từ `HocPhi`; API roster không cho sửa hồ sơ/học phí |
| `POST /api/v1/admin/classes/{ma_lop}/tuition-reminders/?site_code=...` | Admin Big/Admin Small; Kế toán & Lễ tân và Tư vấn & xếp lớp có hồ sơ nhân viên đúng site/chức vụ | `LOCAL` | Tính dư nợ của học viên thuộc lớp tại CSDL site rồi gửi email; ghi kết quả tối thiểu vào `Logs`; giới hạn một email/lớp/học viên/ngày Việt Nam. Cần SMTP; response gửi thành công không chứng minh email tới inbox |
| `GET /api/v1/admin/transfers/?site_code=...` | Admin Big; Admin Small, Kế toán & Lễ tân, Tư vấn & xếp lớp | Admin Big: `GLOBAL` (hoặc chọn một site); Admin Small: truy vấn các nguồn rồi lọc đề nghị phát sinh tại site mình/gửi tới site mình; Kế toán/Tư vấn: `LOCAL` theo site phiên | Trả yêu cầu chuyển cùng phải thu/đã thu/còn nợ tại site nguồn từ `DangKy`/`HocPhi`; không JOIN site đích. Chỉ Tư vấn tạo đề nghị; Kế toán chỉ đọc; Admin Big hoặc Admin Small đúng site nhận được quyết định; retry chỉ Admin Big |
| `POST /api/v1/admin/rooms/` | Admin Big chọn site; Admin Small/Tư vấn & xếp lớp tại site được phân công | `LOCAL` | Tạo `PhongHoc` và ghi `Logs` cùng transaction tại một site; phòng mới `hoat_dong`. Kế toán & Lễ tân không có quyền ghi |
| `PATCH /api/v1/admin/rooms/{ma_phong}/?site_code=...` | Admin Big chọn site; Admin Small/Tư vấn & xếp lớp tại site được phân công | `LOCAL` | Sửa tên, sức chứa, trạng thái; tên duy nhất trong site, sức chứa không thấp hơn sĩ số tối đa của lớp đang tham chiếu; cập nhật `PhongHoc` và `Logs` cùng transaction. Kế toán & Lễ tân không có quyền ghi |
| `DELETE /api/v1/admin/rooms/{ma_phong}/?site_code=...` | Admin Big chọn site; Admin Small/Tư vấn & xếp lớp tại site được phân công | `LOCAL` | Xóa phòng chưa được `LopHoc`/`BuoiHoc` sử dụng; ghi `Logs` cùng transaction. Trả `409` nếu còn tham chiếu để giữ lịch sử và khóa ngoại. Kế toán & Lễ tân không có quyền ghi |
| `GET /api/v1/classes/{ma_lop}` / `PATCH /api/v1/classes/{ma_lop}` | Admin Small đúng site; giáo viên chỉ đọc lớp được giao | `LOCAL` | Không cho đổi lớp sang site khác; ghi nhật ký các thay đổi quan trọng |
| `GET /api/v1/classes/{ma_lop}/sessions` / `POST /api/v1/classes/{ma_lop}/sessions` | Admin Small đúng site; giáo viên được phân công chỉ đọc | `LOCAL` | Đọc/tạo `BuoiHoc`; kiểm tra phòng, giờ, giáo viên và trùng lịch trong cùng site |
| `PATCH /api/v1/classes/{ma_lop}/sessions/{ma_buoi}` | Admin Small đúng site | `LOCAL` | Sửa lịch/buổi hợp lệ, cập nhật audit và từ chối nếu phát sinh xung đột |
| `GET /api/v1/site/dashboard` | Admin Small, Kế toán & Lễ tân, Tư vấn & xếp lớp đúng site | `LOCAL` | Tóm tắt việc cần xử lý tại site được gán; chỉ trả widget phù hợp quyền |
| `GET /api/v1/enrollments?ma_hoc_vien=...&ma_lop=...` | Admin Small/Kế toán & Lễ tân/Tư vấn & xếp lớp tại site; Admin Big theo quyền | `LOCAL` hoặc `GLOBAL` theo phạm vi được cấp | Đọc `DangKy`; API giới hạn site, phân trang và trạng thái |
| `GET /api/v1/enrollments/{ma_dang_ky}` | Admin Small/Kế toán & Lễ tân/Tư vấn & xếp lớp đúng site; Admin Big theo quyền | `LOCAL` hoặc định vị rồi `LOCAL` | Chi tiết đăng ký, lớp và khoản học phí liên quan; không JOIN xuyên site |
| `GET /api/v1/admin/tuition/?site_code=...&status=...&search=...&limit=...&offset=...` | Kế toán & Lễ tân/Admin Small tại site; Admin Big theo phạm vi | `LOCAL` hoặc `GLOBAL` | Đã triển khai: đọc `HocPhi` cùng `DangKy`/`HocVien`/`LopHoc`, tìm theo tên/mã học viên hoặc lớp, phân trang. `status=con_no` lọc số dư dương; mỗi dòng trả số phải thu, đã thu và còn lại |
| `GET /api/v1/tuition/{ma_hoc_phi}` | Kế toán & Lễ tân/Admin Small theo quyền; Admin Big theo quyền | `LOCAL` hoặc định vị rồi `LOCAL` | Chi tiết khoản phí, dư nợ và lịch sử thu/hoàn tại site sở hữu dữ liệu |
| `GET /api/v1/tuition-receipts?ma_hoc_phi=...&ma_hoc_vien=...&ma_phieu=...&tu_ngay=...&den_ngay=...&loai=...&cursor=...&limit=...` | Kế toán & Lễ tân; Admin Small theo quyền; Admin Big theo quyền | `LOCAL` hoặc `GLOBAL` theo phạm vi | Tìm/lọc biên nhận theo học phí, học viên, mã phiếu, khoảng ngày và loại thu/hoàn; phân trang, giới hạn site và quyền tài chính |
| `GET /api/v1/tuition-receipts/{ma_phieu}` | Kế toán & Lễ tân; Admin Small theo quyền; Admin Big theo quyền | `LOCAL` hoặc định vị rồi `LOCAL` | Chi tiết biên nhận/hoàn tiền; không trả dữ liệu thẻ hoặc bí mật cổng |
| `GET /api/v1/reports/site-summary?ma_co_so=...&tu_ngay=...&den_ngay=...` | Admin Big; Admin Small đúng site | Admin Big: `GLOBAL`, hoặc `LOCAL` khi lọc một site; Admin Small: `LOCAL` | Tổng hợp số học viên/lớp và chỉ số vận hành trong phạm vi được cấp; nêu site thiếu |
| `GET /api/v1/admin/reports/tuition-by-site/?site_code=...` | Admin Big; Admin Small; Kế toán & Lễ tân tại site | Admin Big: `GLOBAL` khi bỏ `site_code`, `LOCAL` khi chọn site; Admin Small/Kế toán & Lễ tân: `LOCAL` | Đã triển khai snapshot từ `HocPhi`, `PhieuThu`: số khoản, số khoản còn nợ, phải thu, đã thu ròng, đã thu, đã hoàn và còn nợ; báo `complete`/`missing_sites`; chưa lọc theo ngày |
| `GET /api/v1/reports/audit-logs/?ma_co_so=...&ma_tai_khoan=...&loai_log=...&tu_ngay=...&den_ngay=...&limit=...&offset=...` | Admin Big; Admin Small đúng site | Admin Big: `GLOBAL`, hoặc `LOCAL` khi lọc một site; Admin Small: `LOCAL` | Đã triển khai: đọc `dbo.Logs` độc lập tại từng site, lọc tài khoản/loại/ngày Việt Nam và phân trang ở API. Trả `complete`/`missing_sites`; 503 nếu thiếu site. Không trả IP, hash, token, JSON trước/sau hoặc ghi chú tự do. |
| `GET /api/v1/admin/notifications/` | Admin Big; Admin Small | Admin Big: `GLOBAL` hoặc `LOCAL` khi lọc site; Admin Small: `LOCAL` | Đã triển khai: đọc `dbo.ThongBao`; không lưu trạng thái đã đọc. |
| `POST /api/v1/admin/notifications/` | Admin Big; Admin Small | Admin Big: `REPLICATED-WRITE` tới site hoạt động; Admin Small: `LOCAL` | Đã triển khai: tạo thông báo Admin Big/Admin Small trong `dbo.ThongBao`, ghi audit `dbo.Logs` tại mỗi site được ghi. Bắt buộc `Idempotency-Key`; trả `200` khi đủ site hoặc `202 complete=false` với `missing_sites` để retry cùng key/body. Không có transaction ACID xuyên site. |

Tạo thông báo nhận `category`, `severity`, `audience`, `title`, `message` và `target_path` nội bộ `/admin/...` (không bắt buộc). Chỉ Admin Big/Admin Small được tạo; Admin Small chỉ ghi tại site của mình và không thể nhắm riêng Admin Big. Admin Big gửi tới mọi site hoạt động. API thủ công chấp nhận `admin_all`, `admin_big`, `admin_small`; audience nội bộ `site_staff` chỉ do nghiệp vụ server phát tại site, hiện dùng để báo nhân sự site nhận khi chuyển học viên hoàn tất. Thông báo đó được ghi idempotent trong transaction kích hoạt hồ sơ đích và Admin Small/Kế toán & Lễ tân/Tư vấn & xếp lớp chỉ đọc tại site nhận. Không phát thông báo trực tiếp cho học viên/giáo viên. Các lần ghi dùng transaction và audit riêng tại từng CSDL site; nếu một site lỗi, API không báo hoàn tất toàn phần. Dùng cùng `Idempotency-Key` và cùng body để tiếp tục các site còn thiếu; dùng key cũ với nội dung khác trả `409`.

`POST /admin/sites` không có nghĩa API tự tạo CSDL tùy ý bằng credential từ browser. Khâu tạo database, cấu hình kết nối bí mật, chạy migration và nạp bản sao phải thuộc provisioning phía server/nhóm triển khai; endpoint chỉ khởi chạy quy trình đã được bảo vệ.

### Nhân viên nghiệp vụ — đã có route trong source

Nhân viên nghiệp vụ dùng `NhanVien.chuc_vu` (`ke_toan`, `tu_van`); form chỉ tạo hai chức vụ “Kế toán & Lễ tân” và “Tư vấn & xếp lớp”. Migration 41 chuyển hồ sơ `le_tan` cũ thành `ke_toan`. Kế toán & Lễ tân chỉ đọc phòng, lớp/roster, hồ sơ học viên, công nợ và đề nghị chuyển tại site được gán; được gửi nhắc phí, xem báo cáo tài chính/phiếu thu và thu/hoàn, nhưng không ghi phòng/lớp/hồ sơ, đăng ký/xếp lớp hoặc sửa kế hoạch đóng. Tư vấn & xếp lớp được CRUD hồ sơ học viên và phòng tại site được giao nhưng không cấp tài khoản; mở lớp, phân công giáo viên, đăng ký/xếp lớp; sửa tên/sĩ số và hủy mềm lớp đủ điều kiện; xem/nhắc công nợ và chỉ sửa kế hoạch đóng; tạo đề nghị và xem lịch sử chuyển tại site nguồn nhưng không quyết định/retry. Admin Big hoặc Admin Small ở đúng site nhận có thể duyệt/từ chối đề nghị; Admin Small không thể duyệt đề nghị của site nguồn hoặc retry. Khi chuyển hoàn tất, API ghi thông báo `site_staff` tại đích; tài khoản học viên giữ nguyên. Tư vấn có hộp thư liên hệ LOCAL tại site được gán và quyền tạo/sửa/xuất bản bài Blog dùng chung qua `REPLICATED-WRITE` (không xóa bài hoặc sửa danh mục). Không dùng hồ sơ `Admin.loai_admin=admin_small`. API xác định quyền từ phiên đã xác thực. Admin Big được bỏ `site_code` trên GET danh sách nhân viên để đọc GLOBAL; nếu truyền site thì chỉ đọc LOCAL site đó. GET chi tiết và mọi thao tác ghi cần site cụ thể. Admin Small có site cố định và không thể mở rộng phạm vi bằng query/body.

| Method và path | Người gọi | Kiểu phân tán | Bảng đọc/ghi và hành vi |
|---|---|---|---|
| `GET /api/v1/admin/employees/?site_code=...&job_title=...&status=...&search=...&limit=...&offset=...` | Admin Big; Admin Small đúng site | Admin Big bỏ site: `GLOBAL`; có site: `LOCAL`; Admin Small: `LOCAL` | Đọc `NhanVien`, `TaiKhoan`, `Logs` riêng tại từng site; mỗi dòng gồm email, username, phone, `site_code`, `avatar_secure_url` và `credential_email_status`. Global Query báo site thiếu thay vì coi site đó rỗng |
| `POST /api/v1/admin/employees/` | Admin Big; Admin Small đúng site | `LOCAL` + `REPLICATED-WRITE` | Tạo `NhanVien` ở site được chọn; tạo `TaiKhoan` và đồng bộ các site hoạt động theo service hiện có; body gồm `full_name`, `email`, `job_title`, tùy chọn `username`, `phone`, `site_code`, `avatar_requested`. Không gửi email khi tạo; ghi trạng thái chờ gửi vào `Logs` tại site và trả `credential_email_status`. Khi yêu cầu ảnh, response cấp `avatar_setup_token` ngắn hạn |
| `POST /api/v1/admin/employees/{account_id}/credential-email/?site_code=...` | Admin Big; Admin Small đúng site | `GLOBAL` đọc bản sao + `LOCAL` + SMTP | Xác minh các bản sao `TaiKhoan` và hồ sơ `NhanVien` tại site; chỉ Admin Big/Admin Small bấm gửi mới gọi SMTP. Ghi `employee_credential_email_*` vào `Logs` của site; chỉ `ready`/`failed` được gửi, còn `sent`/`processing`/`unknown`/`changed` khóa gửi lại |
| `GET /api/v1/admin/employees/{slug}/?site_code=...` | Admin Big; Admin Small đúng site | `LOCAL` | Đọc chi tiết `NhanVien` và bản `TaiKhoan` tại CSDL site được chọn, gồm `avatar_secure_url`; không dò hoặc JOIN qua site khác |
| `PATCH /api/v1/admin/employees/{slug}/?site_code=...` | Admin Big; Admin Small đúng site | `LOCAL` | Chỉ cập nhật `NhanVien.ho_ten`, `sdt`, `chuc_vu`; ghi `Logs` cùng transaction cục bộ |
| `PATCH /api/v1/admin/employees/{slug}/status/?site_code=...` | Admin Big; Admin Small đúng site | `REPLICATED-WRITE` | Body `{ "status": "inactive" }`; chỉ chuyển `active` → `inactive` trên các site hoạt động và thu hồi `PhienDangNhap`; không hỗ trợ kích hoạt lại, không đổi trạng thái công việc `NhanVien` |
| `DELETE /api/v1/admin/employees/{slug}/?site_code=...` | Admin Big; Admin Small đúng site | `LOCAL` + `REPLICATED-WRITE` | Xóa vật lý các bản `TaiKhoan`, phiên/token và ảnh; xóa hồ sơ `NhanVien` nếu không có phiếu thu, nếu có thì gỡ FK tài khoản và giữ hồ sơ `nghi_viec`; giữ `Logs`/`PhieuThu`, có marker retry từng site |
| `POST /api/v1/admin/employees/{slug}/avatar/upload-intents/` | Admin Big; Admin Small đúng site, token cấp lúc tạo | `GLOBAL` đọc bản sao + `LOCAL` đọc hồ sơ | Xác minh tài khoản/hồ sơ nhân viên, trạng thái ảnh và site hoạt động; ký intent ngắn hạn để client tải trực tiếp lên Cloudinary |
| `POST /api/v1/admin/employees/{slug}/avatar/complete/` | Admin Big; Admin Small đúng site, token cấp lúc tạo | `REPLICATED-WRITE` | Xác minh asset Cloudinary rồi cập nhật `TaiKhoan.avatar_public_id`/`avatar_secure_url` cùng audit tại từng site hoạt động; lỗi site trả incomplete/503, không báo hoàn tất giả |

PATCH nhận ít nhất một trong `full_name`, `phone`, `job_title`; body có trường lạ nhận `400`. `phone: null` hoặc `phone: ""` xóa số điện thoại. Chỉ hồ sơ đang làm việc có tài khoản hoạt động được sửa; email/tên đăng nhập là danh tính tài khoản nhân bản, còn `site_code` xác định mảnh nên các trường này không được sửa bằng endpoint hồ sơ. GET/PATCH/DELETE dùng query `site_code` cho Admin Big; Admin Small có thể bỏ query hoặc truyền đúng site của mình.

API GET danh sách/chi tiết nhân viên dùng scope đọc `employee_read` (120 request/phút), tách khỏi scope ghi `employee_management` (10 request/giờ) của POST/PATCH/DELETE. Gửi mật khẩu dùng scope `admin_credential_email`, có giới hạn riêng như các email cấp tài khoản khác. Việc tải danh sách sau khi tạo không tiêu hao hạn mức ghi.

Email cấp tài khoản nhân viên hiển thị email làm thông tin đăng nhập chính; người nhận không cần username được sinh tự động. Login API vẫn chấp nhận username như định danh thay thế.

`tu_van` là chức vụ duy nhất cho tư vấn và xếp lớp; migration 37 chuyển dữ liệu `xep_lop` cũ sang giá trị này. Migration 41 chuyển `le_tan` thành `ke_toan` để dùng chung chức vụ “Kế toán & Lễ tân”. Chạy tuần tự migration 37 và 41 tại từng CSDL site trước khi triển khai phiên bản mới.

Create trả `201`; GET/PATCH/DELETE và gửi email thành công trả `200`; lỗi validation/quyền/không tìm thấy/xung đột lần lượt có thể trả `400`/`403`/`404`/`409`. Ảnh không bắt buộc, chỉ nhận JPG/JPEG/PNG/WebP tối đa 5 MB; API xác minh setup token, upload intent và asset, client gửi bytes trực tiếp Cloudinary, không qua Django. Nếu upload ảnh thất bại thì tài khoản đã tạo vẫn tồn tại và giao diện phải báo ảnh chưa lưu. POST tạo không gửi email; người quản lý bấm gửi riêng. SMTP báo không nhận thì trả `502` và cho thử lại; kết quả chưa rõ trả `503` và khóa gửi lại để tránh gửi trùng. PATCH `/status/` chỉ cho phép `active` → `inactive`, thu hồi phiên và tách biệt với DELETE. DELETE xóa vật lý tài khoản, phiên/token, trạng thái đọc thông báo và ảnh; hồ sơ NhanVien chỉ giữ lại khi PhieuThu tham chiếu, đồng thời gỡ liên kết tài khoản và đánh dấu nghỉ việc. Giữ Logs/chứng từ. Nếu site chưa đồng bộ hoặc dọn ảnh được thì trả `503`, không báo thành công toàn phần, và có thể gọi lại cùng slug để tiếp tục. Các database commit độc lập nên `REPLICATED-WRITE` không đồng nghĩa ACID xuyên site; chưa có bằng chứng lỗi và phục hồi nhiều site thật.

## Endpoint cho giáo viên

| Method và path | Người gọi | Kiểu phân tán | Bảng chính và kiểm tra quyền |
|---|---|---|---|
| `GET /api/v1/teacher/classes` | Giáo viên | `LOCAL` | Chỉ trả lớp có phân công của tài khoản hiện tại |
| `GET /api/v1/teacher/dashboard` | Giáo viên | `LOCAL` | Lịch buổi sắp tới và tác vụ thuộc các lớp được phân công |
| `GET /api/v1/teacher/classes/{ma_lop}` | Giáo viên được phân công | `LOCAL` | Trả thông tin lớp và danh sách đăng ký cần cho giảng dạy; từ chối lớp khác |
| `GET /api/v1/teacher/classes/{ma_lop}/sessions` | Giáo viên được phân công | `LOCAL` | Đọc `BuoiHoc` tại site của lớp |
| `PUT /api/v1/teacher/sessions/{ma_buoi}/attendance` | Giáo viên được phân công | `LOCAL` | Tạo/cập nhật `DiemDanh` cho học viên có `DangKy` hợp lệ của lớp; một dòng cho mỗi cặp buổi/đăng ký |
| `GET /api/v1/teacher/enrollments/{ma_dang_ky}/grades` | Giáo viên được phân công | `LOCAL` | Đọc điểm của đăng ký trong lớp mình dạy |
| `GET /api/v1/teacher/enrollments/{ma_dang_ky}/grades/history` | Giáo viên được phân công; quản lý theo quyền | `LOCAL` | Đọc lịch sử chỉnh sửa điểm của đăng ký đúng lớp/site; không cho sửa lịch sử |
| `PUT /api/v1/enrollments/{ma_dang_ky}/grades/{loai_diem}` | Giáo viên được phân công; quản lý chỉ theo quyền | `LOCAL` | Ghi `Diem`; kiểm tra phân công, site, loại điểm và điểm 0–10; lưu nhật ký thay đổi |

API không nhận `ma_giao_vien` từ body để quyết định quyền. Người ghi lấy từ phiên đã xác thực; API xác nhận giáo viên thuộc cùng site và được phân công vào đúng lớp/buổi.

## Quản lý hồ sơ học viên và phạm vi portal

Admin Big, Admin Small và Tư vấn & xếp lớp CRUD hồ sơ học viên tại site được phép theo FS-STU-01; Kế toán & Lễ tân chỉ đọc. Tạo hồ sơ chỉ ghi `HocVien` tại site được xác thực; không tạo `TaiKhoan` hoặc gửi mật khẩu. Admin Big chọn `site_code`; Admin Small/Tư vấn dùng site trong phiên và không thể gửi site khác. Chỉ Admin Big/Admin Small được cấp tài khoản cho hồ sơ đang `dang_hoc` có email hợp lệ, kể cả khi chưa có `DangKy`; API thực hiện `REPLICATED-WRITE` cho `TaiKhoan`, ghi liên kết `HocVien.ma_tai_khoan` cục bộ và chỉ gửi mật khẩu tạm lúc đó. Email cấp tài khoản ghi email làm thông tin đăng nhập chính.

Portal đọc hồ sơ/đăng ký/lịch/học phí/điểm và SePay có code/schema/UI trong source nhưng vẫn chưa được duyệt phạm vi môn học. Việc cấp tài khoản không đồng nghĩa portal hoặc thanh toán trực tuyến đã được đưa vào phạm vi.

Các đường dẫn thực tế được khai báo trong `src/api/core/urls.py`:

| Route source | Hành vi | Trạng thái phạm vi |
|---|---|---|
| `GET /api/v1/admin/students/?site_code=...&status=...&search=...&account_issued=...&limit=...&offset=...` | Liệt kê học viên | Admin Big bỏ site: `GLOBAL`; có site: `LOCAL`; Admin Small/Tư vấn/Kế toán & Lễ tân đọc site phiên. API lấy site nhân viên từ phiên, từ chối `site_code` do nhân viên gửi. Tư vấn có thể ghi hồ sơ; Kế toán chỉ đọc; nhân viên không cấp tài khoản. Trả `avatar_secure_url`, cờ cấp tài khoản và `site_code` từng dòng; kết quả thiếu site có `complete=false`, `missing_sites`, `count=null` |
| `POST /api/v1/admin/students/` | Tạo hồ sơ học viên | Admin Big chọn site; Admin Small/Tư vấn & xếp lớp chỉ site phiên; `LOCAL` trên `HocVien` và `Logs`, sinh mã từ `Seq_HV`; slug tùy chọn mặc định theo họ tên, được chuẩn hóa và thêm hậu tố số nếu trùng tại site; giới tính tùy chọn chỉ nhận `Nam`, `Nữ`, `Khác`; chưa tạo tài khoản/mật khẩu |
| `GET/PATCH/DELETE /api/v1/admin/students/{slug}/` | Xem/sửa/xóa hồ sơ | `GET` cho Admin Big/Admin Small/Kế toán & Lễ tân/Tư vấn tại đúng site (`LOCAL`); `PATCH/DELETE` cho Admin Big/Admin Small/Tư vấn; Kế toán chỉ đọc. PATCH giới tính chỉ nhận `Nam`, `Nữ`, `Khác`; chỉ xóa nếu chưa có tài khoản, đăng ký hoặc lịch sử chuyển; `Logs` và dữ liệu học tập không bị xóa |
| `POST /api/v1/admin/students/{slug}/avatar/upload-intents/?site_code=...` | Admin Big chọn site; Admin Small/Tư vấn đúng site | `LOCAL` đọc `HocVien`; cấp intent ngắn hạn gắn với người gọi, hồ sơ và site; trình duyệt tải trực tiếp JPG/PNG/WebP tối đa 5 MB lên Cloudinary |
| `POST /api/v1/admin/students/{slug}/avatar/complete/?site_code=...` | Admin Big chọn site; Admin Small/Tư vấn đúng site | `LOCAL` đọc/ghi `HocVien` và `Logs`; API xác minh asset Cloudinary rồi cập nhật metadata ảnh trong transaction site-local; lỗi lưu sau upload chưa được báo thành công và có thể retry cùng token/public ID |
| `POST /api/v1/admin/students/{slug}/account/` | Admin chủ động cấp tài khoản sau khi tạo hồ sơ | Trong phạm vi riêng; hồ sơ phải `dang_hoc` và email hợp lệ, không yêu cầu có `DangKy`; `REPLICATED-WRITE` cho `TaiKhoan` và liên kết cục bộ |
| `/api/v1/students/profile/{slug}/` và các route con `/enrollments/`, `/schedule/`, `/tuition/`, `/grades/` | Đọc hồ sơ/portal theo tài khoản đã xác thực | Có code; chỉ trả dữ liệu theo hồ sơ hiện hành; phạm vi chưa được duyệt |
| `/api/v1/students/profile/{slug}/tuition/{tuition_id}/payments/sepay/` | Tạo yêu cầu thanh toán SePay | Có code/schema; tắt mặc định và chưa được duyệt phạm vi |
| `/api/v1/students/profile/{slug}/payments/{attempt_id}/` | Đọc trạng thái lượt thanh toán | Có code/schema; tắt mặc định và chưa được duyệt phạm vi |

Không có account-signup endpoint công khai. `POST /api/v1/public/enrollments/` là đăng ký khóa học, không tự tạo tài khoản. API vẫn phải xác thực quyền và giới hạn bản ghi ở server; không tin slug/site do client gửi để mở rộng quyền. Bằng chứng source và giới hạn phạm vi được ghi trong [ma trận trạng thái](../docs/Trang-Thai-Trien-Khai.md).

## Quy ước response và lỗi — đề xuất

Nhóm nên thống nhất một cấu trúc response dùng chung. Mẫu dưới đây là đề xuất, chưa phải định dạng đã triển khai:

```json
{
  "data": {},
  "meta": {
    "request_id": "...",
    "complete": true,
    "missing_sites": []
  }
}
```

`meta` có thể bỏ với response `LOCAL`; mọi response `GLOBAL` bắt buộc có `complete` và `missing_sites`. Response phân trang thêm thông tin phân trang; nếu chỉ đọc được một phần thì không được đưa ra tổng số toàn cục (có thể trả `count: null`). Global Query đọc từng site độc lập và không tạo snapshot/transaction nguyên tử xuyên các CSDL.

Với lỗi:

```json
{
  "error": {
    "code": "BUSINESS_RULE_VIOLATION",
    "message": "Yêu cầu không thể thực hiện.",
    "details": {},
    "request_id": "..."
  }
}
```

Các response `GLOBAL` cần có dấu hiệu đầy đủ/không đầy đủ. Nếu một site lỗi, ví dụ `complete: false` và `missing_sites: ["Q7"]`; giao diện phải cảnh báo người dùng. Không biến lỗi site thành danh sách rỗng không phân biệt với “không có dữ liệu”.

| HTTP status đề xuất | Dùng cho |
|---|---|
| `200` | Đọc hoặc cập nhật thành công và có kết quả |
| `201` | Tạo bản ghi nghiệp vụ thành công |
| `204` | Thao tác thành công không cần response body, ví dụ logout |
| `202` | Chấp nhận yêu cầu bất đồng bộ; giao dịch còn đang xử lý |
| `400` / `422` | Request sai định dạng hoặc không qua kiểm tra nghiệp vụ |
| `401` | Chưa xác thực hoặc thông tin xác thực không hợp lệ |
| `403` | Đã xác thực nhưng không có quyền/phạm vi phù hợp |
| `404` | Không tìm thấy tài nguyên trong phạm vi được phép |
| `409` | Xung đột trạng thái, gửi trùng hoặc dữ liệu đã thay đổi |
| `429` | Quá giới hạn đăng nhập hoặc gọi API |
| `503` | Site bắt buộc không khả dụng nên nghiệp vụ không thể hoàn tất |
| `500` | Lỗi hệ thống không dự kiến; chỉ trả thông tin an toàn kèm `request_id` |

Mã lỗi chính xác và cách biểu diễn response khi `GLOBAL` chỉ lấy được một phần phải được chốt cùng nhóm; nội dung trên là quy ước đề nghị để bắt đầu thiết kế.

## Danh mục endpoint đề xuất cho sáu nghiệp vụ

Các path dưới đây là **bản nháp để thảo luận**, chưa khẳng định đã có trong source. Cần giữ nhất quán giữa API, giao diện và kiểm thử sau khi nhóm chốt.

| Nghiệp vụ | Endpoint đề xuất | Vai trò | Kiểu phân tán | Site và bảng chính |
|---|---|---|---|---|
| Đăng ký khóa học | `POST /api/v1/enrollments` | Admin Big, Admin Small, Tư vấn & xếp lớp | `LOCAL` | Site học viên/lớp; đọc `HocVien`, `LopHoc`; ghi `DangKy`, `HocPhi`, cập nhật sĩ số `LopHoc`; Kế toán & Lễ tân chỉ xem |
| Xếp/đổi lớp | `PATCH /api/v1/enrollments/{ma_dang_ky}/class` | Admin Big, Admin Small, Tư vấn & xếp lớp | `LOCAL` | Site của đăng ký; đọc lớp và sĩ số; cập nhật `DangKy`, sĩ số hai lớp; Kế toán & Lễ tân chỉ xem |
| Liệt kê phiếu thu/hoàn | `GET /api/v1/admin/tuition/{tuition_id}/receipts/` | Kế toán & Lễ tân tại site | `LOCAL` | Đọc `HocPhi`, `PhieuThu`; trả từng phiếu gốc và số còn có thể hoàn |
| Thu học phí tại quầy | `POST /api/v1/admin/tuition/{tuition_id}/receipts/` | Kế toán & Lễ tân tại site | `LOCAL` | Ghi `PhieuThu`, cập nhật `HocPhi` và các kỳ; chống gửi lặp bằng mã phiếu site-prefixed |
| Hoàn học phí | `POST /api/v1/admin/tuition/{tuition_id}/receipts/{receipt_id}/refund/` | Kế toán & Lễ tân tại site | `LOCAL` | Ghi phiếu `hoan` tham chiếu phiếu thu gốc, cập nhật `HocPhi`/`DotHocPhi`, audit; idempotency lưu tại site |
| Tạo/tiếp tục yêu cầu thanh toán trực tuyến (nếu nhóm chọn tích hợp cổng) | `POST /api/v1/tuition-payment-attempts` | Vai trò thanh toán đã được nhóm duyệt | `LOCAL` | Lưu yêu cầu tại đúng site của `HocPhi`; chưa ghi `PhieuThu` hay tăng số đã thu khi chưa xác minh thành công |
| Tra cứu trạng thái thanh toán | `GET /api/v1/tuition-payment-attempts/{ma_yeu_cau}` | Người tạo và nhân viên có quyền tại site; Admin Big theo quyền | `LOCAL` hoặc `GLOBAL` định vị rồi `LOCAL` | Đọc trạng thái bền vững tại site chứa khoản học phí; không suy site từ tiền tố mã |
| Tiếp tục yêu cầu còn mở | `GET /api/v1/tuition/{ma_hoc_phi}/payment-attempts?active=true` | Người học đã được liên kết (chỉ khi portal được duyệt); nhân viên có quyền tại site | `LOCAL` sau khi định vị site nếu cần | Tìm yêu cầu còn mở sau khi đóng tab, đổi thiết bị hoặc mất mã yêu cầu |
| Yêu cầu hủy thanh toán đang chờ | `POST /api/v1/tuition-payment-attempts/{ma_yeu_cau}/cancel` | Người tạo và nhân viên có quyền tại site | `LOCAL` | Ghi yêu cầu hủy; chỉ chuyển `da_huy` khi cổng xác nhận chưa thu/đã hủy |
| Cổng thanh toán báo kết quả | `POST /api/v1/payment-providers/{provider}/webhook` | Cổng thanh toán qua chữ ký xác thực | `LOCAL` | Site được xác định từ tham chiếu giao dịch phía server; xử lý sự kiện lặp an toàn, chỉ ghi phiếu thu một lần |
| Quản lý điểm | `PUT /api/v1/enrollments/{ma_dang_ky}/grades/{loai_diem}` | Giáo viên được phân công; quản lý theo quyền | `LOCAL` | Site của lớp/đăng ký; đọc phân công và đăng ký; ghi `Diem`, nhật ký chỉnh sửa |
| Tạo đề nghị chuyển | `POST /api/v1/transfers` | Tư vấn & xếp lớp tại site được giao | `LOCAL` | Nguồn lấy từ phiên đăng nhập; ghi `GiaoDichChuyenCoSo`, thêm `LichSuChuyenCoSo`; chưa ghi site đích |
| Hộp thư đề nghị | `GET /api/v1/transfers/inbox` | Admin Big | `GLOBAL` | Đọc riêng các site đang hoạt động; gộp kết quả trong API; trả trạng thái đầy đủ/thiếu site |
| Duyệt đề nghị | `POST /api/v1/transfers/{ma_chuyen}/approve` | Admin Big; Admin Small đúng site đích | `LOCAL` ghi quyết định, rồi `DISTRIBUTED-TX` | Quyết định ghi tại nguồn; Coordinator tạo hồ sơ đích, giữ `ma_tai_khoan`, sao chép metadata ảnh Cloudinary của `HocVien` nếu có, và ghi thông báo site-local cho nhân sự đích; hồ sơ/metadata nguồn vẫn được giữ làm lịch sử |
| Từ chối đề nghị | `POST /api/v1/transfers/{ma_chuyen}/reject` | Admin Big; Admin Small đúng site đích | `LOCAL` | Ghi `tu_choi`, người quyết định, thời điểm, lý do và sự kiện tại nguồn; hồ sơ học viên không đổi |
| Xem trạng thái chuyển | `GET /api/v1/transfers/{ma_chuyen}` | Admin Big; Admin Small trong phạm vi được phép | Admin Big: `GLOBAL` để định vị nguồn; Admin Small: `LOCAL` tại site được gán | Đọc trạng thái tại nguồn; không suy ra site từ tiền tố mã học viên |
| Thống kê học viên theo cơ sở | `GET /api/v1/reports/students-by-site` | Admin Big toàn hệ thống; Admin Small site mình | `LOCAL` hoặc `GLOBAL` tùy phạm vi | Đọc `HocVien` và trạng thái chuyển liên quan; gộp tại API khi nhiều site |
| Tổng quan vận hành cơ sở | `GET /api/v1/reports/site-summary` | Admin Big; Admin Small đúng site | Admin Big: `GLOBAL`; Admin Small: `LOCAL` | Tổng hợp số học viên/lớp và chỉ số vận hành; gộp ở API, báo site thiếu |
| Báo cáo tài chính học phí | `GET /api/v1/admin/reports/tuition-by-site/` | Admin Big; Admin Small; Kế toán & Lễ tân tại site | Admin Big: `GLOBAL` hoặc chọn site; Admin Small/Kế toán & Lễ tân: `LOCAL` | Đọc `HocPhi`, `PhieuThu`; tổng hợp phải thu/đã thu/đã hoàn/còn nợ; nếu thiếu site thì trả `complete=false` và `missing_sites` |

## Request và quy tắc kiểm tra chính

Các trường dưới đây là phần nghiệp vụ tối thiểu để đặc tả. Kiểu SQL chính xác, khóa ngoại và giá trị enum phải đối chiếu schema trước khi triển khai.

### Đăng nhập và nạp quyền

`POST /api/v1/auth/login` nhận:

```json
{
  "identifier": "nhanvien.q1",
  "password": "<không ghi vào log>"
}
```

Web form yêu cầu email làm định danh đăng nhập. API vẫn nhận `identifier` là email hoặc tên đăng nhập để tương thích; API tra cứu bản `TaiKhoan` nhân bản, so sánh với hash mật khẩu, kiểm tra `trang_thai`, rồi dựng quyền từ tài khoản và hồ sơ tương ứng. Không nhận `vai_tro`, `ma_co_so` hoặc danh sách lớp từ body. Đăng nhập sai, tài khoản bị khóa và tài khoản không tồn tại dùng thông báo chung; ghi kết quả vào nhật ký nhưng không ghi tên đăng nhập nhạy cảm, mật khẩu hay token. Thành công trả `user`, `idle_timeout_seconds` và `expires_at` UTC; `/auth/session/` trả `user` cùng hạn hiện tại mà không đổi hạn.

Khuyến nghị phiên trình duyệt dùng cookie `HttpOnly`, `Secure`, `SameSite` và cơ chế CSRF phù hợp; không lưu access token/mật khẩu trong `localStorage`. Nếu nhóm chọn cơ chế bearer token khác, phải đặc tả thời hạn, thu hồi, refresh và nơi lưu trước khi code.

`GET /api/v1/auth/profile/{slug}/` trả user context và hạn phiên khi slug khớp với danh tính trong phiên. Source dùng `role`, `site_code`, `profile_id`, `must_change_password` và `avatar_secure_url`; không trả `permissions` hoặc `default_route` trong response này:

```json
{
  "user": {
    "account_id": "Q1-TK-000001",
    "slug": "quan-ly-q1",
    "email": "quanly@example.test",
    "username": "quanly.q1",
    "role": "admin_small",
    "site_code": "Q1",
    "profile_id": "Q1-ADM-000001",
    "must_change_password": false,
    "avatar_secure_url": null
  },
  "expires_at": "2026-11-15T10:00:00Z"
}
```

Ví dụ trên phản ánh các trường serializer hiện có; giá trị ID và thời điểm chỉ là mẫu. Admin Small có `role = admin_small` trong user context dù `TaiKhoan.vai_tro = nhan_vien`; Admin Big và các vai trò nghiệp vụ được serialize tương tự. API kiểm tra quyền ở mỗi request; không trả `permissions`, `scope` hay `default_route` trong payload profile này.

### Tạo tài khoản Admin Small hoặc giáo viên

Các thao tác này do Admin Big thực hiện. Ví dụ request tạo Admin Small:

```json
{
  "ho_ten": "Nguyễn Minh An",
  "ten_dang_nhap": "minhan.q7",
  "email": "minhan@example.test",
  "sdt": "0900000000",
  "ma_co_so": "Q7"
}
```

API tự đặt `TaiKhoan.vai_tro = nhan_vien`, gắn site và tạo hồ sơ `Admin.loai_admin = admin_small` tại Q7; không tạo hồ sơ `NhanVien` cho Admin Small. Không cho client gửi `vai_tro` hoặc `loai_admin`. Với giáo viên, API đặt `vai_tro = giao_vien`, tạo `TaiKhoan` dùng chung và hồ sơ `GiaoVien` tại site được chọn.

Source có endpoint tạo Admin Small, giáo viên và nhân viên; API khởi tạo mật khẩu theo cấu hình, lưu hash, bắt buộc đổi mật khẩu ở lần đăng nhập đầu. Tạo tài khoản không tự gửi email; Admin gửi qua endpoint credential-email riêng khi chủ động chọn thao tác đó. Các endpoint gửi thông tin đăng nhập không nhận trường dữ liệu trong body; serializer rỗng được khai báo tường minh để OpenAPI mô tả đúng request mà không phải đoán serializer của APIView. Chưa có token kích hoạt tài khoản kiểu invitation. Gửi email thật vẫn phụ thuộc SMTP và cần xác minh tại môi trường chạy.

Đây là nhiều bước ghi (`REPLICATED-WRITE` cho `TaiKhoan`, `LOCAL` cho hồ sơ). Response cần có trạng thái xử lý theo từng chặng; chỉ trả thành công hoàn toàn khi tài khoản có hồ sơ/phạm vi dùng được. Nếu đồng bộ tài khoản thành công nhưng tạo hồ sơ site thất bại, vô hiệu hóa hoặc đưa tài khoản về trạng thái chờ xử lý có thể phục hồi; không để tài khoản hoạt động không có site/phạm vi. Kiểm tra trùng `ten_dang_nhap`/`email` trên các bản sao trước khi ghi.

### Phân công giáo viên

Source chưa có route tổng hợp `PUT .../assignments` cho giáo viên. Việc gán giáo viên vào lớp đi qua `PUT /api/v1/admin/classes/{class_id}/teacher/` trong site của lớp; API kiểm tra quyền và hồ sơ giáo viên cùng site. Danh sách lớp/buổi được giao được truy xuất qua API giáo viên; không mô tả một hợp đồng phân công nhiều lớp trong một request khi route đó chưa tồn tại.

### Điểm danh buổi học

`PUT /api/v1/teacher/sessions/{ma_buoi}/attendance` nhận một lần lưu cho danh sách học viên của cùng buổi:

```json
{
  "items": [
    { "ma_dang_ky": "Q1-DK-000001", "trang_thai": "co_mat", "ghi_chu": null },
    { "ma_dang_ky": "Q1-DK-000002", "trang_thai": "vang_co_phep", "ghi_chu": "Đã báo nghỉ" }
  ]
}
```

API lấy tài khoản giáo viên từ phiên, kiểm tra giáo viên được phân công vào buổi đó và từng đăng ký thuộc đúng lớp/site. Dùng ràng buộc duy nhất (`ma_buoi`, `ma_dang_ky`) để tạo mới hoặc cập nhật; lưu `ma_tai_khoan_ghi` và nhật ký thay đổi. Transaction `LOCAL` phải thành công toàn bộ hoặc rollback toàn bộ danh sách.

### Học viên tự xem dữ liệu — chỉ khi portal được duyệt

Các route `GET /api/v1/student/me/...` không nhận `ma_hoc_vien` từ client. API dùng phiên học viên và quan hệ liên kết đã được duyệt để tìm hồ sơ hiện hành bằng Global Query; sau khi xác định đúng site mới đọc `DangKy`, `LopHoc`, `BuoiHoc`, `HocPhi`, `PhieuThu` hoặc `Diem` qua kết nối site đó. Trong lúc chuyển cơ sở, nếu có hai dòng vật lý `dang_hoc`, Coordinator phải chọn hồ sơ chuẩn theo trạng thái `GiaoDichChuyenCoSo` như README mục 5.5; không đếm/trả cả hai. Nếu không thể xác định bản chuẩn an toàn, không trả dữ liệu và ghi lỗi để phục hồi/đối soát.

Đây vẫn là phương án, không phải contract được bật. Trước khi viết API phải cập nhật schema về liên kết tài khoản–học viên và quy tắc mang liên kết qua chuyển cơ sở. Mặc định chỉ đọc dữ liệu của chính người dùng; các thao tác đăng ký, thanh toán và sửa hồ sơ cần hợp đồng riêng, permission riêng, kiểm thử riêng.

### Đăng ký khóa học

```json
{
  "ma_hoc_vien": "Q1-HV-000001",
  "ma_lop": "Q1-LH-000001"
}
```

API phải xác nhận học viên và lớp thuộc cùng site, lớp đang nhận đăng ký và còn chỗ, học viên chưa có đăng ký trùng còn hiệu lực. Tạo `DangKy`, `HocPhi`, cập nhật sĩ số và ghi nhật ký trong một transaction cục bộ; lỗi ở một bước thì rollback cả transaction.

Kiểm tra chỗ trống và cập nhật sĩ số phải được bảo vệ khỏi cạnh tranh trong chính transaction đó. Người triển khai phải ghi cơ chế SQL Server thực tế đã chọn (khóa/mức cô lập hoặc cập nhật có điều kiện), không chỉ đọc sĩ số rồi ghi lại ngoài vùng bảo vệ. Unique `(ma_hoc_vien, ma_lop)` không ngăn hai học viên khác nhau lấy chỗ cuối. Theo hợp đồng đề xuất, yêu cầu thua cạnh tranh trả `409` với mã lỗi nghiệp vụ đã chốt; frontend đọc lại lớp, không tự gửi lại đăng ký. Không để lại `DangKy`/`HocPhi` hoặc tăng sĩ số của yêu cầu thất bại.

### Xếp hoặc đổi lớp

Request tối thiểu gồm `ma_lop_moi`. API lấy site từ đăng ký hiện tại; không nhận site để chuyển đăng ký sang cơ sở khác. Kiểm tra lớp đích cùng site, còn chỗ và phù hợp lịch; cập nhật đăng ký/sĩ số lớp cũ và mới trong một transaction cục bộ.

## Thanh toán học phí

Thu/hoàn tại quầy là thao tác `LOCAL` tại site giữ `HocPhi`. Thu tiền hiện dùng mã phiếu site-prefixed để đọc lại yêu cầu lặp; hoàn tiền lưu UUID idempotency và liên kết phiếu gốc tại cùng CSDL site. Source có tích hợp SePay nhưng portal học viên/thanh toán online chưa được duyệt vào phạm vi và `SEPAY_ENABLED=false` mặc định. Không dùng trạng thái frontend thay cho trạng thái SQL Server.

### Thu hoặc hoàn học phí tại quầy

```json
{
  "ma_hoc_phi": "Q1-HP-000001",
  "loai": "thu",
  "so_tien": 1500000,
  "hinh_thuc": "chuyen_khoan",
  "ghi_chu": "..."
}
```

Endpoint này dùng cho nhân viên ghi nhận khoản tiền đã thu/xác minh tại quầy; `hinh_thuc = chuyen_khoan` không tự chứng minh rằng ngân hàng đã chuyển tiền. Nếu có thanh toán trực tuyến qua nhà cung cấp, phải dùng luồng yêu cầu thanh toán ở phần tiếp theo, không gọi endpoint này từ trang quay về của cổng để tự khai báo thành công.

Request thu tại quầy có `idempotency_key` trong body; request hoàn có UUID `idempotency_key` cùng số tiền, phương thức và lý do. API tự lấy site từ phiên và khoản học phí, xác thực quyền và kiểm tra số tiền dương, số dư, trạng thái khoản phí. Trong một transaction `LOCAL`, API khóa/đọc lại `HocPhi`, tạo `PhieuThu`, cập nhật `HocPhi`/`DotHocPhi` và ghi nhật ký. Khi hoàn, cùng người gọi + cùng site + cùng key và nội dung trả lại cùng phiếu; cùng key nhưng nội dung khác trả `409`. Nếu transaction rollback thì có thể gửi lại cùng key. Không xóa phiếu đã phát sinh; hoàn tiền tạo dòng `PhieuThu` loại `hoan` với mã `ma_phieu_goc` và khóa idempotency riêng.

Với hoàn tiền, `receipt_id` trong URL là phiếu gốc; API kiểm tra số đã hoàn trước đó và không cho tổng hoàn vượt số tiền thu còn có thể hoàn hoặc tổng đã thu ròng. Phiếu gốc được giữ nguyên. Hợp đồng hiện tại cho phép Kế toán & Lễ tân ghi nhận trực tiếp; **chưa có** quy trình đề nghị/duyệt hoàn tiền riêng. Admin Small giám sát theo quyền, không ghi phiếu hoàn bằng API này.

`GET /api/v1/admin/tuition/{tuition_id}/receipts/?site_code=Q1` liệt kê phiếu của một khoản tại site; mỗi phiếu thu có `refunded_amount` và `refundable_amount`. `POST /api/v1/admin/tuition/{tuition_id}/receipts/{receipt_id}/refund/?site_code=Q1` nhận:

```json
{
  "idempotency_key": "<UUID>",
  "amount": 500000,
  "payment_method": "chuyen_khoan",
  "reason": "Điều chỉnh khoản thu theo yêu cầu"
}
```

`GET /api/v1/admin/tuition/?status=con_no&search=...&limit=20&offset=0` trả danh sách khoản có số dư dương, kèm học viên, lớp, tổng học phí, đã thu và còn lại; `search` tìm theo tên/mã học viên hoặc tên/mã lớp. Danh sách phân trang từ API để không bỏ sót khoản ở site có nhiều hồ sơ.

`GET /api/v1/admin/reports/tuition-by-site/` trả số khoản học phí, số khoản còn nợ, tổng phải thu, đã thu, đã hoàn, thu ròng và còn nợ theo site. Kế toán & Lễ tân chỉ nhận báo cáo `LOCAL` của site trong phiên; Admin Small cũng chỉ đọc site được giao; Admin Big có thể đọc `GLOBAL` hoặc chọn một site. `GLOBAL` truy vấn riêng từng DB và đánh dấu site thiếu.

### SePay — code có trong source, phạm vi và vận hành chưa được duyệt

SePay là provider được triển khai trong source. `POST /api/v1/students/profile/{slug}/tuition/{tuition_id}/payments/sepay/`, `GET /api/v1/students/profile/{slug}/payments/{attempt_id}/` và `POST /api/v1/webhooks/sepay/` là các route hiện có. Tích hợp mặc định tắt, phụ thuộc merchant/webhook secret và chưa có bằng chứng chạy giao dịch thật. Cổng thanh toán là dịch vụ ngoài, không phải một site SQL Server; nghiệp vụ khoản phí là `LOCAL` tại database chứa `HocPhi`, không phải giao dịch xuyên DB. Các quy tắc bên dưới là tiêu chí an toàn/thiết kế, không phải bằng chứng mọi trường hợp lỗi đã được triển khai.

#### Hợp đồng thiết kế và thứ tự xử lý

Các đường dẫn tổng quát dưới đây là mẫu thiết kế, không phải route source hiện tại. Khi cập nhật hợp đồng, dùng chính xác route SePay ở trên và đối chiếu `src/api/core/urls.py`.

1. Trước lần gửi đầu, frontend tạo một UUID cho `Idempotency-Key` và giữ nguyên key cho đúng lần thao tác đó. `POST /api/v1/tuition-payment-attempts` nhận key cùng tối thiểu `ma_hoc_phi`, `so_tien` (nếu cho phép trả một phần) và `provider` nếu đã cấu hình. API lấy site từ `HocPhi`, tự kiểm tra dư nợ phía server, xác thực quyền, rồi ghi yêu cầu thanh toán bền vững ở site đó **trước khi** trả URL/đưa người dùng sang cổng. Không tin số tiền hay trạng thái do client gửi; nếu cho phép trả một phần, kiểm tra số tiền dương và không vượt dư nợ. Response lần đầu có `202 Accepted`, `ma_yeu_cau`, `trang_thai: cho_thanh_toan`, `han_thanh_toan` và URL cổng nếu đã tạo được phiên. Gửi lại đúng key/nội dung trả cùng yêu cầu và URL hiện có; key cũ với nội dung khác trả `409`.
2. Nếu ứng dụng reload/chết sau khi server đã lưu yêu cầu nhưng trước khi nhận `ma_yeu_cau`, frontend gọi `GET /api/v1/tuition/{ma_hoc_phi}/payment-attempts?active=true` để tìm yêu cầu đang mở theo phiên/quyền người dùng. Nếu response của POST chỉ bị mất và client còn key, có thể lặp lại đúng POST với cùng key. Khi server tìm thấy yêu cầu khác đang mở cho khoản phí đó, trả `409 PAYMENT_IN_PROGRESS` kèm mã/trạng thái yêu cầu hiện có; không gọi cổng lần nữa.
3. `GET /api/v1/tuition-payment-attempts/{ma_yeu_cau}` trả trạng thái hiện tại từ CSDL, có thể kèm `retry_after_ms`. API chỉ cho người tạo hoặc vai trò được cấp quyền xem đúng site. Sau reload hoặc đăng nhập lại, frontend nạp yêu cầu đang mở rồi gọi GET này; không tự tạo yêu cầu mới và không tự kết luận thành công/thất bại từ URL quay về.
4. Khi người dùng quay lại từ cổng, trang kết quả chỉ gọi GET trạng thái. Tham số URL do trình duyệt gửi về là dữ liệu không đáng tin; không tạo `PhieuThu` chỉ dựa trên trang redirect, query string hay thông báo từ frontend. URL quay về phải được cấu hình/allowlist phía server; không nhận URL tùy ý từ request để tránh open redirect.
5. `POST /api/v1/payment-providers/{provider}/webhook` nhận thông báo server-to-server. API kiểm tra chữ ký/HMAC theo tài liệu cổng, thời gian/chống replay, mã merchant, mã yêu cầu, số tiền, đơn vị tiền tệ và mã giao dịch; không ghi secret/chữ ký/token hoặc payload nhạy cảm vào log. Chỉ sau khi xác minh thành công, trong một transaction `LOCAL` API khóa yêu cầu và `HocPhi`, kiểm tra lại số dư, ghi duy nhất sự kiện cổng, tạo đúng một `PhieuThu`, cập nhật `HocPhi`, chuyển yêu cầu sang `da_thanh_toan` và ghi audit. Callback hợp lệ đã xử lý trước đó phải trả phản hồi chấp nhận mà không tạo thêm phiếu.
6. Tác vụ đối soát phía server truy vấn trạng thái cổng cho yêu cầu quá hạn hoặc callback bị thiếu. Nếu cổng chưa xác nhận kết quả, giữ `dang_xu_ly`/`can_doi_soat`, không báo thất bại và không cho tạo lượt thu mới có thể gây thu hai lần. Chỉ mở lượt mới khi cổng xác nhận lượt cũ thất bại, hủy hoặc hết hạn mà không thu tiền.

Ví dụ response khi đã tạo phiên thanh toán:

```json
{
  "data": {
    "ma_yeu_cau": "Q1-TT-000041",
    "trang_thai": "cho_thanh_toan",
    "so_tien": 1500000,
    "don_vi_tien": "VND",
    "han_thanh_toan": "2026-10-17T13:00:00+07:00",
    "checkout_url": "https://payment-provider.example/checkout/..."
  }
}
```

Nếu đã có yêu cầu còn mở cho khoản phí, API trả `409 PAYMENT_IN_PROGRESS` cùng `ma_yeu_cau` và `trang_thai` hiện tại để giao diện tiếp tục yêu cầu đó. Đây là xung đột nghiệp vụ có thể phục hồi bằng cách gọi GET, không hiện thông báo “đã thanh toán” hoặc tạo request mới.

## Bài toán lỗi, phục hồi và bảo mật thanh toán

Thanh toán kết hợp hai hệ thống độc lập: cổng có thể đã nhận tiền trong khi API hoặc SQL Server chưa nhận được kết quả. Vì vậy, timeout hay người dùng đóng trang **không chứng minh thanh toán thất bại**. API phải ưu tiên xác minh trạng thái thật của cổng, giữ yêu cầu bền vững ở CSDL site và tránh tạo lần thu thứ hai. Đây là xử lý phục hồi giữa hệ thống, không phải transaction ACID xuyên SQL Server và cổng.

### Tình huống lỗi và cách xử lý

| Tình huống | Trạng thái/hành vi bắt buộc của API | Hành vi giao diện |
|---|---|---|
| Chưa gửi form hoặc chưa tạo được yêu cầu ở server | Chưa có giao dịch; chưa tạo `PhieuThu`, chưa đổi `HocPhi` | Có thể gửi lại; tạo/gửi lại cùng idempotency key nếu không biết request trước đã tới server chưa |
| API đã lưu yêu cầu nhưng response mất hoặc người dùng reload | Giữ yêu cầu hiện tại; cùng idempotency key lấy lại cùng `ma_yeu_cau`; nếu client mất key thì tìm yêu cầu đang mở theo `ma_hoc_phi` trong phạm vi được cấp | Gọi lại POST cùng key nếu còn key; nếu không, gọi danh sách yêu cầu đang mở rồi GET trạng thái; không tạo key mới |
| Đang chờ người dùng thanh toán ở cổng | `cho_thanh_toan`; chưa ghi `PhieuThu`, dư nợ chưa giảm | Hiển thị đang chờ; reload/đăng nhập lại thì tra cứu lại trạng thái |
| Người dùng đóng tab, mất mạng hoặc rời trang | Không tự suy ra thất bại và không tự hủy; yêu cầu vẫn được lưu | Lần sau tra cứu bằng `ma_yeu_cau`; thông báo “đang xác nhận” nếu chưa có kết quả cuối |
| Người dùng bấm Hủy | Chuyển `dang_yeu_cau_huy`; chỉ thành `da_huy` khi cổng xác nhận | Không mở lượt mới trong lúc đang xác nhận hủy |
| Cổng báo đã thu tiền, callback đến trễ hoặc response API mất | Xác minh/đối soát; khi xác nhận thì cập nhật `da_thanh_toan` và ghi phiếu đúng một lần | GET lại trạng thái cho đến khi thấy kết quả cuối; không bấm thanh toán lần hai |
| API timeout và chưa rõ cổng đã trừ tiền chưa | `can_doi_soat`; hỏi trạng thái cổng bằng server, khóa tạo lượt mới cho khoản đó | Hiển thị “đang xác nhận giao dịch”; không báo thất bại giả và không yêu cầu trả lại |
| Cổng xác nhận thất bại/hủy/hết hạn mà không thu tiền | Chuyển trạng thái cuối tương ứng; giữ audit, không tạo `PhieuThu` | Cho phép tạo yêu cầu mới với idempotency key mới |
| Cổng gửi cùng callback nhiều lần | Khóa duy nhất mã sự kiện cổng và chuyển trạng thái idempotent | Không hiển thị nhiều giao dịch/phiếu thu |

### Máy trạng thái và quy tắc không thu trùng

Schema hiện tại cho `YeuCauThanhToan.trang_thai` các giá trị `cho_thanh_toan`, `da_thanh_toan`, `het_han`, `can_doi_soat`, `da_huy`. Không dùng các trạng thái thiết kế như `dang_xu_ly` hoặc `dang_yeu_cau_huy` như enum đã có. Chỉ `da_thanh_toan` mới được tính vào `HocPhi.so_tien_da_dong`; chuyển trạng thái phải do API/provider đã xác minh, không để client PATCH trực tiếp.

- Mỗi lần tạo yêu cầu dùng idempotency key ở API và cùng mã yêu cầu làm khóa idempotency khi gọi cổng (nếu cổng hỗ trợ). Nếu request tạo phiên tới cổng timeout, tra cứu bằng mã tham chiếu đó trước khi thử lại; không tạo phiên mới mù quáng.
- Webhook chỉ được trả thành công cho cổng sau khi sự kiện đã được xác minh và transaction cập nhật site đã commit, hoặc khi xác định đó là sự kiện đã xử lý trước. Nếu site DB tạm lỗi, trả lỗi có thể retry và để tác vụ đối soát xử lý; không ACK callback rồi làm mất sự kiện.
- Nếu cổng xác nhận đã thu nhưng ghi `PhieuThu`/cập nhật `HocPhi` thất bại, không trả trạng thái thất bại cho người dùng và không phát sinh lần thu mới. Giữ `can_doi_soat`, retry an toàn theo mã yêu cầu, rồi ghi đúng một phiếu thu.
- `so_tien_da_dong` phải được tính nhất quán từ giao dịch đã xác nhận: tổng `PhieuThu` loại `thu` trừ tổng loại `hoan`. Chỉ cập nhật trạng thái học phí từ kết quả đã commit; không tính khoản đang chờ hoặc chưa xác minh.
- Nếu hoàn tiền, hủy đăng ký, có chargeback hoặc điều chỉnh học phí, giữ nguyên giao dịch gốc và tạo nghiệp vụ đảo/điều chỉnh có mã tương quan, lý do, người thực hiện và idempotency riêng. Không sửa số tiền của phiếu cũ để che lịch sử.

### Yêu cầu bảo mật

- Dùng trang checkout do nhà cung cấp lưu trữ hoặc cơ chế token hóa chính thức. Không để số thẻ đầy đủ, CVV, PIN hay dữ liệu xác thực ngân hàng đi qua Django, lưu trong SQL Server, trình duyệt, analytics hoặc log. API chỉ lưu mã giao dịch tham chiếu và metadata tối thiểu.
- Số tiền, khoản học phí, đơn vị tiền (`VND` theo cấu hình hiện tại), site và trạng thái được API lấy/kiểm tra từ dữ liệu tin cậy. Không cho frontend quyết định đã thu, sửa số tiền phải trả hoặc chọn CSDL/site bằng body.
- Bắt buộc HTTPS/TLS. Quyền tạo/tra cứu/hủy yêu cầu được kiểm tra theo phiên và site; không dùng mã yêu cầu khó đoán thay cho authorization. Rate limit tạo yêu cầu và tra cứu trạng thái để chống spam.
- Webhook không dựa vào cookie đăng nhập. Xác minh chữ ký theo tài liệu provider trên đúng raw body, kiểm tra timestamp/chống replay, merchant, mã đơn, tiền tệ, số tiền và trạng thái giao dịch; so sánh chữ ký an toàn. Secret chỉ nằm trong secret store/environment máy chủ, không trong source, SQL, frontend hoặc log.
- `return_url` phải allowlist phía server; không nhận redirect tùy ý từ client. Trang quay về không được gửi lệnh xác nhận tiền, chỉ được đọc trạng thái API.
- Nhật ký chỉ lưu mã yêu cầu, mã sự kiện, kết quả kiểm tra, người thao tác và thời điểm `Asia/Ho_Chi_Minh`; không lưu thông tin thẻ, chữ ký, secret, token, cookie hoặc payload nhạy cảm.
- Giới hạn quyền hoàn tiền riêng với quyền thu tiền; bắt buộc lý do và audit. Nếu nhóm yêu cầu duyệt hoàn tiền, người đề nghị và người duyệt phải được phân tách theo vai trò đã thống nhất.

### Schema và giới hạn triển khai hiện tại

`db/01_create_schema.sql` đã có `YeuCauThanhToan` và `SuKienThanhToan`, đặt cục bộ tại từng database site; `PhieuThu` có liên kết tới yêu cầu. `YeuCauThanhToan` giữ khoản học phí, kỳ, tài khoản, số tiền, mã tham chiếu, khóa idempotency, trạng thái và thời hạn; `SuKienThanhToan` lưu ID giao dịch SePay duy nhất cùng metadata đã lọc và kết quả nhận. Không có database thanh toán trung tâm. Đối chiếu đủ cột/ràng buộc trong [`DATABASE_SCHEMA.md`](../docs/DATABASE_SCHEMA.md).

Thu tại quầy dùng mã phiếu để nhận diện yêu cầu lặp; hoàn tiền dùng `khoa_idempotency` bền vững trong `PhieuThu`. Refund API cần migration `40_enable_tuition_refunds.sql` trên từng site trước khi triển khai. SePay có code/schema nhưng mặc định tắt và chưa được kiểm chứng merchant/webhook thật. Chốt phạm vi với nhóm trước khi bật portal/payment; nếu thay đổi schema hoặc hợp đồng API, cập nhật schema/script trong cùng thay đổi.

## Quản lý điểm

Request tối thiểu gồm `diem_so` trong khoảng 0–10. API xác định site từ đăng ký/lớp, kiểm tra giáo viên được phân công và loại điểm hợp lệ. Mỗi đăng ký chỉ có một dòng cho mỗi `loai_diem`; endpoint phải quy định rõ tạo mới khi chưa có điểm hay cập nhật điểm đã có, và mọi lần sửa phải ghi nhận lịch sử theo quy tắc audit của dự án.

## Chuyển cơ sở

Tạo đề nghị nhận tối thiểu `ma_hoc_vien`, `ma_co_so_dich`, `ly_do_de_nghi`. Không nhận `ma_co_so_nguon` như một giá trị đáng tin từ client; API lấy nguồn từ phiên Tư vấn & xếp lớp đã xác thực. Admin Small không tạo đề nghị. Kiểm tra học viên hiện hành, nợ học phí, đích đang hoạt động, đích khác nguồn và không có giao dịch mở. Lưu trạng thái `cho_duyet` cùng sự kiện `de_nghi` tại nguồn; khi tạo đề nghị chưa được ghi hồ sơ đích.

Hộp thư Admin Big là `GLOBAL`: hỏi các site độc lập và gộp tại API. Admin Small xem đề nghị phát sinh tại site mình hoặc có site đích là site mình bằng truy vấn các nguồn đã lọc; Tư vấn tạo/đọc tại site trong phiên (`LOCAL`); Kế toán & Lễ tân chỉ đọc tại site được giao. Mỗi dòng kèm tổng phải thu/đã thu/còn nợ tính từ `DangKy`/`HocPhi` ở CSDL nguồn, không JOIN sang site đích. Admin Big hoặc Admin Small đúng site đích được duyệt/từ chối; chỉ Admin Big được retry. Quyết định định tuyến về CSDL nguồn và ghi trạng thái/sự kiện tại nguồn. Khi từ chối, cần `ly_do_tu_choi`; khi duyệt, kiểm tra lại điều kiện rồi mới giao Coordinator chạy `DISTRIBUTED-TX`. Tại site đích, giữ slug nguồn nếu chưa được dùng; nếu trùng thì thêm hậu tố số trong transaction đích và retry giữ nguyên slug đã tạo. `ma_tai_khoan` được giữ nguyên; sau khi hoàn tất, thông báo `site_staff` được ghi tại đích để nhân sự biết và tư vấn chọn lớp/phòng thủ công. Giao dịch phải hỗ trợ trạng thái và phục hồi theo [README mục 5.5](../README.md#55-chuyển-học-viên-sang-cơ-sở-khác); không tuyên bố ACID nguyên tử xuyên hai CSDL.

## Thống kê học viên theo cơ sở

Site cụ thể chỉ được nhận từ request sau khi API kiểm tra phạm vi của người gọi. Admin Small không được yêu cầu site khác; Admin Big có thể truy vấn toàn hệ thống. Với `GLOBAL`, gộp kết quả ở API, loại bản `da_chuyen_di`, không đếm trùng trạng thái chuyển tạm thời và nêu rõ site không phản hồi.

## Gửi lặp, cập nhật đồng thời và lỗi site

- Mọi thao tác tạo/sửa kiểm tra quyền, phạm vi site và điều kiện nghiệp vụ trước khi ghi. DELETE hồ sơ học viên chỉ được xóa bản chưa có tài khoản, đăng ký hoặc lịch sử chuyển; không xóa học phí, phiếu thu, điểm, điểm danh, lịch sử hoặc nhật ký đã phát sinh.
- Ràng buộc duy nhất hiện có giúp chặn một số thao tác trùng: `DangKy(ma_hoc_vien, ma_lop)`, `Diem(ma_dang_ky, loai_diem)`, `DiemDanh(ma_buoi, ma_dang_ky)`, và `GiaoDichChuyenCoSo.khoa_chong_lap`. Khi nhận lại cùng thao tác hợp lệ, API nên trả kết quả cũ thay vì tạo thêm nghiệp vụ.
- Thu tại quầy dùng mã phiếu site-prefixed; hoàn tại quầy lưu UUID idempotency trong `PhieuThu` cùng transaction với `HocPhi`/`DotHocPhi`. Xác nhận migration 40 đã áp dụng lên từng site trước khi triển khai.
- SePay hiện có `YeuCauThanhToan`/`SuKienThanhToan` tại database site và API callback; tích hợp mặc định tắt, chưa có bằng chứng giao dịch thật. Khi được nhóm duyệt, cần kiểm chứng callback lặp, timeout, retry và đối soát; không dựa vào trạng thái frontend/localStorage để xác định đã thu tiền.
- Tạo tài khoản nội bộ vừa ghi bản sao `TaiKhoan` vừa tạo hồ sơ site. API phải lưu đủ tiến trình để tiếp tục hoặc vô hiệu hóa an toàn nếu một chặng lỗi; không tuyên bố transaction ACID xuyên site.
- Giao dịch chuyển dùng `GiaoDichChuyenCoSo.khoa_chong_lap` và trạng thái Coordinator trong CSDL nguồn. Nếu site đích đã commit hồ sơ, phục hồi phải tiến về phía trước theo README mục 5.5.
- `GLOBAL` không trả thành công toàn phần khi site bị lỗi: giữ kết quả từng site, đặt `complete: false`, liệt kê `missing_sites`; các thao tác yêu cầu đủ site như `REPLICATED-WRITE` phải báo thất bại/chờ đối soát theo chính sách, không giả thành công.
- Ghi `Logs` append-only cùng transaction cục bộ cho các thao tác có audit. Log chỉ chứa định danh và dữ liệu nghiệp vụ tối thiểu; không ghi mật khẩu, hash mật khẩu, token, cookie, header xác thực hay thông tin kết nối.

Replication runtime hiện có cho `MonHoc`, `KhoaHoc` và CMS `DanhMucBlog`/`BaiVietBlog`: mỗi writer ghi dữ liệu và ACK append-only vào `Logs` trong transaction cục bộ tại site. ACK có mã thao tác theo `Idempotency-Key` và site; retry cùng key/body tiếp tục site chưa ACK, còn key/body khác hoặc bản sao lệch trả xung đột để đối soát. Các writer là luồng theo miền nghiệp vụ, không dùng `Logs` như outbox tổng quát. `CoSo` chưa có fan-out runtime đầy đủ; một số luồng tài khoản vẫn có cơ chế riêng, chưa được gom thành một service chung. Đây là mô tả code hiện có, không thay thế kịch bản chạy kiểm chứng đồng bộ trên các site.

## Kiểm thử hợp đồng API cần có

| Nhóm | Kịch bản phải kiểm tra |
|---|---|
| Concurrency bắt buộc YC-05 | TC-CON-01: hai phiên độc lập, hai học viên khác nhau cùng đăng ký lớp còn một chỗ; ghi cách tạo cạnh tranh và dữ liệu cuối, đúng một yêu cầu thành công. Không thay bằng test thanh toán online còn ngoài phạm vi |
| Replication YC-03 và đồng bộ YC-07 | TC-REP-01 truyền thay đổi danh mục; TC-SYNC-01 gây lỗi trước ghi và giữa ghi, kết nối lại rồi đối soát/retry không trùng; đọc từng bản sao |
| Distributed transaction YC-04 | TC-DTX-01 phải có thay đổi thật ở DB nguồn/đích sau duyệt, trạng thái trước–sau và phục hồi; transaction cục bộ đăng ký không thay thế |
| Phân quyền | Tư vấn gửi đề nghị cho học viên ngoài site bị `403`; Admin Small không được tạo đề nghị; Admin Small nguồn không thể duyệt đề nghị nguồn hoặc site khác; Admin Small đúng site đích và Admin Big có thể quyết định; chỉ Admin Big retry; giáo viên gọi lớp không được phân công bị từ chối |
| Phân tán | Không có JOIN xuyên site; Global Query tổng hợp ở API; một site lỗi được thể hiện là kết quả một phần |
| Đồng bộ chung | Ghi môn/khóa/tài khoản không trả success nếu site bắt buộc chưa được cập nhật; đối soát có thể tiếp tục |
| Nghiệp vụ cục bộ | Đăng ký và lớp cùng site; thu/hoàn giữ lịch sử; nhập điểm và điểm danh đúng phân công |
| Múi giờ | Lịch 07:00/13:00/14:00 và hạn thanh toán đúng `Asia/Ho_Chi_Minh`; chạy API dưới timezone máy chủ khác vẫn không lệch giờ/ngày |
| Thanh toán lặp/lỗi mạng | Cùng idempotency key chỉ tạo một yêu cầu/phiếu; cùng key khác body trả `409`; response mất sau commit vẫn đọc lại được; lỗi trước commit rollback sạch |
| Reload/thoát trang | Reload khi đang chờ phải đọc lại trạng thái; đóng tab không tự hủy; đăng nhập lại có thể tìm yêu cầu đang mở; không tạo yêu cầu thứ hai khi yêu cầu cũ còn mở |
| Cổng thanh toán | Redirect giả không đánh dấu đã thu; webhook sai chữ ký/replay/sai số tiền bị từ chối; callback lặp không tạo thêm phiếu; timeout chưa rõ kết quả chuyển `can_doi_soat` và khóa lượt mới cho tới đối soát |
| Lỗi commit và retry callback | Làm SQL Server lỗi sau khi cổng xác nhận thu; API không ACK webhook trước commit; callback gửi lại/đối soát sau phục hồi chỉ tạo đúng một `PhieuThu` và cập nhật đúng `HocPhi` |
| Gửi đồng thời | Hai request khác key cho cùng khoản phí cùng lúc chỉ tạo tối đa một yêu cầu đang mở; không tạo hai phiên thu ở cổng hoặc ghi quá số dư |
| Bảo mật thanh toán | Tài khoản sai quyền không được thu/hoàn; sửa số tiền/site trong body bị từ chối; số thẻ/CVV/token không xuất hiện trong API, DB, log hoặc analytics |
| Hoàn tiền | Hoàn một phần/toàn phần tạo sự kiện/phiếu mới, giữ nguyên phiếu thu gốc, cập nhật số dư đúng một lần; người không có quyền hoàn bị từ chối |
| Hủy/thất bại/hết hạn | Chỉ cho thử lượt mới sau kết quả cuối đã xác nhận không thu tiền; yêu cầu hủy đang xử lý không được xem là đã hủy |
| Chuyển cơ sở | Tư vấn tạo đề nghị ở nguồn; Admin Big hoặc Admin Small site nhận duyệt/từ chối; thử lỗi trước/sau khi đích commit, giữ account ID, thông báo site nhận idempotent và chạy phục hồi |
| Tài khoản | Mật khẩu sai dùng lỗi chung; tài khoản bị khóa không tạo phiên; reset token hết hạn/đã dùng bị từ chối |
| Học viên | Source có tài khoản/portal và API đọc hồ sơ; chỉ tính vào phạm vi đồ án sau khi nhóm duyệt. Khi được duyệt, kiểm tra hồ sơ liên kết, quyền, site hiện hành và luồng chuyển cơ sở |
| Validation | Gửi thiếu trường, sai kiểu, sai enum, ngày kết thúc trước ngày bắt đầu, ngày ngoài phạm vi và body quá lớn; API từ chối mà không ghi DB |
| SQL injection | Thử payload SQL trên login, search, filter, sort và các endpoint ghi; không được mở rộng kết quả, vượt quyền hoặc thay đổi bảng |
| CRUD thực tế | Với từng tài nguyên được phép: gọi create/read/update trên SQL Server test, đọc lại để xác nhận dữ liệu đã lưu đúng; thử sai quyền và sai site |
| Xóa và lưu lịch sử | Mặc định chỉ xóa dữ liệu nháp chưa được tham chiếu nếu nghiệp vụ cho phép; hóa đơn/phiếu thu, điểm danh, giao dịch và nhật ký không hard-delete. Ngoại lệ: tài khoản Admin Small hoặc nhân viên được hard-delete theo endpoint đã nêu; giữ Logs/chứng từ và giữ hồ sơ nhân viên nếu PhieuThu đang tham chiếu; không thay thao tác xóa bằng inactive |
| Chống spam | Kiểm tra rate limit từng form, `429`/`Retry-After`, CAPTCHA sau ngưỡng và response không tiết lộ tài khoản |
| Ảnh | Kiểm tra signed upload Cloudinary, file MIME giả, file quá lớn, intent hết hạn, user khác dùng public ID, gỡ ảnh còn tham chiếu và không phát sinh file trong source |
| Hiệu năng | Đo p50/p95 theo millisecond với dữ liệu có kích thước ghi rõ; kiểm tra LOCAL, GLOBAL, login và upload riêng |

### Điều kiện kiểm tra create/read/update/delete

Kịch bản phải chạy trên CSDL SQL Server test riêng theo site, không chỉ mock repository. Mỗi thao tác thành công phải được đọc lại từ đúng site để chứng minh dữ liệu đã commit; thao tác sai phải kiểm tra không để lại bản ghi dở dang. Với `REPLICATED-WRITE`, đọc đối chiếu bản sao từng site; với `GLOBAL`, kiểm tra dữ liệu được gộp ở API chứ không ghi vào một CSDL trung tâm.

Không ép mọi bảng có nút xóa. `HocVien` giữ lịch sử chuyển; `PhieuThu`, `DiemDanh`, `LichSuChuyenCoSo` và `Logs` không hard-delete trong luồng nghiệp vụ thông thường. Tài khoản nhân viên/Admin Small: thao tác ngưng đăng nhập là riêng với DELETE; DELETE xóa vật lý tài khoản, phiên và dữ liệu bảo mật phụ, đồng thời giữ Logs/chứng từ. Với nhân viên đã lập phiếu thu, giữ hồ sơ rời tài khoản để bảo toàn khóa ngoại. Kiểm tra tham chiếu và giao dịch đang mở trước khi bắt đầu; ghi dấu retry ở từng site và không tuyên bố ACID xuyên CSDL. Kịch bản delete phải chứng minh tài khoản đã biến mất nhưng dữ liệu lịch sử không mất.

Với mọi route, tối thiểu kiểm tra: thành công; request sai; unauthenticated; role sai; site sai; bản ghi không tồn tại; bản ghi bị cập nhật/xóa song song; site SQL Server mất kết nối; retry cùng request; transaction rollback. Ghi lệnh/kịch bản và kết quả trong PR hoặc tài liệu test; nếu endpoint chưa được cài thì ghi `Chưa chạy — chưa có implementation`, không tự ghi là pass.

## Mục tiêu hiệu năng API và tối ưu truy vấn

Các con số dưới đây là mục tiêu nghiệm thu ban đầu, đo ở API server trong môi trường test được ghi rõ, không phải cam kết tốc độ production. Dùng millisecond (`ms`) và báo p50/p95, kích thước dữ liệu, số site đang hoạt động, số request đồng thời và cấu hình máy.

| Nhóm request | Mục tiêu p95 đề xuất |
|---|---:|
| Đăng nhập và `GET /api/v1/auth/profile/{slug}/` | ≤ 500 ms |
| `LOCAL` đọc | ≤ 300 ms |
| `LOCAL` ghi | ≤ 500 ms |
| `GLOBAL` báo cáo/truy vấn trang đầu | ≤ 1500 ms; nếu site chậm/vắng phải trả trạng thái một phần theo deadline, không chờ vô hạn |
| Ký upload intent Cloudinary | ≤ 300 ms; thời gian truyền bytes tới Cloudinary đo riêng và hiện progress |

Đo phía giao diện theo [mục 9 của `ui-ux.md`](ui-ux.md#9-tốc-độ-và-ngân-sách-hiệu-năng): LCP/INP tính bằng ms; CLS là tỷ lệ không đơn vị. Không đổi các chỉ số trang thành đơn vị giây.

Quy tắc tối ưu:

- Phân trang ở server; mặc định 25 dòng, giới hạn `page_size` tối đa 100; chỉ trả cột cần thiết. Không tải toàn bộ học viên/điểm/phí để lọc ở trình duyệt.
- Dùng `select_related`/`prefetch_related` phù hợp để tránh N+1; đo số query và xem execution plan/IO của SQL Server trước khi thêm index. Index phải theo bộ lọc, khóa ngoại và thứ tự sắp xếp thực tế, không thêm trùng index unique.
- `GLOBAL` lấy site hoạt động từ dữ liệu `CoSo`, gọi các site song song với concurrency có giới hạn, timeout cho từng site và gộp tại tầng API. Không viết cứng Q1/Q7/TD hoặc tuần tự chờ từng site; bổ sung site mới không được yêu cầu sửa vòng lặp cố định.
- Cache chỉ dữ liệu công khai/dùng chung phù hợp. Cache key cho dữ liệu phân quyền phải chứa site và phạm vi người dùng; không dùng chung cache response riêng tư giữa tài khoản. Có invalidation sau khi ghi/đồng bộ.
- Giữ công việc nặng ngoài request đồng bộ khi cần; trả `202` và trạng thái tiến trình cho đồng bộ dài hoặc giao dịch phục hồi. Không giả trả thành công trước khi có trạng thái ghi bền vững.
- Báo cáo và danh sách lớn phải lọc, sắp xếp theo allowlist và phân trang; không chạy truy vấn không giới hạn hoặc tải ảnh qua API server khi có thể upload trực tiếp Cloudinary.

Nếu không đạt p95, xác định bottleneck bằng query log/analyzer an toàn, sửa thuật toán/index/pagination rồi đo lại cùng bộ dữ liệu. Không tối ưu bằng cách bỏ kiểm tra quyền, bỏ transaction cục bộ, bỏ audit hoặc trả thiếu site như thể đủ dữ liệu.

## Mẫu hợp đồng endpoint

Sao chép mẫu này cho từng endpoint sau khi nhóm thống nhất:

```markdown
### [Tên thao tác]
- Trạng thái: Đề xuất / Đã thống nhất / Đã triển khai
- Method/path:
- Người gọi và vai trò:
- Quyền/phạm vi site:
- Kiểu phân tán:
- Mã yêu cầu YC / kịch bản TC liên quan (hoặc Không áp dụng, nêu lý do):
- Site Router chọn site theo:
- Bảng đọc:
- Bảng ghi:
- Transaction cục bộ / giao dịch phân tán:
- Quy tắc request và validation:
- Ví dụ request:
- Ví dụ response thành công:
- HTTP status và mã lỗi:
- Xử lý retry/gửi trùng/cập nhật đồng thời:
- Kiểm tra đã chạy:
- Thay đổi giao diện/schema/tài liệu liên quan:
```

## Các điểm còn phải thống nhất hoặc kiểm chứng

1. CRUD hồ sơ và cấp tài khoản học viên theo thao tác Admin riêng nằm trong FS-STU-01. Portal học viên và SePay có code/schema/UI nhưng vẫn chưa được duyệt phạm vi; không coi việc cấp tài khoản là quyết định bật portal hoặc thanh toán online.
2. Refund API yêu cầu chạy migration `40_enable_tuition_refunds.sql` riêng trên mỗi site. Chưa kiểm chứng migration và API với SQL Server đang dùng; đối chiếu cấu trúc Q1/Q7/TD trước khi bật.
3. API quản lý `CoSo` chưa có; runtime replication cho `CoSo` còn thiếu. `MonHoc`/`KhoaHoc` có service ghi replication; một số luồng ghi `TaiKhoan` vẫn có cơ chế riêng, chưa gom về một điểm vào.
4. Chạy đủ TC-SITE/FRAG/REP/SYNC/DTX/CON/DQ trên các database SQL Server đang dùng. Còn thiếu outage/recovery, fault injection chuyển cơ sở, concurrency hai phiên và Global Query khi thiếu site; xem [ma trận trạng thái](../docs/Trang-Thai-Trien-Khai.md).
5. Xác nhận với giảng viên mức bảo đảm của Coordinator chuyển cơ sở. Cơ chế hiện tại dùng transaction cục bộ và phục hồi tiến về phía trước; không phải ACID nguyên tử xuyên database, MSDTC hoặc 2PC.
6. SMTP, OAuth provider, Cloudinary và SePay cần kiểm tra cấu hình/tích hợp thật tại môi trường tương ứng. Không ghi secret vào source, tài liệu hoặc log.
7. Chốt rate limit bền vững khi chạy nhiều worker, ngưỡng bcrypt và mục tiêu p50/p95 theo môi trường đo.
