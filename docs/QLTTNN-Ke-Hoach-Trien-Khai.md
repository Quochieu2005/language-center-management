# Kế hoạch triển khai và tiêu chí hoàn tất

Kế hoạch này bám theo README chính, mục 6, 9 và 10. README là nguồn quyết định cho nghiệp vụ; [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) là nguồn quyết định cho cấu trúc bảng. Đọc [hướng dẫn làm việc nhóm](QLTTNN-Lam-Viec-Nhom.md) trước khi chia đầu việc. Yêu cầu báo cáo và minh chứng cài đặt chi tiết nằm trong [đề cương báo cáo](QLTTNN-De-Cuong-Bao-Cao.md).

## 1. Cổng quyết định trước khi code

Stack đã chốt trong README mục 9: SQL Server, SSMS, Django API và Next.js frontend. Trước phần phụ thuộc, nhóm vẫn cần thống nhất cách đặt các CSDL/site, cấu hình kết nối an toàn, cơ chế giao dịch/phục hồi liên site, session/token, email, giới hạn đăng nhập sai, thời hạn token, lưu log, công thức điểm và điều kiện hoàn thành. Ghi người quyết định và lý do trong lịch sử nhóm; không tự thêm công nghệ khác vào source.

## 2. Các giai đoạn và đầu ra

| Giai đoạn | Công việc | Bằng chứng/đầu ra để chuyển bước |
|---|---|---|
| A. Chốt cấu hình triển khai | Ghi phiên bản/cấu hình SQL Server, cách đặt từng site, cấu hình Django và quy trình chạy Next.js/Django | Quyết định được ghi, mọi thành viên có thể dựng cùng môi trường |
| B. CSDL | Tạo các CSDL riêng; chạy cùng schema; tạo dữ liệu demo khác nhau theo site và bản nhân bản giống nhau | Có thể kết nối độc lập tới từng site; kiểm tra phân mảnh và nhân bản bằng truy vấn |
| C. Django Coordinator API | Site Router, danh sách cơ sở hoạt động, Global Query, logging và nền giao dịch | Không hard-code số site; truy vấn biết nguồn; site mất kết nối được báo rõ |
| D. Quyền và dữ liệu dùng chung | Đăng nhập, phân quyền, tài khoản, quên mật khẩu, danh mục, đồng bộ | Quyền bị từ chối đúng; bảng nhân bản không báo thành công nếu thiếu site |
| E. Nghiệp vụ cơ sở | Mở lớp, sinh lịch, đăng ký, đổi lớp, học phí, điểm danh, điểm | Mỗi thao tác chỉ thay đổi site sở hữu; thay đổi cùng nghiệp vụ rollback cùng nhau |
| F. Nghiệp vụ toàn cục | Thống kê, tra cứu học viên, nhật ký nhiều site | Kết quả gộp; cảnh báo site thiếu; không đếm `da_chuyen_di` |
| G. Chuyển cơ sở | Đề nghị Admin Small, duyệt/từ chối của Admin Big, Global Query, transaction, retry và phục hồi | Chứng minh chờ duyệt, từ chối, duyệt; lỗi trước khi tạo đích và restart sau khi tạo đích |
| H. Hoàn thiện | Giao diện, kiểm thử tích hợp, demo, ảnh cài đặt, báo cáo và slide | Kịch bản demo có thể chạy lại từ đầu; tài liệu khớp source thực tế |

Đây là nhóm giai đoạn để quản lý tích hợp; danh sách chức năng theo thứ tự chi tiết vẫn là README mục 10.

## 3. Ma trận kiểm chứng theo loại nghiệp vụ

| Loại | Kịch bản thành công | Kịch bản lỗi bắt buộc | Điều kiện đạt |
|---|---|---|---|
| `LOCAL` | Đăng ký ở Q1 tạo đăng ký, học phí, tăng sĩ số, ghi log | Ép lỗi ở từng bước sau khi bắt đầu giao dịch | Rollback toàn bộ; chỉ Q1 thay đổi khi thành công |
| `GLOBAL` | Đếm học viên tại từng site rồi cộng | Một site timeout | Hiện phần có được, nêu site thiếu và đánh dấu chưa đầy đủ |
| `REPLICATED-WRITE` | Sửa khóa học khi mọi site hoạt động | Một site không kết nối hoặc lỗi giữa chừng | Từ chối trước khi bắt đầu nếu site không sẵn sàng; nếu lỗi giữa chừng có recovery, không để lệch âm thầm |
| `DISTRIBUTED-TX` | Chuyển học viên hết nợ từ Q1 sang Q7 | Q7 không sẵn sàng trước khi tạo hồ sơ đích; tiến trình dừng sau khi đích tạo xong | Nhánh đầu không đổi Q1; nhánh sau resume phần nguồn; chỉ một bản được tính là đang học sau recovery |

## 4. Kịch bản demo bảo vệ

Theo bảng README mục 6, chạy đủ 17 kịch bản: kiểm tra phân mảnh; đăng ký/thu học phí cục bộ; từ chối quyền sai site; thống kê toàn cục; ghi nhân bản thành công và khi thiếu site; Admin Small tạo đề nghị chuyển; chặn Admin Small duyệt; Admin Big duyệt và từ chối; kiểm tra site đích đóng; retry khi mất kết nối trước commit đích; restart sau khi đích commit; hai đề nghị chuyển đồng thời; đặt lại mật khẩu; kiểm tra nhật ký; thêm cơ sở BT. Dùng dữ liệu mẫu của [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md), không sửa cứng dữ liệu demo vào ứng dụng.

## 5. Bằng chứng cài đặt

Theo đúng hướng dẫn giảng viên, lưu ảnh/script chứng minh cấu hình mạng hoặc VPN/Remote Desktop, kết nối server, cài SQL Server và quản trị bằng SSMS, kiểm tra Agent nếu áp dụng, Linked Server/Publication nếu được yêu cầu, truy vấn trước/sau đồng bộ và giao dịch thử. Ghi phiên bản Next.js/Django và cách API kết nối từng CSDL. Bảng mã ảnh và nội dung cần chụp theo từng mục 3.1–3.7 nằm trong [đề cương báo cáo](QLTTNN-De-Cuong-Bao-Cao.md). Tài liệu này không khẳng định bước nào đã cài xong; ghi nhận theo trạng thái thực tế.

## 6. Definition of Done cho một chức năng

- Có chủ sở hữu và người review; source dùng đúng Next.js, Django và SQL Server đã thống nhất.
- Quyền, loại nghiệp vụ, site và bảng bị tác động được nêu trong PR.
- Thành công và thất bại đã được chứng minh; có kiểm tra nhật ký và dữ liệu sau thao tác.
- Không có JOIN/FK xuyên site, dữ liệu hard-code hoặc bí mật trong repo/log.
- Docs cập nhật đồng bộ nếu đổi schema, trạng thái, quyền hoặc luồng.
- Kịch bản integration chạy trên các CSDL độc lập giống môi trường demo.
