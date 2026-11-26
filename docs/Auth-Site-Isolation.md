# Xác thực khi site mất kết nối và tài khoản học viên miễn phí

Chốt ngày 21/11/2026 theo yêu cầu chủ dự án: cho tự đăng ký tài khoản học viên miễn phí trước khi mua khóa học; tách lỗi site nghiệp vụ khỏi việc xác thực người dùng ở site khác. Chính sách này thay nội dung cũ yêu cầu đọc/đối chiếu mọi bản sao tài khoản trước mỗi lần đăng nhập. Thanh toán SePay và kiểm chứng provider OAuth thật không được mở rộng trong thay đổi này.

## Phạm vi và giới hạn

`AUTH_SESSION_SITE_CODE` chọn bản `TaiKhoan` có thẩm quyền cùng kho phiên, khóa đăng nhập và hàng đợi; môi trường hiện dùng **Q1 trên máy chạy API**, thay cho Q7. Chỉ đọc bản có thẩm quyền để kiểm tra mật khẩu, khóa tài khoản và phiên bản; không dùng mật khẩu từ bản sao cũ khi mất kết nối. Dữ liệu lớp, học viên, học phí, điểm và chứng từ vẫn phân mảnh theo site, không gom về Q1.

**Đăng ký chỉ tạo tài khoản (bước 2, `SELF_REGISTRATION_ACCOUNT_ONLY`, mặc định tắt):** tạo `TaiKhoan` vai trò `nguoi_dung`, `ma_co_so` rỗng, không tạo `HocVien`. Email được giữ chỗ trong `DatChoEmailHocVien` dưới site authority và `ma_hoc_vien` rỗng. Trigger/worker vẫn nhân bản tài khoản tới mọi site hoạt động; 5 cột hồ sơ cơ bản chỉ được sao chép cho vai trò `nguoi_dung`, nên site chưa chạy migration 48 vẫn nhận các tài khoản khác bình thường nhưng sẽ lỗi (nằm lại hàng đợi) với tài khoản `nguoi_dung`. Chỉ bật cờ sau khi mọi site đã chạy migration 48 và phần đăng nhập hỗ trợ vai trò này (bước 3). Khi tư vấn tạo hồ sơ học viên cho email đã giữ chỗ dưới authority, luồng gắn tài khoản (bước 5) phải xử lý bản giữ chỗ này.

| Tình huống | Hành vi |
|---|---|
| Q7 không truy cập được, Q1/TD và API còn chạy | Người dùng Q1/TD đăng nhập bằng kho xác thực Q1 và hồ sơ ở cơ sở mình. Không mở kết nối Q7 để đối chiếu mật khẩu. |
| TD không truy cập được | Người dùng Q1/Q7 tiếp tục nếu kho xác thực và site sở hữu hồ sơ còn chạy. |
| Site sở hữu hồ sơ mất | Không giả hồ sơ, lớp, học phí hay quyền truy cập; thao tác cần site đó trả lỗi dịch vụ. |
| Q1/kho xác thực hoặc API mất | Đăng nhập và xác thực phiên vẫn gián đoạn. Thay đổi này **chưa phải HA/failover** cho kho xác thực/API. |
| Báo cáo toàn cục thiếu site | Giữ hợp đồng `complete`/`missing_sites` của từng báo cáo; không coi số liệu thiếu là toàn bộ. |

Hồ sơ học viên được tìm ở site ghi trên tài khoản trước. Nếu không còn hồ sơ hiện hành ở đó do chuyển cơ sở, mới tìm các mảnh còn lại; hồ sơ đích đang staged không cấp quyền. Không tự chuyển học viên sang một site còn sống.

## Ghi tài khoản và phục hồi

Tạo Admin Small, nhân viên, giáo viên, cấp tài khoản học viên và tự đăng ký chỉ đòi hỏi kho xác thực cùng site sở hữu hồ sơ. Namespace email/username được giữ bằng khóa transaction tại kho xác thực. Commit tại các site vẫn độc lập; không tuyên bố 2PC/ACID xuyên site. Luồng tự đăng ký bị gián đoạn sau commit cục bộ chỉ được tiếp tục nếu mật khẩu khớp tài khoản cục bộ đã tạo, không tự nhận hồ sơ có sẵn.

Migration `45_account_replication_queue.sql` chỉ chạy tại kho xác thực. Trigger trên `TaiKhoan` ghi `DongBoTaiKhoan` cùng transaction với thay đổi tài khoản; hàng đợi chỉ chứa mã tài khoản/site, không chứa mật khẩu hay bản sao hash. Worker lấy snapshot **hiện tại**, ghi bản sao, rồi xác nhận đúng thế hệ sự kiện. Lỗi giữa commit đích và xác nhận được thử lại, không tạo trùng tài khoản. Replica có phiên bản mới hơn hoặc thông tin bảo mật khác ở cùng phiên bản bị giữ lại để đối soát, không tự ghi đè.

Worker kiểm tra kết nối đích trước khi khóa tài khoản nguồn, thử lại lỗi sau 10 giây và quét đối soát lại mỗi 60 giây. Quét này có thể bù bản sao tài khoản cũ sau khi Subscriber được restore; không khôi phục dữ liệu nghiệp vụ chỉ tồn tại ở mảnh bị mất. Xóa bản sao có lịch sử/FK không thực hiện được vẫn nằm trong hàng đợi để kiểm tra. Lỗi job đổi mật khẩu chỉ chặn tài khoản liên quan; cập nhật mật khẩu có hiệu lực tại kho xác thực và được chuyển sang các replica qua cùng hàng đợi. Kho phiên kiểm tra phiên bản hiện tại để vô hiệu phiên cũ.

Phản hồi cấp tài khoản trả `replication_complete` và `replication_pending_sites`. `201` xác nhận tài khoản/hồ sơ đã tạo tại các nơi bắt buộc, không khẳng định tất cả bản sao đã đồng bộ. UI thông báo các site còn chờ. Liên kết Google/Facebook và Admin Big tự sửa email/tên đăng nhập/slug cũng chỉ ghi authority, tăng `phien_ban` để worker ghi đè bản sao cũ (không còn ghi từng site rồi kẹt `AccountReplicaConflict` khi lỗi giữa chừng), giữ các phiên đang hiệu lực. Ảnh đại diện tài khoản (Admin, Admin Small, giáo viên, nhân viên) cũng đọc/ghi metadata tại authority, ghi biên nhận idempotent trong `Logs` của authority và để worker chép cột ảnh sang bản sao; site không liên quan offline không chặn xem hay đổi ảnh. Ảnh hồ sơ học viên vẫn là metadata `HocVien` tại site sở hữu. Các luồng xóa tài khoản và chuyển cơ sở có hợp đồng riêng; không suy ra chúng đều hoạt động khi site bắt buộc mất kết nối.

## Tự đăng ký miễn phí và ghi danh

- `GET /api/v1/auth/register/`: danh sách cơ sở hoạt động từ danh mục tại kho xác thực và cờ `registration_ready`.
- `POST /api/v1/auth/register/`: họ tên, email, cơ sở dự định học, mật khẩu và xác nhận. CSRF bắt buộc; giới hạn 5 lần/giờ/IP theo throttle của API; mật khẩu tối thiểu 12 ký tự, được kiểm tra bằng validators và băm bằng hasher cấu hình. Từ chối trường thừa như role/phạm vi quyền. Server luôn tạo `hoc_vien`, không cấp vai trò nhân viên/Admin.
- Tạo `TaiKhoan`, `HocVien` và nhật ký; không tạo `DangKy`/`HocPhi`, không gửi mật khẩu qua email. Chưa có bước xác minh email trong thay đổi này; không dùng email khai báo để nhận hồ sơ học viên/guest có sẵn. Tài khoản/hồ sơ đã có được hướng dẫn đăng nhập hoặc liên hệ trung tâm.
- Trang `/register` có liên kết từ `/login`; sau tạo thành công hướng sang đăng nhập. Portal trống hướng sang xem khóa học.
- Học viên có thể đổi mật khẩu sau đăng nhập và dùng luồng OTP khôi phục mật khẩu hiện có, kể cả chưa mua khóa học. Phản hồi yêu cầu OTP không tiết lộ tài khoản có tồn tại; gửi email thật vẫn cần SMTP hoạt động.
- `POST /api/v1/public/enrollments/` giữ luồng khách chưa có tài khoản. Với cookie phiên học viên hợp lệ, API lấy mã học viên/site từ phiên, kiểm tra site được chọn và ghi danh vào chính hồ sơ đó; các trường liên hệ gửi lên không chọn được hồ sơ khác. Chọn lớp tại site khác yêu cầu nghiệp vụ chuyển cơ sở.

`DatChoEmailHocVien` là directory kỹ thuật chứa HMAC email, site và mã hồ sơ; không chứa hồ sơ nghiệp vụ. `TrangThaiKhoEmail` chặn mở đăng ký mới trước khi đã đọc đủ các mảnh lần đầu. Chạy bootstrap khi mọi site hoạt động, không có giao dịch chuyển cơ sở đang chạy và đã tạm dừng ghi hồ sơ. Email trùng giữa các hồ sơ phải đối soát trước. Sau bootstrap, các lần giữ email chỉ đọc directory và site đích; site không liên quan có thể offline. Reservation đã commit nhưng thao tác bị lỗi được giữ lại để tránh giải phóng nhầm sau commit từ xa chưa rõ kết quả. Không tự tái sử dụng email đã đổi/xóa; cần đối soát trước khi giải phóng. Đổi `SECRET_KEY` cần kế hoạch dựng lại directory trong thời gian dừng ghi, vì HMAC phụ thuộc khóa đó.

## Triển khai

1. Đối chiếu bản tài khoản, phiên bản, trạng thái và job mật khẩu tại từng site; sao lưu cấu hình trước khi đổi authority. Không đổi authority chỉ để đọc một bản sao cũ khi kho đang chạy gặp lỗi. Phiên tại kho cũ không được tự chuyển; người dùng đăng nhập lại.
2. Đảm bảo schema tài khoản đủ cột, gồm migration 27 cho OAuth tại mọi Subscriber. Chạy migration 45 trên database authority; API role cần quyền trên các bảng kỹ thuật (role trong script 05 cấp theo schema).
3. Cấu hình `AUTH_SESSION_SITE_CODE=Q1` cho API và worker. Không đổi `MONHOC_PUBLISHER_SITE_CODE` theo biến này.
4. Khi đủ site online và đã dừng ghi hồ sơ/chuyển cơ sở: chạy `.\.venv\Scripts\python.exe manage.py seed_student_emails` từ `src/api`. Lỗi đọc bất kỳ site nào không được bật `san_sang`; không sửa cờ bằng tay. Đây là bước khởi tạo **một lần**, không phải điều kiện phải bật mọi máy trong mỗi lần đăng ký.
   Khi chưa thể bật đủ site, người vận hành có thể chủ động chạy `manage.py seed_student_emails --allow-missing-sites`: site mất kết nối (trừ authority) bị bỏ qua và lệnh in danh sách site đã bỏ qua. Rủi ro: email chỉ tồn tại ở site bị bỏ qua không được giữ chỗ nên có thể bị đăng ký trùng; khi site trở lại hãy chạy lại lệnh không có tùy chọn hoặc đối soát thủ công. Mặc định lệnh vẫn đòi đủ site.
5. Khởi động API cùng worker bằng `src/api/run-local.ps1`. Nếu chạy API bằng lệnh khác, phải chạy thêm `sync_accounts` và `sync_courses` trong các tiến trình được giám sát. Worker cần chạy để tự đồng bộ tài khoản/khóa học sau phục hồi; `--once` chỉ phục vụ kiểm tra một lượt. Môi trường production phải giám sát/khởi động lại API và worker bằng công cụ vận hành hiện có.
6. Khi site khôi phục: kiểm tra SQL/ZeroTier/schema, để worker tiếp tục; đọc `DongBoTaiKhoan` theo site, `so_lan_thu` và `loi`. `AccountReplicaConflict` cần đối soát dữ liệu và nguồn có thẩm quyền trước khi xử lý; không tắt kiểm tra xung đột.

## Bằng chứng ngày 21/11/2026

Kiểm tra SQL thật chỉ kết nối được **Q1**; Q7 và TD không truy cập được và người dùng xác nhận chưa bật được hai máy. Migration 45 đã áp dụng Q1, cấu hình xác thực đã đổi Q1, directory chưa được bật do chưa đối soát được dữ liệu hai site còn lại. Giao diện đăng ký báo tạm ngưng và khóa gửi khi `registration_ready=false`.

Đã chạy kiểm tra SQL Q1 trong transaction hoàn tác: tạo tài khoản miễn phí, đăng nhập, đọc phiên, đổi mật khẩu, vô hiệu phiên/mật khẩu cũ, thấy Q7/TD còn chờ, không có đăng ký lớp/học phí. Không giữ lại dữ liệu QA. Bài kiểm tra tự động dùng các database SQLite commit độc lập để kiểm tra mất đích/phục hồi, lỗi ACK, retry lấy mật khẩu mới, giữ replica mới hơn; các kiểm tra dịch vụ/API xác nhận CSRF, role injection, profile riêng, bootstrap fail-closed và không nhận hồ sơ guest cũ.

Chưa có bằng chứng đồng bộ/phục hồi trên **ba SQL Server thật** của thay đổi này. Chưa kiểm chứng HA cho authority/API. Sau khi Q7/TD được bật, còn phải đối soát dữ liệu, áp dụng schema thiếu, bootstrap email và chạy bài thử end-to-end ba máy trước khi tuyên bố triển khai đầy đủ.

Kết quả kiểm tra source: Django `manage.py test core` **179/179**; frontend typecheck và production build qua; lint không có lỗi, còn một cảnh báo ảnh `<img>` có sẵn ở `StudentTuitionPanel.tsx`. Trình duyệt desktop đã kiểm tra `/register`, lựa chọn cơ sở, thông báo tạm ngưng/khóa gửi và điều hướng hai chiều với `/login`. HTTP thật: phiên không cookie `204`, trao đổi CSRF thành công, định danh thử không tồn tại trả `401` (lượt đo khoảng 5,4 giây), GET đăng ký `200` với `registration_ready=false`. Worker đang chạy nền trong phiên local; 7 tài khoản chờ Q7 và 7 tài khoản chờ TD, lỗi kết nối được giữ lại. Chưa kiểm tra mobile, đăng ký qua browser ở trạng thái đã bootstrap, OAuth provider, email thật hoặc thanh toán.
