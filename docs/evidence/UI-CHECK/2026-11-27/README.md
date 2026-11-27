# Kiểm tra giao diện admin với API thật (27/11/2026)

Khác bản 26/11 (API giả), lần này giao diện Next.js gọi **API Django thật** chạy trên hai database tạm `QLTTNN_EVA` (authority) và `QLTTNN_EVB`, đăng nhập bằng tài khoản `admin_big` thật (mật khẩu truyền qua biến môi trường `SCRATCH_ADMIN_PASSWORD`, không nằm trong file). Không đụng Q1, Q7, TD; database tạm đã xóa sau khi chạy. Dữ liệu mẫu: 9 học viên có đăng ký ở hai site, từ fixture của `docs/evidence/scripts`.

Cách chạy: web ở `localhost:3001`, API tạm ở `localhost:8011`; kịch bản Playwright chuyển hướng các yêu cầu `/api/v1` sang API tạm. Thư gửi tài khoản đi qua một máy chủ SMTP giả ở máy cục bộ (hệ thống từ chối cấp tài khoản nếu không dùng SMTP thật hoặc giả, nên không dùng được backend console).

## Kết quả

| Kịch bản | Kết quả |
|---|---|
| [ui_real_admin.py](ui_real_admin.py): Dashboard và Đăng ký khóa học với dữ liệu thật | Tải đủ, mọi API trả 200. Dashboard hiện 9 học viên, hai site online, 4 lớp nổi bật; trang Đăng ký khóa học liệt kê 9 người đăng ký của cả hai site |
| [ui_issue_account.py](ui_issue_account.py): cấp tài khoản cho học viên ở **site không phải authority** (EVB) | `POST …/account/?site_code=EVB` trả 201; hàng biến khỏi danh sách chờ. Kiểm tra database: tài khoản có ở cả authority (EVA) và EVB, học viên EVB được gắn đúng mã tài khoản, thư chỉ đến máy chủ giả |
| [ui_outage.py](ui_outage.py): EVB về OFFLINE | Dashboard: "Các site chưa phản hồi: EVB". Đăng ký khóa học: cảnh báo vàng rộng hết bề ngang, danh sách chỉ còn 5 người của EVA. Không lỗi 500. Đã bật EVB lại sau đó |

Ảnh: [screenshots](screenshots).

## Phát hiện và sửa

- Chân trang admin hiển thị **độ trễ và tên database cố định** (`QLTTNN_Q1 (12ms) · Q7 (15ms) · TD (18ms)`), giống số đo trực tiếp nhưng không phải: trên môi trường tạm vẫn hiện ba site Q1, Q7, TD. Đã đổi thành dòng mô tả tĩnh, không có số giả.
- `CampusStatusCards.tsx` (số liệu cố định 542 học viên, doanh thu…) không còn component nào dùng; đã xóa.
- Lần cấp tài khoản đầu trả 503 vì môi trường chạy dùng backend console: hệ thống chỉ cấp tài khoản khi cấu hình SMTP (chủ ý, tránh cấp tài khoản mà không gửi được mật khẩu). Không phải lỗi; khi dùng SMTP giả thì thành công.

## Giới hạn

- Hai site trên cùng một instance, không phải ba máy; chưa chạy với dữ liệu `DangKy` thật của Q1, Q7, TD.
- Lúc cấp tài khoản chưa thử trường hợp một site mất kết nối giữa chừng.
- Trình duyệt ở cỡ màn hình máy tính; kiểm tra điện thoại nằm ở [bản 26/11](../2026-11-26/README.md).
