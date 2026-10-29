
# Đặc tả API

> Trạng thái: Các method/path nghiệp vụ dưới đây là bản thiết kế đề xuất — cần nhóm thống nhất trước khi xem là hợp đồng cuối cùng. Scaffold Django và tài liệu OpenAPI đang chạy trong `src/api`; hiện mới triển khai liveness endpoint `GET /api/v1/health/`. Swagger UI/OpenAPI có ở môi trường phát triển. Chưa xem endpoint nghiệp vụ nào khác là đã triển khai chỉ vì được mô tả trong tài liệu này.

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
| YC-03 | Một điểm vào ghi bảng dùng chung; chứng minh cơ chế truyền một thay đổi `MonHoc` tới các bản sao, không chạy UPDATE thủ công từng DB (TC-REP-01) |
| YC-04 | Admin Small đề nghị, Admin Big duyệt rồi Coordinator mới chuyển; trạng thái/sự kiện nguồn và đích cho phép kiểm tra lỗi trước/sau commit đích (TC-DTX-01) |
| YC-05 | Bảo vệ sức chứa và tạo đăng ký/học phí trong cùng transaction site; hai phiên tranh chỗ cuối chỉ một yêu cầu thắng (TC-CON-01) |
| YC-06 | Đọc từng site và tổng hợp tại API; khi thiếu site trả `complete=false`, `missing_sites`, không thay dữ liệu thiếu bằng 0 (TC-DQ-01) |
| YC-07 | Trạng thái đồng bộ bền vững, đối soát/retry sau lỗi; chỉ xác nhận hoàn tất khi đủ site bắt buộc, không áp dụng lại thay đổi đã nhận (TC-SYNC-01) |

[Hướng dẫn kiểm chứng](../docs/QLTTNN-Yeu-Cau-Chung-Va-Kiem-Chung.md) quy định điều kiện đầu vào và bằng chứng. Phương pháp replication và mức bảo đảm distributed transaction phải chốt theo README/FS; chưa chốt công cụ không có nghĩa được bỏ các yêu cầu này. Swagger chỉ mô tả endpoint, không chứng minh chúng đã chạy đúng trên SQL Server.

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

- Áp dụng cho mọi phiên đã xác thực của Admin Big, Admin Small, lễ tân, kế toán, nhân viên và giáo viên; nếu sau này bật tài khoản học viên thì áp dụng cùng chính sách. Mỗi phiên/trình duyệt/thiết bị được theo dõi riêng; đăng xuất do idle ở một thiết bị không tự đăng xuất thiết bị khác.
- Thời hạn idle là **3600 giây (60 phút)** kể từ hoạt động người dùng gần nhất. Thời gian được tính bằng đồng hồ phía server, lưu timestamp UTC có timezone; không dựa vào giờ hệ điều hành của trình duyệt.
- Hoạt động được tính gồm thao tác bàn phím, nhấn/chạm, cuộn trang có chủ ý và thao tác nghiệp vụ do người dùng khởi tạo. Không tính polling, refresh tự động, health check, analytics, request nền, tab còn mở hoặc timer. Reload trang không đặt lại thời hạn.
- API phải kiểm tra hết hạn ở **mọi request cần xác thực**, không chỉ dựa vào timer giao diện. Phiên cần trạng thái có thể thu hồi và `last_user_activity_at`/`idle_expires_at` do server quản lý. Chữ ký token hoặc cookie hết hạn tuyệt đối không tự chứng minh idle timeout nếu server không thể xác minh hoạt động gần nhất.
- Khi người dùng hoạt động nhưng không phát sinh request nghiệp vụ, frontend có thể gửi `POST /auth/activity` có CSRF để cập nhật phiên; chỉ gửi khi có sự kiện người dùng thật và giới hạn cập nhật tối đa một lần mỗi 60 giây. Tự động gọi endpoint này theo chu kỳ không có hoạt động người dùng sẽ làm sai chính sách và bị cấm. Request nghiệp vụ do người dùng khởi tạo có thể cập nhật hoạt động trong cùng lần xác thực.
- Khi hết 3600 giây, API từ chối phiên bằng `401` với mã ổn định `SESSION_IDLE_TIMEOUT`, thu hồi trạng thái phiên, hết hạn cookie `HttpOnly` và không xử lý nghiệp vụ. `POST /auth/logout` dùng cùng cơ chế kết thúc phiên khi logout thủ công. Nếu không thể truy cập nơi lưu trạng thái phiên, API không được coi phiên là hợp lệ; trả lỗi dịch vụ phù hợp và không cho qua kiểm tra quyền.
- Frontend đồng bộ hoạt động giữa các tab cùng phiên, hiển thị cảnh báo trước hạn (mặc định 5 phút) và nút “Tiếp tục phiên” chỉ khi API xác nhận phiên còn hạn. Đến hạn hoặc nhận `SESSION_IDLE_TIMEOUT`, frontend xóa trạng thái người dùng trong bộ nhớ, điều hướng về trang đăng nhập với thông báo phiên hết hạn và không giữ token trong storage.
- Chính sách cần kiểm thử: chưa hết hạn tại 59:59; hết hạn tại 60:00; tương tác thật đặt lại hạn; polling/refresh nền không đặt lại; reload/tab ngủ không kéo dài phiên; hoạt động ở tab khác được đồng bộ; logout thủ công thu hồi ngay; các role có cùng chính sách.
- **Phụ thuộc triển khai hiện tại:** chưa có endpoint đăng nhập/logout, model xác thực hay nơi lưu phiên trong API; `DATABASES['default']` cố ý là dummy. Trước khi bật auth, phải chốt nơi lưu trạng thái phiên có thể thu hồi phù hợp mô hình CSDL riêng từng site và cập nhật schema/migration nếu cần. Không tự tạo CSDL nghiệp vụ trung tâm hoặc lưu trạng thái phiên vào một site tùy ý.

### Rate limit và chống dò tài khoản

Các ngưỡng dưới đây là **giá trị khởi đầu đề xuất**, phải cấu hình được, ghi nhận trong môi trường test và điều chỉnh theo lưu lượng thực tế. Không dùng khóa tài khoản vĩnh viễn chỉ vì client gửi sai nhiều lần.

| Form/endpoint | Giới hạn ban đầu đề xuất | Hành vi khi vượt ngưỡng |
|---|---|---|
| Đăng nhập | Tối đa 10 request/IP/phút và 5 lần sai cho cặp tài khoản+IP trong 15 phút | Tăng thời gian chờ; yêu cầu CAPTCHA sau ngưỡng; trả `429` với `Retry-After`; không tiết lộ tên tài khoản hợp lệ |
| Bắt đầu/callback OAuth | Giới hạn riêng theo IP, provider và state; callback chỉ dùng một lần | Từ chối state/code lặp hoặc hết hạn; không cho client điều chỉnh callback URI; không log query có authorization code |
| Đăng ký, chỉ khi được nhóm bật | Tối đa 5 request/IP/giờ và 3 lần cho cùng email/giờ | Xác minh email/CAPTCHA sau ngưỡng; response trùng email không tiết lộ tài khoản đã có |
| Quên mật khẩu | Tối đa 10 request/IP/giờ và 3 lần cho cùng email/giờ | Trả cùng response `202` dù email có tồn tại hay không; không gửi nhiều email reset |
| Xác nhận reset mật khẩu | Giới hạn theo IP và token; token một lần, có hạn | Token sai/hết hạn/đã dùng không đổi dữ liệu; trả lỗi chung và ghi audit không chứa token |

IP chỉ được lấy từ proxy đã tin cậy; không tin header IP tùy ý từ client. Rate limit phải phối hợp IP, tài khoản/email đã chuẩn hóa và thời gian; CAPTCHA không thay thế rate limit. Public registration hiện vẫn **tắt** vì học viên chưa có tài khoản trong schema. Nếu sau này bật, phải áp dụng các giới hạn này trước khi mở endpoint.

Token reset sinh ngẫu nhiên bằng CSPRNG, đủ entropy, chỉ dùng một lần và lưu dạng hash; token gửi qua email không ghi log. Khác với mật khẩu người dùng, token ngẫu nhiên có thể lưu bằng SHA-256/HMAC hash phục vụ tra cứu an toàn; mật khẩu vẫn phải dùng bcrypt.

### Email kích hoạt tài khoản và khôi phục mật khẩu

Django gửi thư từ backend qua SMTP; thông tin kết nối chỉ nằm trong biến môi trường/secret store (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS` hoặc `EMAIL_USE_SSL`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`). Với Gmail, cấu hình mặc định là `smtp.gmail.com:587` + STARTTLS, dùng địa chỉ Gmail và Google App Password. App Password chỉ dành cho SMTP, không phải OAuth Client Secret. Không ghi thông tin này vào source, Git, log, Swagger response hoặc frontend. Chỉ báo gửi thành công sau khi SMTP chấp nhận thư; lỗi gửi thư phải có trạng thái retry an toàn và không log nội dung bí mật.

Khi Admin Big tạo Admin Small hoặc giáo viên, không gửi mật khẩu tạm qua email. Sau khi tài khoản và hồ sơ site được tạo an toàn, gửi email mời người nhận tự đặt mật khẩu bằng token kích hoạt ngẫu nhiên, một lần, có hạn; tài khoản chưa được đăng nhập cho tới khi kích hoạt. Schema hiện tại chưa có bảng token kích hoạt riêng/trạng thái `cho_kich_hoat`, nên phải cập nhật schema và luồng `REPLICATED-WRITE`/phục hồi trước khi bật tính năng mời. Không tái sử dụng token reset cho mục đích kích hoạt.

Quên mật khẩu gửi liên kết đặt lại chứa token có entropy cao; người dùng mở liên kết và tự nhập mật khẩu mới. Token hết hạn theo `PASSWORD_RESET_TIMEOUT` (mặc định 900 giây), chỉ dùng một lần, chỉ lưu hash tại site tiếp nhận và không xuất hiện trong nhật ký. Nếu site lưu tài khoản không sẵn sàng, không báo reset thành công và không cập nhật một phần các bản sao. Endpoint yêu cầu reset vẫn trả cùng thông báo chung `202` dù tài khoản/email tồn tại hay không; rate limit theo IP và email đã chuẩn hóa. Chọn liên kết ngẫu nhiên thay cho mã số ngắn trong phiên bản đầu để giảm khả năng dò mã; nếu sau này dùng OTP số, phải thêm bộ đếm thử/khóa ngắn hạn và lưu hash mã vào schema trước khi triển khai.

Các timeout URL cấu hình ở backend gồm `PASSWORD_RESET_TIMEOUT` (900 giây) và `ACCOUNT_ACTIVATION_TIMEOUT` (86400 giây). `WEB_APP_BASE_URL` chỉ nhận origin đã được cấu hình; không lấy URL redirect tùy ý từ request. Cấu hình SMTP hiện mới là nền tảng, không có endpoint gửi thư cho tới khi các luồng tài khoản được triển khai và kiểm thử.

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

Khai báo `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` và `CLOUDINARY_ROOT_FOLDER` trong `src/api/.env`, không commit các giá trị này. Nếu API secret từng bị chia sẻ, phải rotate trước khi cấu hình giá trị mới. `.env.example` chỉ chứa placeholders. Cấu hình hiện tại mới chuẩn bị biến môi trường và hàm dựng folder path; chưa có endpoint upload hay upload nào được xác nhận hoạt động. Trước khi bật upload phải bổ sung metadata ảnh tại CSDL site phù hợp trong `docs/DATABASE_SCHEMA.md` và triển khai/kiểm thử xác thực, quyền, ký upload và xác minh asset.

Luồng chuẩn: frontend xin upload intent từ API → API cấp chữ ký có thời hạn → frontend gửi bytes ảnh trực tiếp tới Cloudinary → frontend gửi `public_id` về API → API xác minh lại asset rồi gắn metadata vào bản ghi tại site đúng. Nếu upload Cloudinary thành công nhưng ghi metadata thất bại, không báo hoàn tất; ghi nhận asset mồ côi để dọn an toàn.

| Method và path đề xuất | Người gọi | Hành vi |
|---|---|---|
| `POST /api/v1/media/upload-intents` | Người dùng đã xác thực, có quyền sửa hồ sơ/tài nguyên tương ứng | API kiểm tra quyền/site, mục đích và loại ảnh; tạo chữ ký upload Cloudinary hết hạn ngắn, public ID do server sinh |
| `POST /api/v1/media/assets` | Người dùng vừa upload bằng intent hợp lệ | API xác minh chữ ký, public ID, loại tài nguyên, kích thước và metadata từ Cloudinary; sau đó gắn asset vào bản ghi được phép |
| `DELETE /api/v1/media/assets/{ma_media}` | Người có quyền sửa bản ghi sở hữu ảnh | Gỡ liên kết và chỉ xóa asset Cloudinary khi xác nhận không còn tham chiếu; shared asset phải xử lý theo chính sách đồng bộ |

Yêu cầu upload: chỉ MIME ảnh trong allowlist; kiểm tra cả MIME thực và phần mở rộng; giới hạn dung lượng/chiều rộng/chiều cao theo cấu hình; đổi tên bằng public ID phía server; không nhận URL tùy ý rồi tải hộ (tránh SSRF). Có thể dùng Cloudinary transformation để tạo thumbnail/responsive format. Upload intent hết hạn, gắn với tài khoản, site, mục đích và bản ghi được phép; không cho tái sử dụng để ghi đè ảnh tùy ý. Trước khi xóa asset, xác minh không còn bản ghi tham chiếu tại các site cần thiết; nếu xóa metadata/asset bị lỗi giữa chừng, trả trạng thái phục hồi và không để URL hỏng được báo là đã xóa sạch.

SQL Server lưu metadata như `public_id`, `secure_url`, định dạng, kích thước, alt text và liên kết bản ghi; không lưu bytes ảnh. Metadata phải theo đúng vị trí dữ liệu: ảnh của hồ sơ site ghi `LOCAL`; ảnh thuộc danh mục dùng chung đồng bộ theo `REPLICATED-WRITE`. Không tạo database trung tâm cho media. Schema hiện chưa mô tả bảng/cột metadata Cloudinary; phải bổ sung `MediaAsset` hoặc các cột quan hệ đã thống nhất trong `docs/DATABASE_SCHEMA.md` trước khi triển khai upload.

## Danh tính, vai trò và phạm vi site

Đây là một API dùng chung cho một frontend. Người dùng không gửi vai trò để tự chọn quyền. API xác định danh tính từ phiên đăng nhập, kiểm tra trạng thái tài khoản và dựng phạm vi trên mỗi request.

| Người dùng | Biểu diễn theo schema hiện tại | Phạm vi API |
|---|---|---|
| Admin Big | `TaiKhoan.vai_tro = admin`, `ma_co_so = NULL` | Toàn hệ thống; thao tác nhiều site phải được gắn `GLOBAL`, `REPLICATED-WRITE` hoặc `DISTRIBUTED-TX` rõ ràng |
| Admin Small | `TaiKhoan.vai_tro = nhan_vien`, `NhanVien.chuc_vu = quan_ly_co_so`, có `ma_co_so` | Một site được gán; không được chọn site khác trong query/body để mở rộng quyền |
| Lễ tân | `nhan_vien` với chức vụ tương ứng | Hồ sơ học viên, đăng ký và xếp lớp trong site được gán |
| Kế toán | `nhan_vien` với chức vụ tương ứng | Học phí và phiếu thu trong site được gán |
| Giáo viên | `TaiKhoan.vai_tro = giao_vien`, hồ sơ `GiaoVien` tại site | Chỉ lớp/buổi được phân công; API kiểm tra phân công ở mỗi thao tác |
| Học viên | **Chưa có tài khoản trong schema hiện tại** | Không có quyền hoặc endpoint hoạt động. API portal học viên ở mục “Phạm vi học viên đề xuất” chỉ được mở sau khi nhóm duyệt và cập nhật schema |

`Admin Small` là chức vụ của nhân viên, không thêm giá trị `admin_small` vào `TaiKhoan.vai_tro`. Nếu một endpoint nhận bộ lọc `ma_co_so`, API chỉ chấp nhận site đúng quyền; với Admin Big, site đích vẫn phải tồn tại và đang hoạt động. Không dùng tiền tố mã học viên để xác định site hiện hành.

## Endpoint dùng chung: Web công khai và xác thực

Tất cả method/path dưới đây là **đề xuất cho đặc tả**, chưa khẳng định đã có code. Đăng ký công khai không mở trong phạm vi hiện tại: Admin Big tạo tài khoản nội bộ; học viên chưa có tài khoản.

| Method và path | Người gọi | Kiểu truy cập | Dữ liệu đọc/ghi và hành vi |
|---|---|---|---|
| `GET /api/v1/public/sites` | Khách chưa đăng nhập | Đọc bản sao dùng chung | Đọc `CoSo`; chỉ trả trường công khai của site đang hoạt động |
| `GET /api/v1/public/courses?search=...&ma_mon_hoc=...&trinh_do=...&sort=...&cursor=...&limit=...` | Khách chưa đăng nhập | Đọc bản sao dùng chung | Đọc `MonHoc`, `KhoaHoc`; chỉ cho sort theo allowlist; không trả khóa học đã đóng |
| `GET /api/v1/public/courses/{ma_khoa_hoc}` | Khách chưa đăng nhập | Đọc bản sao dùng chung | Chi tiết khóa học; mã không tồn tại trả `404` |
| `GET /api/v1/public/classes?ma_co_so=...&ma_khoa_hoc=...` | Khách chưa đăng nhập | `LOCAL` nếu lọc một site; `GLOBAL` nếu xem nhiều site | Đọc `LopHoc`, lịch cần công khai; Global Query phải trả `meta.complete` và `missing_sites` |
| `POST /api/v1/auth/login` | Vai trò nội bộ hiện có | `GLOBAL` tra cứu tài khoản nhân bản, xác thực ở Django | Nhận tên đăng nhập/mật khẩu; trả phiên và ngữ cảnh quyền, không trả hash mật khẩu hoặc chuỗi kết nối |
| `GET /api/v1/auth/oauth/{provider}/start?intent=login` | Người chưa đăng nhập; `provider` chỉ `google` hoặc `facebook` | Khởi tạo OAuth; chưa truy cập CSDL nghiệp vụ | Tạo state một lần rồi chuyển hướng tới provider; redirect URI lấy từ cấu hình server |
| `GET /api/v1/auth/oauth/{provider}/callback` | Callback Google/Facebook | `GLOBAL` xác minh liên kết nhân bản và đọc `TaiKhoan` | Đổi authorization code ở server; xác minh provider subject; chỉ tài khoản nội bộ hoạt động mới được cấp phiên |
| `GET /api/v1/auth/oauth/{provider}/link/start` | Người đã đăng nhập và xác thực lại gần đây | Khởi tạo liên kết; callback ghi bằng `REPLICATED-WRITE` | Bắt đầu ghép danh tính provider với `ma_tai_khoan` lấy từ phiên; không tìm tài khoản theo email |
| `GET /api/v1/auth/oauth/{provider}/link/callback` | Callback Google/Facebook trong luồng link | `REPLICATED-WRITE` | Ghi liên kết giống nhau tới mọi site hoạt động; nếu thiếu site hoặc xung đột thì không báo thành công toàn phần |
| `DELETE /api/v1/auth/oauth/{provider}/link` | Người đã đăng nhập, xác thực lại gần đây | `REPLICATED-WRITE` | Thu hồi liên kết ở mọi site; giữ lịch sử và bảo đảm còn phương thức đăng nhập hợp lệ |
| `POST /api/v1/auth/register` | Không có trong phạm vi hiện tại | Tắt/chưa triển khai | Chưa cấp tài khoản công khai; chỉ mở sau khi nhóm duyệt đối tượng đăng ký, schema, xác minh email và rate limit |
| `GET /api/v1/auth/me` | Người đã đăng nhập | Đọc ngữ cảnh phiên và hồ sơ an toàn đúng site | Trả vai trò/chức vụ, site, phạm vi lớp, quyền được phép, trang mặc định và thông tin hồ sơ được phép hiển thị trên trang cá nhân; không trả bí mật xác thực |
| `POST /api/v1/auth/logout` | Người đã đăng nhập | Hủy phiên | Thu hồi phiên phía server và xóa cookie nếu dùng cookie |
| `POST /api/v1/auth/password-change` | Người đã đăng nhập | `LOCAL` kiểm tra tài khoản; `REPLICATED-WRITE` cập nhật bản sao mật khẩu theo chính sách | Nhận mật khẩu hiện tại và mật khẩu mới; xác minh bằng bcrypt, thu hồi phiên khác và ghi audit an toàn |
| `POST /api/v1/auth/password-reset-requests` | Người chưa đăng nhập | Tra cứu nhiều bản tài khoản; tạo token cục bộ | Luôn trả thông báo chung để không tiết lộ email/tên đăng nhập có tồn tại hay không |
| `POST /api/v1/auth/password-resets` | Người có liên kết đặt lại | `LOCAL` kiểm token; `REPLICATED-WRITE` cập nhật tài khoản | Token dùng một lần, có hạn; cập nhật bản băm mật khẩu tại mọi site bắt buộc theo chính sách |
| `POST /api/v1/auth/account-activations` | Người có liên kết mời hợp lệ | `LOCAL` kiểm token; `REPLICATED-WRITE` kích hoạt và đặt mật khẩu mới | Chỉ bật sau khi schema có trạng thái tài khoản chờ kích hoạt và token kích hoạt riêng; không dùng chung token reset |

`POST /api/v1/auth/register` hiện là route tắt: nếu `RegisterPage` còn hiển thị, trang chỉ giải thích điều kiện/liên hệ, không gửi tạo tài khoản. Admin Big tạo tài khoản nội bộ. Nếu nhóm duyệt portal học viên, đăng ký/kích hoạt phải được đặc tả và cập nhật schema trước khi bật endpoint; tuyệt đối không tự mở public signup.

### Đăng nhập và liên kết tài khoản Google/Facebook — đặc tả, chưa triển khai

Hai nút Google và Facebook dùng chung màn hình đăng nhập. Đây là phương thức bổ sung cho tài khoản nội bộ có `vai_tro` `admin`, `nhan_vien` hoặc `giao_vien`; học viên vẫn chưa có tài khoản trong phạm vi hiện tại. API chưa có endpoint đăng nhập nào được triển khai. Các route trong bảng là thiết kế, không được frontend gọi cho tới khi code, CSDL và OAuth applications đã được cấu hình, kiểm thử.

**Luồng đăng nhập:**

1. Người dùng bấm nhà cung cấp tương ứng; trình duyệt mở `GET /api/v1/auth/oauth/google/start?intent=login` hoặc `.../facebook/start?intent=login`. Backend chỉ nhận provider từ allowlist, tạo state ngẫu nhiên dùng một lần (và nonce cho Google), gắn với trình duyệt bằng cookie bảo mật tạm thời rồi chuyển hướng sang provider. `redirect_uri` được cấu hình cố định ở API, không lấy từ query/body.
2. Google/Facebook trả authorization code về callback đã đăng ký của API. Backend đối chiếu state/cookie, đổi code trực tiếp với provider qua HTTPS rồi xác minh; không chuyển provider token sang frontend và không ghi code/token vào log.
3. Google ID token phải được xác minh chữ ký bằng JWKS chính thức và kiểm tra `iss`, `aud`, `exp`, `iat`, `nonce`; định danh bền vững là `sub`, không phải email. Facebook access token phải được introspect server-to-server (app ID đúng, token hợp lệ, đúng subject và chưa hết hạn); sau đó lấy Facebook app-scoped user ID. Chỉ yêu cầu quyền dữ liệu tối thiểu.
4. API tìm provider subject trong `TaiKhoan.google_subject` hoặc `TaiKhoan.facebook_subject` tại từng CSDL site riêng, sau đó xác nhận các bản sao `TaiKhoan` nhất quán, tài khoản đang hoạt động và vai trò/phạm vi còn hợp lệ. Đây là `GLOBAL`; nếu site cần thiết mất kết nối hoặc các bản sao mâu thuẫn, từ chối cấp phiên và trả lỗi tạm thời, không âm thầm chọn một bản.
5. Sau khi xác minh, API tạo phiên ứng dụng riêng bằng cơ chế phiên có thể thu hồi đã chốt, đặt cookie `HttpOnly`, `Secure`, `SameSite` phù hợp và redirect về URL callback web trong allowlist. Không trả Google/Facebook token hoặc quyền do provider cung cấp về trình duyệt. Frontend gọi `GET /auth/me` để nhận vai trò, site và phạm vi từ API.

Facebook có thể không trả email hoặc người dùng có thể từ chối quyền email; điều đó không ảnh hưởng xác thực vì API dùng Facebook user ID. Không yêu cầu quyền `email` chỉ để ghép tài khoản. Google email đã xác minh cũng không dùng làm khóa: chỉ subject đã liên kết mới đăng nhập được.

**Luồng liên kết:** người dùng đăng nhập bằng tài khoản nội bộ hiện hữu, xác thực lại bằng mật khẩu gần thời điểm liên kết, rồi bắt đầu OAuth trong chế độ `link`. Callback chỉ ghi subject vào cột provider tương ứng của `TaiKhoan` lấy từ phiên đã xác thực. Nếu subject đã thuộc tài khoản khác, API từ chối; không tự chuyển liên kết. Thu hồi liên kết đặt cột tương ứng về `NULL` qua Replicated-Write đủ site. Không có chức năng tự đăng ký qua Google/Facebook hoặc Admin Big gắn danh tính cho người khác.

**Redirect và lỗi:** callback URL/`return_to` chỉ lấy từ allowlist cấu hình; từ chối URL tùy ý để chống open redirect. Sai state, code hết hạn, provider lỗi, identity chưa liên kết, tài khoản bị khóa hoặc dữ liệu site không đủ đều không tạo phiên. Người dùng nhận thông báo chung; nhật ký chỉ ghi provider, mã lỗi nội bộ, kết quả và mã tài khoản nếu xác định an toàn. Không ghi authorization code, ID/access/refresh token, client secret, email hoặc provider subject.

**Phân tán:** provider subject nằm ngay trên bảng `TaiKhoan` đã nhân bản ở từng site, không có bảng OAuth riêng hoặc CSDL identity trung tâm. Liên kết/thu hồi là `REPLICATED-WRITE` qua một service duy nhất; cập nhật cột provider tương ứng tới mọi site hoạt động. Nếu một site bắt buộc lỗi, không báo thành công; lưu kết quả để retry/đối soát. Đăng nhập là `GLOBAL`, đọc từng site riêng rồi đối chiếu ở API. Không có FK/JOIN xuyên site. Vai trò và site luôn lấy từ `TaiKhoan`, không lấy từ provider profile.

**Cấu hình:** tạo OAuth application riêng cho môi trường phát triển và cấu hình được duyệt cho môi trường triển khai; khai báo callback chính xác trong Google Cloud và Meta Developers. API cần `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI`, `FACEBOOK_OAUTH_APP_ID`, `FACEBOOK_OAUTH_APP_SECRET`, `FACEBOOK_OAUTH_REDIRECT_URI` và `OAUTH_WEB_RETURN_URL`. Client secret chỉ ở Django/environment, không ở Next.js, Git, Swagger example hay log. Trước khi bật phải hoàn tất TLS, state/nonce dùng một lần, cookie/CSRF, rate limit riêng từng provider và cơ chế phiên có thể thu hồi.

Start/callback là redirect của trình duyệt, không nhận provider token từ frontend. Khi liên kết, API lấy tài khoản hiện tại từ cookie phiên, không nhận `ma_tai_khoan` từ request. Callback thành công đặt cookie phiên của ứng dụng và redirect tới trang đã cấu hình; các endpoint chỉ xuất hiện trong Swagger khi có code đã triển khai và test tích hợp.

## Endpoint quản trị theo Admin Big và Admin Small

Các quyền dưới đây phải được kiểm tra ở API, không chỉ ẩn menu. `GLOBAL` chỉ dành cho màn hình tổng hợp/tra cứu toàn cục; không có câu SQL JOIN tới database của site khác.

| Method và path | Người gọi | Kiểu phân tán | Site và bảng chính |
|---|---|---|---|
| `GET /api/v1/admin/sites` | Admin Big | Đọc bản sao `CoSo`; tổng hợp trạng thái kết nối theo nhu cầu | `CoSo` ở bản sao tại site; không trả thông tin bí mật kết nối |
| `GET /api/v1/admin/sites/{ma_co_so}` | Admin Big | Đọc bản sao `CoSo` và trạng thái site | Chi tiết cơ sở; không trả credential/chuỗi kết nối |
| `GET /api/v1/admin/dashboard` | Admin Big | `GLOBAL` | Số liệu toàn hệ thống, việc chờ duyệt và tình trạng site; response báo site thiếu |
| `POST /api/v1/admin/sites` | Admin Big | Điều phối cấu hình + nạp dữ liệu dùng chung | Tạo metadata và khởi chạy quy trình provisioning; không cho trình duyệt truyền credential SQL Server |
| `PATCH /api/v1/admin/sites/{ma_co_so}/status` | Admin Big | `REPLICATED-WRITE`/quy trình đóng site | Chỉ nhận trạng thái cho phép; trước khi đóng phải xử lý giao dịch chuyển và dữ liệu đang hoạt động theo README mục 5.14 |
| `GET /api/v1/admin/admins-small` | Admin Big | `GLOBAL` hoặc đọc bản sao tài khoản kèm tra cứu hồ sơ từng site | Gộp Admin Small theo site; phản hồi một phần nếu site thiếu |
| `GET /api/v1/admin/admins-small/{ma_tai_khoan}` | Admin Big | `GLOBAL` định vị rồi `LOCAL` đọc hồ sơ | Chi tiết tài khoản và cơ sở được phân công; báo rõ site thiếu |
| `POST /api/v1/admin/admins-small` | Admin Big | Tài khoản `REPLICATED-WRITE` + hồ sơ `LOCAL` | Tạo tài khoản `nhan_vien`, phân công `ma_co_so`, tạo `NhanVien.chuc_vu = quan_ly_co_so`; phải có trạng thái phục hồi nếu hai chặng lệch |
| `GET /api/v1/admin/accounts` | Admin Big | `GLOBAL`/bản sao tài khoản | Danh sách tài khoản nội bộ, trạng thái và phạm vi; không trả hash mật khẩu |
| `GET /api/v1/admin/accounts/{ma_tai_khoan}` | Admin Big | Đọc bản sao tài khoản và tra cứu hồ sơ site cần thiết | Chi tiết tài khoản/phạm vi được phép; không trả hash hoặc secret |
| `PATCH /api/v1/admin/accounts/{ma_tai_khoan}/status` | Admin Big | `REPLICATED-WRITE` | Khóa/mở tài khoản qua dịch vụ đồng bộ chung; không cho tự khóa tài khoản Admin Big cuối cùng nếu nhóm đặt quy tắc đó |
| `GET /api/v1/admin/teachers?ma_co_so=...` | Admin Big hoặc Admin Small đúng site | Admin Big: `GLOBAL`; Admin Small: `LOCAL` | Đọc hồ sơ `GiaoVien`, trạng thái và phân công; site lấy từ quyền nếu Admin Small |
| `GET /api/v1/admin/teachers/{ma_giao_vien}` | Admin Big hoặc Admin Small đúng site | Admin Big: định vị rồi `LOCAL`; Admin Small: `LOCAL` | Chi tiết giáo viên và các phân công trong phạm vi được cấp |
| `POST /api/v1/admin/teachers` | Admin Big | Tài khoản `REPLICATED-WRITE` + hồ sơ `LOCAL` | Tạo tài khoản `giao_vien`, hồ sơ `GiaoVien` tại cơ sở được chọn; không để tài khoản hoạt động nếu hồ sơ site chưa tạo |
| `PUT /api/v1/admin/teachers/{ma_giao_vien}/assignments` | Admin Big hoặc Admin Small đúng site | `LOCAL` | Cập nhật lớp/buổi được giao qua `LopHoc` và `BuoiHoc`; từ chối lớp/buổi ngoài site hoặc trùng lịch |
| `GET /api/v1/admin/subjects` / `GET /api/v1/admin/courses` | Vai trò có quyền xem | Đọc bản sao dùng chung | Đọc `MonHoc`, `KhoaHoc` |
| `POST /api/v1/admin/subjects` / `PATCH /api/v1/admin/subjects/{ma_mon_hoc}` | Admin Big | `REPLICATED-WRITE` | Tạo/cập nhật `MonHoc` qua dịch vụ đồng bộ chung tới mọi site đang hoạt động |
| `POST /api/v1/admin/courses` / `PATCH /api/v1/admin/courses/{ma_khoa_hoc}` | Admin Big | `REPLICATED-WRITE` | Tạo/cập nhật `KhoaHoc` qua dịch vụ đồng bộ chung; validate môn học tồn tại trong dữ liệu dùng chung |
| `GET /api/v1/students?search=...&trang_thai=...&cursor=...&limit=...` | Admin Big; Admin Small/lễ tân trong site | Admin Big: `GLOBAL`; nhân viên cơ sở: `LOCAL` | Tìm/lọc `HocVien`, phân trang; giới hạn kết quả theo phạm vi người gọi, không đoán site bằng tiền tố mã |
| `POST /api/v1/students` | Admin Small/lễ tân đúng site | `LOCAL` | Tạo `HocVien` tại site do API lấy từ tài khoản; không nhận site tùy ý từ client |
| `GET /api/v1/students/{ma_hoc_vien}` | Admin Big; nhân viên đúng site | Admin Big: `GLOBAL` định vị hồ sơ hiện hành; nhân viên: `LOCAL` | Trả hồ sơ theo quyền; không JOIN xuyên CSDL |
| `PATCH /api/v1/students/{ma_hoc_vien}` | Admin Small/lễ tân đúng site | `LOCAL` | Chỉ cho sửa trường hồ sơ được phép; kiểm tra version để tránh ghi đè cập nhật mới |
| `GET /api/v1/classes` / `POST /api/v1/classes` | Admin Small đúng site | `LOCAL` | Đọc/tạo `LopHoc`; khi tạo lịch phải kiểm tra khóa học, giáo viên, phòng, lịch và sức chứa cùng site |
| `GET /api/v1/classes/{ma_lop}` / `PATCH /api/v1/classes/{ma_lop}` | Admin Small đúng site; giáo viên chỉ đọc lớp được giao | `LOCAL` | Không cho đổi lớp sang site khác; ghi nhật ký các thay đổi quan trọng |
| `GET /api/v1/classes/{ma_lop}/sessions` / `POST /api/v1/classes/{ma_lop}/sessions` | Admin Small đúng site; giáo viên được phân công chỉ đọc | `LOCAL` | Đọc/tạo `BuoiHoc`; kiểm tra phòng, giờ, giáo viên và trùng lịch trong cùng site |
| `PATCH /api/v1/classes/{ma_lop}/sessions/{ma_buoi}` | Admin Small đúng site | `LOCAL` | Sửa lịch/buổi hợp lệ, cập nhật audit và từ chối nếu phát sinh xung đột |
| `GET /api/v1/site/dashboard` | Admin Small, lễ tân, kế toán đúng site | `LOCAL` | Tóm tắt việc cần xử lý tại site được gán; chỉ trả widget phù hợp quyền |
| `GET /api/v1/enrollments?ma_hoc_vien=...&ma_lop=...` | Admin Small/lễ tân tại site; Admin Big theo quyền | `LOCAL` hoặc `GLOBAL` theo phạm vi được cấp | Đọc `DangKy`; API giới hạn site, phân trang và trạng thái |
| `GET /api/v1/enrollments/{ma_dang_ky}` | Admin Small/lễ tân đúng site; Admin Big theo quyền | `LOCAL` hoặc định vị rồi `LOCAL` | Chi tiết đăng ký, lớp và khoản học phí liên quan; không JOIN xuyên site |
| `GET /api/v1/tuition?ma_hoc_vien=...&ma_dang_ky=...&trang_thai=...&cursor=...&limit=...` | Kế toán/Admin Small theo quyền; Admin Big theo quyền | `LOCAL` hoặc `GLOBAL` theo phạm vi | Tìm/lọc `HocPhi`, phân trang; không trả dữ liệu ngoài quyền tài chính |
| `GET /api/v1/tuition/{ma_hoc_phi}` | Kế toán/Admin Small theo quyền; Admin Big theo quyền | `LOCAL` hoặc định vị rồi `LOCAL` | Chi tiết khoản phí, dư nợ và lịch sử thu/hoàn tại site sở hữu dữ liệu |
| `GET /api/v1/tuition-receipts?ma_hoc_phi=...&ma_hoc_vien=...&ma_phieu=...&tu_ngay=...&den_ngay=...&loai=...&cursor=...&limit=...` | Kế toán; Admin Small theo quyền; Admin Big theo quyền | `LOCAL` hoặc `GLOBAL` theo phạm vi | Tìm/lọc biên nhận theo học phí, học viên, mã phiếu, khoảng ngày và loại thu/hoàn; phân trang, giới hạn site và quyền tài chính |
| `GET /api/v1/tuition-receipts/{ma_phieu}` | Kế toán; Admin Small theo quyền; Admin Big theo quyền | `LOCAL` hoặc định vị rồi `LOCAL` | Chi tiết biên nhận/hoàn tiền; không trả dữ liệu thẻ hoặc bí mật cổng |
| `GET /api/v1/reports/site-summary?ma_co_so=...&tu_ngay=...&den_ngay=...` | Admin Big; Admin Small đúng site | Admin Big: `GLOBAL`, hoặc `LOCAL` khi lọc một site; Admin Small: `LOCAL` | Tổng hợp số học viên/lớp và chỉ số vận hành trong phạm vi được cấp; nêu site thiếu |
| `GET /api/v1/reports/tuition-by-site?ma_co_so=...&tu_ngay=...&den_ngay=...` | Admin Big; Admin Small đúng site | Admin Big: `GLOBAL`, hoặc `LOCAL` khi lọc một site; Admin Small: `LOCAL` | Tổng hợp phải thu/đã thu/còn nợ/hoàn theo kỳ và site từ `HocPhi`, `PhieuThu`; không trả PII không cần thiết |
| `GET /api/v1/reports/audit-logs?ma_co_so=...&ma_tai_khoan=...&tu_ngay=...&den_ngay=...&cursor=...&limit=...` | Admin Big; Admin Small đúng site | Admin Big: `GLOBAL`, hoặc `LOCAL` khi lọc một site; Admin Small: `LOCAL` | Lọc/phân trang `NhatKyHeThong`; site bị giới hạn theo quyền và kết quả toàn cục phải báo site thiếu |

`POST /admin/sites` không có nghĩa API tự tạo CSDL tùy ý bằng credential từ browser. Khâu tạo database, cấu hình kết nối bí mật, chạy migration và nạp bản sao phải thuộc provisioning phía server/nhóm triển khai; endpoint chỉ khởi chạy quy trình đã được bảo vệ.

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

## Phạm vi học viên đề xuất — chưa được bật

README/schema hiện tại không có tài khoản học viên: `TaiKhoan.vai_tro` chỉ gồm `admin`, `nhan_vien`, `giao_vien`; `HocVien` chưa liên kết với `TaiKhoan`. Để API không hứa chức năng chưa có, các route sau chỉ là **phương án tối thiểu để nhóm duyệt**, không được triển khai trước khi schema và quy tắc tài khoản được cập nhật.

Đề xuất giới hạn ban đầu là **portal chỉ đọc dữ liệu của chính học viên**: xem hồ sơ, đăng ký/lớp hiện tại, lịch, học phí và điểm. Không tự đăng ký khóa học, đóng học phí online, sửa hồ sơ quan trọng hoặc tạo tài khoản công khai. Nhân viên tiếp tục thực hiện sáu nghiệp vụ bắt buộc theo các endpoint hiện có.

| Method và path đề xuất | Kiểu phân tán | Dữ liệu/điều kiện |
|---|---|---|
| `GET /api/v1/student/me` | `GLOBAL` định vị hồ sơ hiện hành, sau đó `LOCAL` đọc | Hồ sơ `HocVien` có tài khoản đang liên kết; chỉ trả bản hiện hành, không trả site khác/history nhạy cảm |
| `GET /api/v1/student/me/enrollments` | `GLOBAL` định vị rồi `LOCAL` | Đăng ký của học viên hiện hành tại site chứa hồ sơ `dang_hoc` |
| `GET /api/v1/student/me/schedule` | `GLOBAL` định vị rồi `LOCAL` | `DangKy`, `LopHoc`, `BuoiHoc` hiện hành |
| `GET /api/v1/student/me/tuition` | `GLOBAL` định vị rồi `LOCAL` | Số phải đóng và phiếu thu chỉ đọc; không trả thông tin thanh toán nhạy cảm |
| `GET /api/v1/student/me/grades` | `GLOBAL` định vị rồi `LOCAL` | Chỉ điểm của đăng ký thuộc hồ sơ hiện hành |

**Điều kiện để chuyển các route học viên từ đề xuất sang hợp đồng:** nhóm phải duyệt có cấp tài khoản hay không; ai tạo/kích hoạt; cơ chế xác minh danh tính; quyền xem/sửa; hành vi khi học viên chuyển cơ sở. Nếu duyệt, cập nhật `docs/DATABASE_SCHEMA.md` để thêm mô hình liên kết duy nhất giữa tài khoản và `HocVien` (và vai trò/điều kiện nhân bản tương ứng), cập nhật README về đăng nhập, đồng bộ `specs/ui-ux.md` và đổi trạng thái route trong file này. Không suy liên kết bằng email đơn thuần; không JOIN xuyên site.

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

`meta` có thể bỏ với response `LOCAL`; mọi response `GLOBAL` bắt buộc có `complete` và `missing_sites`. Response phân trang thêm thông tin phân trang, không được trả số lượng toàn cục nếu chỉ đọc được một phần.

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
| Đăng ký khóa học | `POST /api/v1/enrollments` | Admin Small, lễ tân | `LOCAL` | Site học viên/lớp; đọc `HocVien`, `LopHoc`; ghi `DangKy`, `HocPhi`, cập nhật sĩ số `LopHoc` |
| Xếp/đổi lớp | `PATCH /api/v1/enrollments/{ma_dang_ky}/class` | Admin Small, lễ tân | `LOCAL` | Site của đăng ký; đọc lớp và sĩ số; cập nhật `DangKy`, sĩ số hai lớp |
| Thu/hoàn học phí tại quầy | `POST /api/v1/tuition-receipts` | Kế toán; Admin Small theo quyền | `LOCAL` | Site chứa `HocPhi`; ghi `PhieuThu`, cập nhật số đã thu/trạng thái `HocPhi`; bắt buộc idempotency key |
| Tạo/tiếp tục yêu cầu thanh toán trực tuyến (nếu nhóm chọn tích hợp cổng) | `POST /api/v1/tuition-payment-attempts` | Vai trò thanh toán đã được nhóm duyệt | `LOCAL` | Lưu yêu cầu tại đúng site của `HocPhi`; chưa ghi `PhieuThu` hay tăng số đã thu khi chưa xác minh thành công |
| Tra cứu trạng thái thanh toán | `GET /api/v1/tuition-payment-attempts/{ma_yeu_cau}` | Người tạo và nhân viên có quyền tại site; Admin Big theo quyền | `LOCAL` hoặc `GLOBAL` định vị rồi `LOCAL` | Đọc trạng thái bền vững tại site chứa khoản học phí; không suy site từ tiền tố mã |
| Tiếp tục yêu cầu còn mở | `GET /api/v1/tuition/{ma_hoc_phi}/payment-attempts?active=true` | Người học đã được liên kết (chỉ khi portal được duyệt); nhân viên có quyền tại site | `LOCAL` sau khi định vị site nếu cần | Tìm yêu cầu còn mở sau khi đóng tab, đổi thiết bị hoặc mất mã yêu cầu |
| Yêu cầu hủy thanh toán đang chờ | `POST /api/v1/tuition-payment-attempts/{ma_yeu_cau}/cancel` | Người tạo và nhân viên có quyền tại site | `LOCAL` | Ghi yêu cầu hủy; chỉ chuyển `da_huy` khi cổng xác nhận chưa thu/đã hủy |
| Cổng thanh toán báo kết quả | `POST /api/v1/payment-providers/{provider}/webhook` | Cổng thanh toán qua chữ ký xác thực | `LOCAL` | Site được xác định từ tham chiếu giao dịch phía server; xử lý sự kiện lặp an toàn, chỉ ghi phiếu thu một lần |
| Quản lý điểm | `PUT /api/v1/enrollments/{ma_dang_ky}/grades/{loai_diem}` | Giáo viên được phân công; quản lý theo quyền | `LOCAL` | Site của lớp/đăng ký; đọc phân công và đăng ký; ghi `Diem`, nhật ký chỉnh sửa |
| Tạo đề nghị chuyển | `POST /api/v1/transfers` | Admin Small | `LOCAL` | Nguồn lấy từ tài khoản; ghi `GiaoDichChuyenCoSo`, thêm `LichSuChuyenCoSo`; chưa ghi site đích |
| Hộp thư đề nghị | `GET /api/v1/transfers/inbox` | Admin Big | `GLOBAL` | Đọc riêng các site đang hoạt động; gộp kết quả trong API; trả trạng thái đầy đủ/thiếu site |
| Duyệt đề nghị | `POST /api/v1/transfers/{ma_chuyen}/approve` | Admin Big | `LOCAL` ghi quyết định, rồi `DISTRIBUTED-TX` | Quyết định ghi tại nguồn; Coordinator mới phối hợp nguồn/đích sau khi duyệt |
| Từ chối đề nghị | `POST /api/v1/transfers/{ma_chuyen}/reject` | Admin Big | `LOCAL` | Ghi `tu_choi`, người duyệt, thời điểm, lý do và sự kiện tại nguồn; hồ sơ học viên không đổi |
| Xem trạng thái chuyển | `GET /api/v1/transfers/{ma_chuyen}` | Admin Big; Admin Small trong phạm vi được phép | Admin Big: `GLOBAL` để định vị nguồn; Admin Small: `LOCAL` tại site được gán | Đọc trạng thái tại nguồn; không suy ra site từ tiền tố mã học viên |
| Thống kê học viên theo cơ sở | `GET /api/v1/reports/students-by-site` | Admin Big toàn hệ thống; Admin Small site mình | `LOCAL` hoặc `GLOBAL` tùy phạm vi | Đọc `HocVien` và trạng thái chuyển liên quan; gộp tại API khi nhiều site |
| Tổng quan vận hành cơ sở | `GET /api/v1/reports/site-summary` | Admin Big; Admin Small đúng site | Admin Big: `GLOBAL`; Admin Small: `LOCAL` | Tổng hợp số học viên/lớp và chỉ số vận hành; gộp ở API, báo site thiếu |
| Thống kê học phí | `GET /api/v1/reports/tuition-by-site` | Admin Big; Admin Small đúng site | Admin Big: `GLOBAL`; Admin Small: `LOCAL` | Đọc `HocPhi`, `PhieuThu`; tổng hợp phải thu/đã thu/còn nợ/hoàn theo kỳ và site |

## Request và quy tắc kiểm tra chính

Các trường dưới đây là phần nghiệp vụ tối thiểu để đặc tả. Kiểu SQL chính xác, khóa ngoại và giá trị enum phải đối chiếu schema trước khi triển khai.

### Đăng nhập và nạp quyền

`POST /api/v1/auth/login` nhận:

```json
{
  "ten_dang_nhap": "nhanvien.q1",
  "mat_khau": "<không ghi vào log>"
}
```

API tra cứu bản `TaiKhoan` nhân bản, so sánh với hash mật khẩu, kiểm tra `trang_thai`, rồi dựng quyền từ tài khoản và hồ sơ tương ứng. Không nhận `vai_tro`, `ma_co_so` hoặc danh sách lớp từ body. Đăng nhập sai, tài khoản bị khóa và tài khoản không tồn tại dùng thông báo chung; ghi kết quả vào nhật ký nhưng không ghi tên đăng nhập nhạy cảm, mật khẩu hay token.

Khuyến nghị phiên trình duyệt dùng cookie `HttpOnly`, `Secure`, `SameSite` và cơ chế CSRF phù hợp; không lưu access token/mật khẩu trong `localStorage`. Nếu nhóm chọn cơ chế bearer token khác, phải đặc tả thời hạn, thu hồi, refresh và nơi lưu trước khi code.

`GET /api/v1/auth/me` trả ngữ cảnh tối thiểu để giao diện dựng menu và route:

```json
{
  "data": {
    "user": {
      "ma_tai_khoan": "Q1-TK-000001",
      "vai_tro": "nhan_vien",
      "chuc_vu": "quan_ly_co_so",
      "ma_co_so": "Q1"
    },
    "scope": { "type": "site", "ma_co_so": "Q1" },
    "permissions": ["students.read", "transfers.create"],
    "default_route": "/portal/admin-small"
  }
}
```

Ví dụ trên chỉ minh họa cấu trúc, không cấp quyền bằng chuỗi do frontend gửi. Danh sách quyền thực tế phải suy ra từ vai trò/chức vụ và được API kiểm tra lại mỗi request. Giáo viên nhận `scope.type = assigned_classes`; Admin Big nhận `scope.type = global`. Hiện chưa có `student` trong response.

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

API tự đặt `vai_tro = nhan_vien`, `chuc_vu = quan_ly_co_so`, gắn site và tạo `TaiKhoan` theo chính sách nhân bản cùng hồ sơ `NhanVien` tại Q7. Không cho client gửi `vai_tro` hoặc `chuc_vu` tùy ý. Với giáo viên, API tự đặt `vai_tro = giao_vien`, tạo `TaiKhoan` dùng chung và hồ sơ `GiaoVien` tại site được chọn.

Sau khi schema có trạng thái kích hoạt và token riêng, quy trình phải gửi liên kết đặt mật khẩu ban đầu cho email của người được tạo; Admin Big không biết hoặc gửi mật khẩu người dùng. Hiện endpoint tạo tài khoản và gửi email đều chưa được triển khai.

Đây là nhiều bước ghi (`REPLICATED-WRITE` cho `TaiKhoan`, `LOCAL` cho hồ sơ). Response cần có trạng thái xử lý theo từng chặng; chỉ trả thành công hoàn toàn khi tài khoản có hồ sơ/phạm vi dùng được. Nếu đồng bộ tài khoản thành công nhưng tạo hồ sơ site thất bại, vô hiệu hóa hoặc đưa tài khoản về trạng thái chờ xử lý có thể phục hồi; không để tài khoản hoạt động không có site/phạm vi. Kiểm tra trùng `ten_dang_nhap`/`email` trên các bản sao trước khi ghi.

### Phân công giáo viên

`PUT /api/v1/admin/teachers/{ma_giao_vien}/assignments` nhận danh sách lớp/buổi được phân công. API lấy site từ người gọi (Admin Small) hoặc xác thực site đích theo quyền (Admin Big), xác nhận giáo viên, lớp, buổi và phòng thuộc cùng CSDL site; sau đó cập nhật quan hệ lớp/buổi trong transaction `LOCAL`. Nếu một phần danh sách sai, mặc định từ chối toàn request và không lưu phần hợp lệ một phần.

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

Phần này gom toàn bộ API thu, hoàn và theo dõi học phí. Thu/hoàn tại quầy là thao tác `LOCAL` của kế toán hoặc Admin Small có quyền, tại site đang giữ `HocPhi`. Thanh toán qua cổng là luồng đề xuất riêng nếu nhóm quyết định tích hợp; không dùng trạng thái frontend thay cho trạng thái lưu tại SQL Server.

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

Client gửi `Idempotency-Key: <UUID>` cho mỗi thao tác thu/hoàn. API tự lấy site từ khoản học phí, xác thực quyền và kiểm tra số tiền dương, số dư, trạng thái khoản phí. Trong một transaction `LOCAL`, API khóa/đọc lại `HocPhi`, kiểm tra yêu cầu trùng, tạo `PhieuThu`, cập nhật `HocPhi`, lưu kết quả yêu cầu idempotency và ghi nhật ký. Cùng người gọi + cùng site + cùng endpoint + cùng khóa và cùng nội dung trả lại đúng kết quả/phiếu ban đầu; cùng khóa nhưng nội dung khác trả `409 IDEMPOTENCY_KEY_REUSED`. Nếu transaction rollback thì không phiếu nào được ghi và có thể gửi lại cùng khóa. Nếu transaction đã commit nhưng response bị mất, gửi lại cùng khóa hoặc đọc trạng thái yêu cầu sẽ lấy lại kết quả đã commit, không thu lần hai. Không xóa phiếu đã phát sinh; hoàn tiền tạo dòng `PhieuThu` loại `hoan` với khóa idempotency riêng.

Với `loai = hoan`, request phải tham chiếu `ma_phieu_goc`; API kiểm tra số đã hoàn trước đó và không cho tổng hoàn vượt số tiền thu còn có thể hoàn. Phiếu gốc được giữ nguyên. Hợp đồng hiện tại cho phép người có quyền hoàn tiền ghi nhận trực tiếp; **chưa có** quy trình đề nghị/duyệt hoàn tiền riêng. Nếu nhóm muốn bắt buộc duyệt, cần thêm trạng thái và endpoint duyệt trước khi giao diện hiển thị nút đó.

### Thanh toán qua cổng

Đây là hợp đồng đề xuất nếu nhóm tích hợp cổng thanh toán; nhà cung cấp chưa được chốt. Portal học viên và quyền cho học viên tự thanh toán vẫn cần được nhóm duyệt riêng. Cổng thanh toán là dịch vụ ngoài, không phải một site SQL Server. Nghiệp vụ khoản học phí vẫn là `LOCAL` tại CSDL của cơ sở đang giữ `HocPhi`; không tuyên bố transaction ACID bao trùm SQL Server và cổng thanh toán. Các lỗi, cách khôi phục và yêu cầu bảo mật được quy định riêng tại mục [Bài toán lỗi, phục hồi và bảo mật thanh toán](#bài-toán-lỗi-phục-hồi-và-bảo-mật-thanh-toán).

#### Endpoint và thứ tự xử lý

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

Các trạng thái đề xuất: `cho_thanh_toan` → `dang_xu_ly` → `da_thanh_toan`; kết thúc thay thế gồm `that_bai`, `da_huy`, `het_han`; trường hợp chưa thể xác minh là `can_doi_soat`. Chỉ `da_thanh_toan` mới được tính vào `HocPhi.so_tien_da_dong`. `cho_thanh_toan`, `dang_xu_ly`, `dang_yeu_cau_huy` và `can_doi_soat` không phải trạng thái đã thu tiền. Chuyển trạng thái phải hợp lệ, có thời điểm và tác nhân/sự kiện nguồn; không cho client PATCH trạng thái.

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

### Schema cần bổ sung trước khi viết code

Schema hiện tại chưa có nơi lưu lần thử thanh toán, khóa idempotency, mã callback duy nhất hoặc trạng thái chờ. Cần cập nhật `docs/DATABASE_SCHEMA.md` trước implementation, giữ mọi bảng dưới đây tại CSDL site chứa `HocPhi`, không tạo database thanh toán trung tâm:

- Thêm bảng cục bộ `YeuCauThanhToan`: khóa chính `ma_yeu_cau`; `ma_hoc_phi`; người tạo; số tiền/đơn vị tiền tệ do server xác định; provider; tham chiếu giao dịch provider; `khoa_idempotency`; hash nội dung request; trạng thái; hạn thanh toán; thời điểm tạo/cập nhật/kết thúc. Đặt unique constraint cho khóa idempotency trong phạm vi site/người gọi/endpoint và cho tham chiếu provider; chỉ cho tối đa một lượt còn mở (`cho_thanh_toan`, `dang_xu_ly`, `dang_yeu_cau_huy`, `can_doi_soat`) trên một `HocPhi`, dùng transaction/khóa hàng để chống hai yêu cầu đồng thời.
- Thêm bảng cục bộ append-only `SuKienThanhToan` với mã sự kiện provider duy nhất, mã yêu cầu, loại sự kiện, thời điểm nhận, kết quả xác minh và metadata đã lọc. Không lưu PAN/CVV, secret, token hoặc payload cổng thô; không sửa/xóa sự kiện đã ghi.
- `PhieuThu` cần liên kết duy nhất với yêu cầu thanh toán online (cột `ma_yeu_cau` nullable và unique cho bản thu online, hoặc ràng buộc tương đương) và request ledger idempotency cho thu/hoàn tại quầy. Thu/hoàn thủ công và callback thành công đều phải cập nhật `PhieuThu` + `HocPhi` + ledger/audit trong cùng transaction site.
- Quy định retention, quyền đọc trạng thái, migration/rollback an toàn và tác vụ đối soát. Migration không được tạo giao dịch giả hay thay đổi số đã thu của dữ liệu hiện hữu.

## Quản lý điểm

Request tối thiểu gồm `diem_so` trong khoảng 0–10. API xác định site từ đăng ký/lớp, kiểm tra giáo viên được phân công và loại điểm hợp lệ. Mỗi đăng ký chỉ có một dòng cho mỗi `loai_diem`; endpoint phải quy định rõ tạo mới khi chưa có điểm hay cập nhật điểm đã có, và mọi lần sửa phải ghi nhận lịch sử theo quy tắc audit của dự án.

## Chuyển cơ sở

Tạo đề nghị nhận tối thiểu `ma_hoc_vien`, `ma_co_so_dich`, `ly_do_de_nghi`. Không nhận `ma_co_so_nguon` như một giá trị đáng tin từ client; API lấy nguồn từ tài khoản Admin Small. Kiểm tra học viên hiện hành, nợ học phí, đích đang hoạt động, đích khác nguồn và không có giao dịch mở. Lưu trạng thái `cho_duyet` cùng sự kiện `de_nghi` tại nguồn; khi tạo đề nghị chưa được ghi hồ sơ đích.

Hộp thư Admin Big là `GLOBAL`: hỏi các site độc lập và gộp tại API. Duyệt/từ chối định tuyến về CSDL nguồn và ghi quyết định/sự kiện tại nguồn. Khi từ chối, cần `ly_do_tu_choi`; khi duyệt, kiểm tra lại điều kiện rồi mới giao Coordinator chạy `DISTRIBUTED-TX`. Giao dịch phải hỗ trợ trạng thái và phục hồi theo [README mục 5.5](../README.md#55-chuyển-học-viên-sang-cơ-sở-khác); không tuyên bố ACID nguyên tử xuyên hai CSDL.

## Thống kê học viên theo cơ sở

Site cụ thể chỉ được nhận từ request sau khi API kiểm tra phạm vi của người gọi. Admin Small không được yêu cầu site khác; Admin Big có thể truy vấn toàn hệ thống. Với `GLOBAL`, gộp kết quả ở API, loại bản `da_chuyen_di`, không đếm trùng trạng thái chuyển tạm thời và nêu rõ site không phản hồi.

## Gửi lặp, cập nhật đồng thời và lỗi site

- Mọi thao tác tạo/sửa kiểm tra quyền, phạm vi site và điều kiện nghiệp vụ trước khi ghi; API không dùng `DELETE` để xóa học viên, phiếu thu, điểm danh hoặc nhật ký đã phát sinh.
- Ràng buộc duy nhất hiện có giúp chặn một số thao tác trùng: `DangKy(ma_hoc_vien, ma_lop)`, `Diem(ma_dang_ky, loai_diem)`, `DiemDanh(ma_buoi, ma_dang_ky)`, và `GiaoDichChuyenCoSo.khoa_chong_lap`. Khi nhận lại cùng thao tác hợp lệ, API nên trả kết quả cũ thay vì tạo thêm nghiệp vụ.
- Thu/hoàn tại quầy phải chống gửi lại request sau timeout bằng khóa idempotency lưu bền vững và ghi cùng transaction với `PhieuThu`/`HocPhi`; hiện schema chưa có khóa hoặc request ledger.
- Thanh toán trực tuyến phải lưu `YeuCauThanhToan` và sự kiện callback ở đúng CSDL site, tra cứu được sau reload/đăng nhập lại, xử lý callback lặp idempotent và khóa lượt mới khi kết quả cổng chưa rõ. Hiện schema chưa có các bảng/trạng thái này; xem mục “Thanh toán trực tuyến: reload, thoát trang, timeout và callback lặp”. Không dựa vào trạng thái frontend/localStorage để xác định đã thu tiền.
- Tạo tài khoản nội bộ vừa ghi bản sao `TaiKhoan` vừa tạo hồ sơ site. API phải lưu đủ tiến trình để tiếp tục hoặc vô hiệu hóa an toàn nếu một chặng lỗi; không tuyên bố transaction ACID xuyên site.
- Giao dịch chuyển dùng `GiaoDichChuyenCoSo.khoa_chong_lap` và trạng thái Coordinator trong CSDL nguồn. Nếu site đích đã commit hồ sơ, phục hồi phải tiến về phía trước theo README mục 5.5.
- `GLOBAL` không trả thành công toàn phần khi site bị lỗi: giữ kết quả từng site, đặt `complete: false`, liệt kê `missing_sites`; các thao tác yêu cầu đủ site như `REPLICATED-WRITE` phải báo thất bại/chờ đối soát theo chính sách, không giả thành công.
- Ghi `NhatKyHeThong` cùng giao dịch cục bộ với thao tác quan trọng. Log chỉ chứa định danh và dữ liệu nghiệp vụ tối thiểu; không ghi mật khẩu, hash mật khẩu, token, cookie, header xác thực hay thông tin kết nối.

`NhatKyDongBo` trong schema hiện là log append-only theo site đích, với trạng thái thành công/thất bại; chỉ riêng log này chưa chứng minh API lưu được toàn bộ tiến trình replication để retry an toàn sau timeout chưa rõ. Trước khi bật `REPLICATED-WRITE`, chốt nơi lưu mã thao tác, phiên bản/thay đổi cần áp dụng và trạng thái bền vững của từng site; dùng log hiện có nếu đủ bảo đảm hoặc cập nhật schema/script với outbox/bảng tiến trình theo quyết định nhóm. Không suy diễn “retry an toàn” chỉ từ việc có bảng log.

## Kiểm thử hợp đồng API cần có

| Nhóm | Kịch bản phải kiểm tra |
|---|---|
| Concurrency bắt buộc YC-05 | TC-CON-01: hai phiên độc lập, hai học viên khác nhau cùng đăng ký lớp còn một chỗ; ghi cách tạo cạnh tranh và dữ liệu cuối, đúng một yêu cầu thành công. Không thay bằng test thanh toán online còn ngoài phạm vi |
| Replication YC-03 và đồng bộ YC-07 | TC-REP-01 truyền thay đổi danh mục; TC-SYNC-01 gây lỗi trước ghi và giữa ghi, kết nối lại rồi đối soát/retry không trùng; đọc từng bản sao |
| Distributed transaction YC-04 | TC-DTX-01 phải có thay đổi thật ở DB nguồn/đích sau duyệt, trạng thái trước–sau và phục hồi; transaction cục bộ đăng ký không thay thế |
| Phân quyền | Admin Small gọi site khác bị `403`; giáo viên gọi lớp không được phân công bị từ chối; Admin Big mới được duyệt chuyển |
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
| Chuyển cơ sở | Admin Small tạo đề nghị ở nguồn; Admin Big duyệt/từ chối; thử lỗi trước/sau khi đích commit và chạy phục hồi |
| Tài khoản | Mật khẩu sai dùng lỗi chung; tài khoản bị khóa không tạo phiên; reset token hết hạn/đã dùng bị từ chối |
| Học viên | Cho tới khi portal được duyệt, mọi đăng nhập/route học viên bị từ chối; sau khi duyệt phải kiểm tra chỉ đọc đúng hồ sơ liên kết và theo đúng site hiện hành |
| Validation | Gửi thiếu trường, sai kiểu, sai enum, ngày kết thúc trước ngày bắt đầu, ngày ngoài phạm vi và body quá lớn; API từ chối mà không ghi DB |
| SQL injection | Thử payload SQL trên login, search, filter, sort và các endpoint ghi; không được mở rộng kết quả, vượt quyền hoặc thay đổi bảng |
| CRUD thực tế | Với từng tài nguyên được phép: gọi create/read/update trên SQL Server test, đọc lại để xác nhận dữ liệu đã lưu đúng; thử sai quyền và sai site |
| Xóa và lưu lịch sử | Chỉ xóa dữ liệu nháp chưa được tham chiếu nếu nghiệp vụ cho phép; hóa đơn/phiếu thu, điểm danh, giao dịch và nhật ký dùng hủy/đóng/điều chỉnh, không hard-delete |
| Chống spam | Kiểm tra rate limit từng form, `429`/`Retry-After`, CAPTCHA sau ngưỡng và response không tiết lộ tài khoản |
| Ảnh | Kiểm tra signed upload Cloudinary, file MIME giả, file quá lớn, intent hết hạn, user khác dùng public ID, gỡ ảnh còn tham chiếu và không phát sinh file trong source |
| Hiệu năng | Đo p50/p95 theo millisecond với dữ liệu có kích thước ghi rõ; kiểm tra LOCAL, GLOBAL, login và upload riêng |

### Điều kiện kiểm tra create/read/update/delete

Kịch bản phải chạy trên CSDL SQL Server test riêng theo site, không chỉ mock repository. Mỗi thao tác thành công phải được đọc lại từ đúng site để chứng minh dữ liệu đã commit; thao tác sai phải kiểm tra không để lại bản ghi dở dang. Với `REPLICATED-WRITE`, đọc đối chiếu bản sao từng site; với `GLOBAL`, kiểm tra dữ liệu được gộp ở API chứ không ghi vào một CSDL trung tâm.

Không ép mọi bảng có nút xóa. `HocVien` giữ lịch sử chuyển; `PhieuThu`, `DiemDanh`, `LichSuChuyenCoSo` và `NhatKyHeThong` không hard-delete. Nếu cần xóa tài khoản/tài nguyên chưa sử dụng, dùng trạng thái `vo_hieu`/`da_huy` hoặc endpoint delete có kiểm tra tham chiếu, quyền, nhật ký và phục hồi phù hợp. Test delete phải chứng minh không xóa nhầm dữ liệu dẫn xuất/lịch sử.

Với mọi route, tối thiểu kiểm tra: thành công; request sai; unauthenticated; role sai; site sai; bản ghi không tồn tại; bản ghi bị cập nhật/xóa song song; site SQL Server mất kết nối; retry cùng request; transaction rollback. Ghi lệnh/kịch bản và kết quả trong PR hoặc tài liệu test; nếu endpoint chưa được cài thì ghi `Chưa chạy — chưa có implementation`, không tự ghi là pass.

## Mục tiêu hiệu năng API và tối ưu truy vấn

Các con số dưới đây là mục tiêu nghiệm thu ban đầu, đo ở API server trong môi trường test được ghi rõ, không phải cam kết tốc độ production. Dùng millisecond (`ms`) và báo p50/p95, kích thước dữ liệu, số site đang hoạt động, số request đồng thời và cấu hình máy.

| Nhóm request | Mục tiêu p95 đề xuất |
|---|---:|
| Đăng nhập và `GET /auth/me` | ≤ 500 ms |
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

## Các điểm schema chưa khớp cần xử lý trước khi triển khai

1. Portal học viên còn là đề xuất. Nếu nhóm duyệt, `TaiKhoan.vai_tro`, quan hệ tài khoản–`HocVien`, quy tắc chuyển quan hệ sang site đích, seed/migration và kiểm thử quyền phải được cập nhật trong `docs/DATABASE_SCHEMA.md` trước khi bật các route `/student/me/...`.
2. `specs/api.md` đề xuất API quản lý Admin Small, giáo viên và phân công. Các route này chưa đồng nghĩa code đã tồn tại; cần xác nhận trạng thái triển khai và migration/permission trước khi frontend gọi thật.
3. `PhieuThu` cần khóa idempotency bền vững (hoặc request ledger tại site) cho thu/hoàn tại quầy. Nếu tích hợp cổng trực tuyến, cần thêm `YeuCauThanhToan`, `SuKienThanhToan`, liên kết unique từ phiếu thu tới yêu cầu và trạng thái đối soát theo mục thanh toán; tất cả đặt tại CSDL site chứa `HocPhi`, không tạo DB thanh toán trung tâm. Cập nhật `docs/DATABASE_SCHEMA.md`, phân loại/định vị các bảng và migration trước khi triển khai API.
4. Chốt cách lưu phiên/CSRF, quy tắc pagination, danh sách lỗi nghiệp vụ và cơ chế lưu tiến trình tạo tài khoản nhiều site. Khi chốt phải sửa mục này và ví dụ response trước khi viết client/server.
5. Schema chưa có metadata Cloudinary. Bổ sung bảng/quan hệ metadata và quy tắc phân mảnh/nhân bản trước khi gắn ảnh vào giao diện; binary chỉ ở Cloudinary.
6. Chốt storage bền vững cho giới hạn/rate limit khi có nhiều worker và đặt ngưỡng bcrypt theo benchmark; không lưu bộ đếm chỉ trong memory nếu chạy nhiều instance.
7. OAuth Google/Facebook đã có thiết kế dùng `TaiKhoan.google_subject` và `TaiKhoan.facebook_subject`; database cũ chạy `db/27_move_oauth_identity_to_account.sql` sau khi có `Logs`. Trước khi bật route phải chốt cách lưu/thu hồi phiên, callback HTTPS, tạo OAuth apps và triển khai/test flow liên kết trong `src/api`. OAuth credentials chỉ điền ở `src/api/.env`, không commit.
8. YC-03/YC-07 cần phương pháp replication và tiến trình/ACK/phiên bản cho phục hồi bản sao; YC-04 cần chốt cơ chế đáp ứng tiêu chí distributed transaction; YC-05 cần cơ chế bảo vệ chỗ cuối và kiểm thử hai phiên. Nếu cần thêm trạng thái/bảng, phải cập nhật schema/migration trước; không tự dùng DB trung tâm hoặc coi các mục bắt buộc là tùy chọn.
