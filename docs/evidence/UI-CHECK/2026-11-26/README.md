# Kiểm tra giao diện trên trình duyệt (26/11/2026)

Chạy bằng Playwright (Chromium headless) trên máy chủ web đang chạy ở `localhost:3001` (bản dev), cửa sổ 1440×900 và 390×844. Kịch bản: [ui_check.py](ui_check.py) và [ui_mobile_admin.py](ui_mobile_admin.py); kết quả từng ca: [report.json](report.json); ảnh: [screenshots/](screenshots/).

## Phần nào là thật, phần nào là giả lập

- **API thật (Q1, TD; Q7 offline):** trang Blog (danh sách, chi tiết) và danh mục khóa học công khai.
- **Giả lập trong trình duyệt:** mọi trang cần đăng nhập (`/admin/enrollments`, `/account`), phiên đăng nhập và dữ liệu của chúng, vì không có mật khẩu admin để dùng. Hộp thoại đăng ký lớp cũng dùng danh mục khóa học và lớp giả lập, vì các khóa học thật hiện chưa có lớp mở nên nút "Đăng ký lớp" bị vô hiệu (đúng thiết kế).
- Nên kết quả của các trang giả lập chỉ chứng minh **giao diện và hành vi phía trình duyệt**, không chứng minh backend. Backend của trang Đăng ký khóa học được kiểm bằng test và truy vấn thật ở các bước trước.

## Kết quả

| Hạng mục | Kết quả |
|---|---|
| Blog danh sách và chi tiết (desktop, mobile) | Không tràn ngang; chi tiết không còn dòng "Bắt đầu đọc"; 0 lỗi console |
| Trang Đăng ký khóa học, Admin Big (desktop) | Cảnh báo thiếu site rộng 96% khung (1082/1132px) và nêu đúng "cơ sở Q7"; mặc định ẩn người đã cấp; đủ hai nhãn "Đã đăng ký trên website" và "Chưa có tài khoản"; có mục menu; 0 lỗi console |
| Hộp thoại xác nhận cấp tài khoản | Với người đã có tài khoản website, nội dung nói tài khoản được chuyển thành học viên và giữ nguyên mật khẩu |
| Công tắc "Chỉ người chưa có tài khoản" | Tắt thì hiện người đã cấp với nhãn "Đã cấp"; học viên không có email có nút cấp bị vô hiệu |
| Trạng thái rỗng và lỗi (503) | Hiển thị đúng, không vỡ bố cục |
| Tư vấn & xếp lớp | Chỉ thấy chữ "Chờ Admin cấp tài khoản", không có nút cấp |
| `/account` (tài khoản `nguoi_dung`) | Tải hồ sơ, email và tên đăng nhập bị khóa, đúng bố cục; 0 lỗi console |
| Hộp thoại đăng ký lớp | Mở được cho khách và cho tài khoản website; với tài khoản website, họ tên, email, số điện thoại được điền sẵn và email chỉ đọc |

Một ca báo không đạt trong `report.json`: trang Đăng ký khóa học trên điện thoại tràn ngang 534px. Phân tích bên dưới cho thấy đây không phải lỗi riêng của trang này.

## Phát hiện

1. **Khu admin chưa dùng được trên điện thoại (có sẵn từ trước).** Đo 5 trang admin ở 390px (`/admin/enrollments`, `students`, `notifications`, `rooms`, `audit`): cả 5 tràn ngang đúng 661px khi nội dung rỗng (534px với dữ liệu giả của trang Đăng ký khóa học) vì thanh menu rộng cố định 260px, không thu gọn. Giao diện admin được thiết kế cho màn hình lớn. Chưa sửa vì ngoài phạm vi; hướng sửa là thu gọn menu dưới khoảng 768px.
2. **Blog: API báo TD không nhất quán với Q1.** `GET /api/v1/blog/articles/` trả `inconsistent_sites=["TD"]` và `missing_sites=["Q7"]`. Hàng đợi Blog trên Q1 trống (0 chờ, 0 cần đối soát), nên đây không phải việc đang chờ phát lại. Nghi ngờ: bài `bat-dau-hoc-ngoai-ngu` (cập nhật lần cuối 26/11/2026 03:40 UTC ở Q1, có nội dung và ảnh bìa mới) được sửa khi TD offline và chưa có hàng đợi, nên TD và Q7 còn bản cũ. Chưa xác nhận trực tiếp vì TD mất kết nối ngay lúc so sánh; cần so dữ liệu Q1 với TD khi TD lên rồi quyết định có phát lại bản của Q1 sang TD và Q7 không.
3. **Kết nối TD chập chờn.** Trong lúc làm, TD lúc truy cập được lúc hết thời gian chờ (`08001`). Đây chính là kiểu lỗi mà `missing_sites` và hàng đợi đồng bộ phải chịu được.

## Giới hạn

- Chỉ Chromium; chưa thử Safari/Firefox. Chỉ hai cỡ cửa sổ.
- Chưa kiểm tra bằng tài khoản admin thật, nên chưa thấy trang Đăng ký khóa học với dữ liệu `DangKy` thật (bảng này ở Q1 đang trống).
- Chưa kiểm tra Dashboard và các trang admin khác sau thay đổi cảnh báo rộng 100%; chỉ đo trực tiếp trên trang Đăng ký khóa học.
- Máy chủ web là bản dev đang chạy sẵn của nhóm; không phải build production.

## Chạy lại

Cần web ở `localhost:3001` và API ở `localhost:8001`, rồi từ gốc repo: `python docs/evidence/UI-CHECK/2026-11-26/ui_check.py` (dùng Python có cài `playwright` và Chromium). Kịch bản ghi ảnh vào `screenshots/` cạnh nó.
