# Các điểm cần cả nhóm xác nhận trước khi nộp (hạn 17/12/2026)

Cập nhật 27/11/2026. Mỗi mục có **mặc định mình đề xuất**; nếu cả nhóm đồng ý thì chỉ cần ghi "ok", nếu không thì sửa cột quyết định. Chỗ nào còn trống là thông tin chỉ nhóm biết.

## 1. Giao dịch phân tán (2PC/MSDTC) — đã làm cả hai đường

**Nhận định ban đầu (đã đổi):** hai tài liệu giảng viên đã đọc (GV-01 mục 3.7, GV-06 trang 66–70) chỉ nêu "thử các giao tác" và trigger bảo vệ, không nói rõ MSDTC/2PC. Nhưng danh sách 5 yêu cầu có "ít nhất 1 distributed transaction", và nhóm khác của cùng môn (dự án PTIT-One) hiểu đó là 2PC/MS DTC bắt buộc. Vì không hỏi được giảng viên nên nhóm làm **cả hai đường**, chọn bằng cấu hình:

| Đường | Cách làm | Khi nào dùng |
|---|---|---|
| Phục hồi tiến về phía trước (có sẵn) | Mỗi bước là một transaction cục bộ, có sự kiện để chạy tiếp; chịu được site đích mất kết nối | Mặc định; khi chưa cấu hình MS DTC |
| **2PC qua MS DTC** (mới, migration 50) | Một `BEGIN DISTRIBUTED TRANSACTION` qua Linked Server: đích và nguồn cùng commit hoặc cùng hủy | Khi bật `TRANSFER_2PC_LINKED_SERVERS_JSON` cho cặp site |

Đường 2PC đã chạy và đạt trên hai instance SQL Server thật cùng một máy (K1 đến K5, kể cả đích offline và lỗi ở nguồn sau khi đích đã ghi): [TC-DTX-01](evidence/TC-DTX-01/2026-11-27/README.md). Chưa chạy trên Q7 và TD thật.

Việc còn lại: cấu hình MS DTC và Linked Server giữa các máy thật trong buổi chạy bằng chứng ([hướng dẫn](QLTTNN-Chay-Bang-Chung-Site-That.md#2pc)), chụp ảnh, và chụp ảnh thử trigger và ràng buộc (mã `E-3.7-01` đến `E-3.7-06`). Rủi ro lớn nhất là MS DTC qua ZeroTier và trên SQL Server Linux (Q7); nếu không chạy được thì trình bày 2PC ở mức hai instance cùng máy cộng đường phục hồi tiến về phía trước cho ba site.

## 2. Ba quyết định về hệ thống

| # | Câu hỏi | Hiện trạng trong code | Đề xuất mặc định | Lý do | Quyết định của nhóm |
|---|---|---|---|---|---|
| 1 | Bật tự đăng ký tài khoản (`SELF_REGISTRATION_ACCOUNT_ONLY`) | Đang **tắt**. Bật cần Q7 chạy migration 48, chạy `seed_student_emails` và duyệt vai trò `nguoi_dung` | **Giữ tắt cho tới buổi chạy trên site thật.** Trong buổi, nếu migration 48 ở Q7 chạy tốt thì bật; nếu không thì để tắt và ghi vào báo cáo là chưa bật | Bật khi Q7 thiếu migration 48 có thể làm trùng email giữa các site; đề tài không bắt buộc đăng ký công khai | |
| 2 | Tư vấn & xếp lớp có được cấp tài khoản học viên không | Chỉ Admin Big và Admin Small cấp được. Tư vấn đã được tạo và sửa hồ sơ học viên và tạo đề nghị chuyển cơ sở | **Giữ như hiện tại** (Tư vấn không cấp tài khoản) | Cấp tài khoản gửi mật khẩu tạm qua email và liên quan xác thực; để ở vai trò quản trị đúng nguyên tắc ít quyền nhất. Muốn đổi thì chỉ cần thêm `tu_van` vào danh sách vai trò của endpoint cấp tài khoản và test | |
| 3 | `MonHoc` có đổi sang "ghi cả khi thiếu site" như Blog và `KhoaHoc` không | Ghi `MonHoc` bị từ chối khi thiếu site; Blog và `KhoaHoc` ghi site còn sống rồi đồng bộ sau | **Giữ như hiện tại** | `MonHoc` dùng SQL Server Publication (GV-04). Code ghi `MonHoc` tại Publisher chỉ sau khi đọc và đối soát được **mọi** site đang hoạt động (để biết bản sao đang khớp trước khi Publication phát thay đổi), nên thiếu site thì từ chối. Đây là lựa chọn thận trọng, không sai với yêu cầu. Đổi cần sửa code và chạy lại bằng chứng, mà Q7 và TD đang offline nên không kiểm thử được | |

Một điểm tùy chọn đi kèm mục 3: làm thêm demo Publication có bộ lọc theo bảng cha như GV-02. Chỉ nên làm nếu còn thời gian sau buổi chạy bằng chứng.

## 3. Máy và phiên bản (điền trước khi chụp ảnh cài đặt)

| Site | Máy | Chủ máy | SQL Server | Ghi chú |
|---|---|---|---|---|
| Q1 | `DESKTOP-CK4K90F`, Windows, đăng nhập Windows | Quốc Hiếu | SQL Server 2022, `16.0.1000.6`, Developer Edition (64-bit), RTM (đọc từ máy ngày 27/11/2026) | Authority xác thực, Publisher của `MonHoc` |
| Q7 | SQL Server trên Linux trong Docker, trên máy Mac, instance `sql-q7` | Minh Khôi (theo `QLTTNN-Lam-Viec-Nhom.md`) | **chưa biết** — chạy `SELECT @@VERSION` | Cần xác nhận máy |
| TD | `DESKTOP-N47BBPH`, database `QLTTNN_TD_MOI`, đăng nhập user/mật khẩu | Minh Đức (theo `QLTTNN-Lam-Viec-Nhom.md`) | SQL Server 16.0.1000.6 (đã ghi nhận trước đó) | Nhiều tài liệu cũ ghi TD cùng máy Q1; bản đúng là máy riêng. Cần xác nhận |

Câu lệnh lấy phiên bản trên mỗi máy:

```sql
SELECT SERVERPROPERTY('ProductVersion') AS version, SERVERPROPERTY('Edition') AS edition, SERVERPROPERTY('ProductLevel') AS level;
```

Cần xác nhận: tên chủ máy ở bảng trên có đúng không, và sơ đồ máy [bo-tri-vat-ly](diagrams/bo-tri-vat-ly.png) có đúng với thực tế không (hiện là bản nháp).

## 4. Danh sách 5 sinh viên (điền)

| STT | Họ và tên | MSSV | Vai trò (A đến E, xem [làm việc nhóm](QLTTNN-Lam-Viec-Nhom.md)) | Máy phụ trách |
|---|---|---|---|---|
| 1 | Quốc Hiếu | | | Q1 |
| 2 | Minh Khôi | | | Q7 |
| 3 | Minh Đức | | | TD |
| 4 | | | | |
| 5 | | | | |

Họ tên đầy đủ của ba người đầu lấy từ tài liệu nhóm chỉ ghi tên; cần điền họ và tên đệm, MSSV, và hai thành viên còn lại. Bảng này đưa vào mục 1 của báo cáo.
