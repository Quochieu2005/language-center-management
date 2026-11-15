# Trạng thái triển khai theo source

Đối chiếu source và tài liệu ngày **2026-11-16**. Tài liệu này ghi nhận code hiện có trong repo; nó không xác nhận API/SQL Server đang chạy, không xác nhận một tính năng đã được nhóm duyệt phạm vi, và không thay thế bằng chứng nghiệm thu môn học.

## Kiến trúc đang được triển khai

- Frontend Next.js ở `src/web`; Django REST Framework ở `src/api`; SQL Server là DBMS.
- Mỗi site dùng một database và alias/kết nối riêng. Site Router lấy danh sách site hoạt động từ `CoSo` rồi đối chiếu `SITE_DATABASES_JSON`; `DATABASES['default']` dùng dummy backend.
- Ba site ban đầu là Q1, Q7 và TD. Code không được giới hạn vòng lặp ở ba site. Có thể đặt ba database trên cùng một SQL Server instance trong môi trường demo mà vẫn giữ ba database riêng.
- Không có database nghiệp vụ trung tâm, khóa ngoại xuyên site hoặc JOIN xuyên site. Global Query đọc từng database và tổng hợp tại API.
- `AUTH_SESSION_SITE_CODE` chọn một database site để giữ trạng thái kỹ thuật có thể thu hồi như phiên đăng nhập và tiến trình khôi phục xác thực. Database này không phải kho tổng hợp dữ liệu nghiệp vụ; việc site giữ trạng thái kỹ thuật không thay đổi ranh giới ba database nghiệp vụ.

## Trạng thái theo chức năng

| Chức năng | Trạng thái source | Phân loại/phạm vi | Bằng chứng còn thiếu |
|---|---|---|---|
| Định tuyến site và phân mảnh nghiệp vụ | Có Site Router, cấu hình alias theo site, schema/migration có ràng buộc site; các bảng học viên/lớp và bảng con được lưu theo site | `LOCAL`; bảng con phân mảnh dẫn xuất theo bảng cha | Chạy đối chiếu phân mảnh trên các database hiện dùng, chứng minh đầy đủ, tái thiết và không giao nhau bằng dữ liệu/kết quả TC-SITE-01, TC-FRAG-01 |
| Danh mục dùng chung | Có API/service ghi `MonHoc` và `KhoaHoc` qua Coordinator; seed chỉ là nạp ban đầu. Luồng YC-03 tối thiểu được chọn là `MonHoc` | `REPLICATED-WRITE`; bản sao nằm trong từng database site | TC-REP-01 cần lưu thay đổi thật và đọc lại từng bản sao; TC-SYNC-01 còn cần outage/recovery trên SQL Server thật, retry và đối soát |
| Blog và CMS Admin Big | Có API public đọc danh mục/slug; route `/admin/blog` cho Admin Big nối API liệt kê, tạo, sửa, xóa danh mục/bài; hiển thị trạng thái site và giữ thao tác retry cùng `Idempotency-Key`; trang public vẫn dùng nội dung tĩnh | Public `GLOBAL`; CMS `REPLICATED-WRITE` với transaction riêng từng site, không phải ACID xuyên database; seed migration 36 chỉ là dữ liệu khởi tạo | Chạy migration trên từng site; kiểm tra phân quyền, CRUD, lỗi một site, retry/đối soát và đọc lại từng bản sao trên SQL Server thật; chưa có bằng chứng TC-REP-01/TC-SYNC-01 |
| Quản lý/danh sách cơ sở | Site Router đọc `CoSo`; chưa có API CRUD `CoSo` hoặc route công khai đọc danh sách cơ sở. `/branches` hiện hiển thị trạng thái dữ liệu chưa khả dụng | `CoSo` được phân loại là replicated trong schema, nhưng fan-out ghi runtime còn thiếu | Chốt luồng quản trị/danh sách cơ sở và bổ sung fan-out/đối chiếu theo schema trước khi tuyên bố cơ sở mới được provision tự động |
| Đăng ký, mở lớp, xếp lớp, thu tại quầy | Có route, service và transaction cục bộ; đăng ký khóa học khóa học viên/lớp, kiểm tra sức chứa và ghi các bảng liên quan cùng transaction | `LOCAL` tại site sở hữu hồ sơ/lớp | Chạy nghiệp vụ trên dữ liệu kiểm thử của các site; concurrency hai phiên tranh chỗ cuối vẫn chưa có bằng chứng chấp nhận |
| Điểm danh và quản lý điểm | Có route/service site-local; kiểm tra giáo viên/lớp được phân công và ghi nhật ký/lịch sử điểm theo luồng hiện có | `LOCAL` | Kiểm tra quyền và dữ liệu trên từng site trong môi trường chạy; chưa xem sự tồn tại của code là bằng chứng demo |
| Chuyển cơ sở | Có đề nghị tại nguồn, quyết định Admin Big ghi tại nguồn, Coordinator xử lý nguồn/đích và route retry; sau khi đích commit thì phục hồi tiến về phía trước | `LOCAL` → `GLOBAL` → `DISTRIBUTED-TX` dùng nhiều transaction cục bộ | TC-DTX-01 còn cần fault injection trước/sau commit đích, trạng thái hai site và retry trên SQL Server thật. Không có cam kết ACID nguyên tử xuyên database, MSDTC hoặc 2PC |
| Thống kê học viên theo site | Có Global Query hỏi site riêng, tổng hợp ở API, tính bản `dang_hoc` và trả thông tin site thiếu | `GLOBAL` | Tài liệu ghi từng gọi API khi ba site sẵn sàng; cần lưu đối chiếu dữ liệu từng site và thử một site mất kết nối để hoàn tất TC-DQ-01 |
| Đăng nhập, phiên, đổi mật khẩu | Có đăng nhập cookie, phiên có thể thu hồi, idle timeout 3600 giây, đổi mật khẩu và OTP reset có giới hạn; trạng thái kỹ thuật dùng database được cấu hình | Đọc/đối chiếu tài khoản nhiều site; cập nhật bản sao theo service hiện có | Kiểm tra cấu hình, SMTP và hành vi end-to-end trong môi trường thật; OTP reset hiện hết hạn sau 120 giây theo cấu hình mặc định |
| OAuth Google/Facebook | Có start/callback, state, kiểm tra provider và luồng liên kết cho tài khoản học viên | Đọc subject theo các database site; ghi subject tới bản sao `TaiKhoan` | Chưa có bằng chứng dùng OAuth app thật; credentials/callback còn phụ thuộc cấu hình môi trường |
| Hồ sơ học viên/portal và tài khoản học viên | Có schema, API cấp tài khoản, API hồ sơ/đăng ký/lịch/học phí/điểm và giao diện `/student` | Tài khoản được nhân bản; hồ sơ và dữ liệu học viên nằm tại site hiện hành | Đây là code có trong repo nhưng **chưa được coi là phạm vi môn học đã duyệt** nếu nhóm chưa cập nhật quyết định phạm vi ở README, FS, schema, API và UI |
| Thanh toán học phí SePay | Có schema `YeuCauThanhToan`/`SuKienThanhToan`, API tạo yêu cầu, truy vấn trạng thái và webhook xác minh | `LOCAL` tại database chứa `HocPhi`; không phải giao dịch xuyên DB/cổng | `SEPAY_ENABLED=false` mặc định; chưa có kiểm chứng với tài khoản/merchant/webhook thật. Code tồn tại không tự duyệt portal hay thanh toán online vào phạm vi đồ án |
| Ảnh đại diện | Có upload intent/hoàn tất Cloudinary cho tài khoản Admin, Admin Small, giáo viên và nhân viên mới; metadata `avatar_public_id`/`avatar_secure_url` ở `TaiKhoan` | `REPLICATED-WRITE` cùng tài khoản; metadata nằm trong bản `TaiKhoan` tại từng site | Chưa có bằng chứng upload/đối soát trên Cloudinary thật; không có bảng `MediaAsset` tổng quát |
| Nhân viên, thông báo, nhật ký | Nhân viên có GET danh sách/chi tiết, POST, PATCH hồ sơ/ngưng tài khoản, POST gửi mật khẩu theo thao tác người quản lý, DELETE vĩnh viễn và upload avatar ban đầu; chức vụ `xep_lop` được gộp vào `tu_van` bằng migration 37 | Hồ sơ và trạng thái gửi mật khẩu `LOCAL`; tạo/xóa tài khoản, ngưng đăng nhập, ảnh và thu hồi phiên theo `REPLICATED-WRITE`; thông báo Admin Big ghi theo từng site | Tạo tài khoản không tự gửi mật khẩu; `sent`/`unknown`/`changed` khóa gửi lại, chỉ SMTP xác nhận thất bại mới cho thử lại; status chỉ chuyển `active` → `inactive`; DELETE xóa bản sao tài khoản, giữ hồ sơ nếu có phiếu thu; cần kiểm tra quyền, SMTP, mất kết nối, retry và đối chiếu nhiều site tại môi trường chạy |

## Phân biệt code và bằng chứng môn học

| Mã kiểm chứng | Trạng thái được ghi trong tài liệu hiện có |
|---|---|
| TC-SITE-01 / TC-FRAG-01 | Schema và script hỗ trợ; phải lưu kết quả truy vấn từng database để chứng minh phân mảnh, không suy ra đạt từ ba DB |
| TC-REP-01 | Có luồng `MonHoc` và kiểm tra retry trong môi trường rollback; cần demo thay đổi được giữ và đọc ở từng bản sao |
| TC-SYNC-01 | Chưa có outage/recovery SQL Server thật, khôi phục kết nối, retry và đối soát |
| TC-DTX-01 | Có luồng đề nghị/duyệt/Coordinator/retry; chưa có fault injection thật trước và sau commit đích |
| TC-CON-01 | Có khóa/transaction bảo vệ sức chứa trong source; chưa chạy hai phiên SQL Server đồng thời tranh chỗ cuối |
| TC-DQ-01 | Có ghi nhận API trả kết quả khi các site sẵn sàng; còn thiếu bằng chứng dữ liệu đối chiếu và trường hợp một site không phản hồi |

Đây là tình trạng đọc source/tài liệu, không phải lần chạy kiểm thử mới. Chỉ đánh dấu đạt sau khi lưu điều kiện đầu, site/bảng, lệnh hoặc request, kết quả trước/sau và log/ảnh không chứa bí mật theo [mẫu kiểm chứng](QLTTNN-Yeu-Cau-Chung-Va-Kiem-Chung.md).

## Quyết định phạm vi cần giữ rõ

- Đăng ký khóa học công khai là luồng tuyển sinh, không đồng nghĩa với đăng ký tài khoản công khai.
- Portal/tài khoản học viên và thanh toán online có code trong repo. Theo quy tắc dự án, chúng chỉ trở thành phạm vi đã duyệt sau khi nhóm thống nhất và cập nhật README, FS, schema, API spec và UI spec đồng bộ.
- Thanh toán online hiện là triển khai riêng cho SePay; không mô tả như một cổng thanh toán đã chạy thật khi chưa cấu hình `SEPAY_ENABLED`, merchant, HTTPS webhook và kiểm thử giao dịch thật.
- Chuyển cơ sở dùng Coordinator với các transaction cục bộ và phục hồi tiến về phía trước sau khi đích commit. Không mô tả là ACID nguyên tử xuyên CSDL, MSDTC hoặc 2PC khi chưa cấu hình và kiểm chứng.

## Source of truth

- Route API: [`src/api/core/urls.py`](../src/api/core/urls.py)
- Site Router/cấu hình DB: [`src/api/core/sites/connections.py`](../src/api/core/sites/connections.py), [`src/api/config/settings.py`](../src/api/config/settings.py)
- Schema khởi tạo và migration: [`db/`](../db/README.md), [`docs/DATABASE_SCHEMA.md`](DATABASE_SCHEMA.md)
- Yêu cầu và bằng chứng môn học: [`docs/QLTTNN-Yeu-Cau-Chung-Va-Kiem-Chung.md`](QLTTNN-Yeu-Cau-Chung-Va-Kiem-Chung.md)
- Luồng nghiệp vụ và các quyết định phân tán: [`README.md`](../README.md), [`fs/Functional-Specification.md`](../fs/Functional-Specification.md), [`specs/api.md`](../specs/api.md), [`specs/ui-ux.md`](../specs/ui-ux.md)
