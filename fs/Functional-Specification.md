# Đặc tả chức năng hệ thống

**Tên hệ thống:** Quản lý trung tâm đào tạo ngoại ngữ

**Môn học:** Cơ sở dữ liệu phân tán

**Phiên bản:** 1.0

**Trạng thái:** Tài liệu yêu cầu và tiêu chí nghiệm thu. Code hiện có nhiều luồng nghiệp vụ; phạm vi source, tình trạng vận hành và bằng chứng môn học được phân biệt trong [ma trận trạng thái triển khai](../docs/Trang-Thai-Trien-Khai.md).

## 1. Mục đích và người đọc

Tài liệu này chuyển yêu cầu đề tài thành hành vi cụ thể để thành viên nhóm có thể phân công, code, review và kiểm thử nhất quán. Mỗi yêu cầu nêu người dùng, điều kiện đầu vào, luồng thành công, lỗi cần xử lý, phạm vi site, bảng dữ liệu và tiêu chí nghiệm thu.

Người đọc chính là thành viên làm frontend, API/Coordinator, SQL Server, kiểm thử và người review nghiệp vụ. Tài liệu này không thay thế:

- [README.md](../README.md): kiến trúc, giải thích nghiệp vụ và hướng dẫn cho thành viên.
- [docs/DATABASE_SCHEMA.md](../docs/DATABASE_SCHEMA.md): tên bảng/cột, khóa, quan hệ, phân mảnh và vị trí dữ liệu.
- [specs/api.md](../specs/api.md): hợp đồng HTTP dự kiến, bảo mật và quy ước response.
- [specs/ui-ux.md](../specs/ui-ux.md): cấu trúc trang, trạng thái giao diện và quy tắc trình bày.

Khi một chức năng cần bảng/cột chưa có trong schema, phải cập nhật schema và script SQL trước hoặc cùng thay đổi triển khai. Không tạo database nghiệp vụ trung tâm để làm cho nghiệp vụ dễ viết hơn.

## 2. Bài toán, mục tiêu và phạm vi

Trung tâm có nhiều cơ sở; nhân sự tại một cơ sở cần quản lý hồ sơ, lớp, đăng ký, học phí và điểm tại nơi mình làm việc. Ban quản lý cần xem số liệu toàn trung tâm, quản trị danh mục dùng chung và duyệt việc chuyển học viên. Một học viên có thể đổi cơ sở, vì vậy mã học viên không đủ để xác định nơi lưu hồ sơ hiện tại.

Hệ thống phải thể hiện CSDL phân tán thật: mỗi cơ sở có một CSDL SQL Server riêng, cùng cấu trúc logic nhưng chứa các mảnh dữ liệu phù hợp. Django API/Coordinator định tuyến truy vấn đến các CSDL site. Truy vấn nhiều cơ sở được tổng hợp ở tầng API; dữ liệu nghiệp vụ không được gom lưu vào một CSDL trung tâm.

Ba site ban đầu:

| Mã | Cơ sở |
|---|---|
| Q1 | Quận 1 |
| Q7 | Quận 7 |
| TD | Thủ Đức |

Danh sách site không được đóng cứng trong code. Khi có thêm cơ sở, Site Router lấy các site hoạt động từ dữ liệu CoSo và đối chiếu cấu hình kết nối. Một site hoạt động thiếu cấu hình hoặc không kết nối được phải được báo rõ.

### 2.1. Nằm trong phạm vi

- Một frontend web dùng chung, xác thực tập trung, sau đăng nhập hiển thị workspace theo vai trò.
- Quản lý hồ sơ học viên, giáo viên, nhân viên, cơ sở, lớp, lịch học và danh mục khóa học.
- Sáu nghiệp vụ đề tài: đăng ký khóa học, xếp lớp, chuyển cơ sở, đóng học phí, quản lý điểm, thống kê học viên theo cơ sở.
- Phân quyền Admin Big, Admin Small, Kế toán & Lễ tân, Tư vấn & xếp lớp và giáo viên.
- Đăng nhập nội bộ; thiết kế đăng nhập Google/Facebook và khôi phục mật khẩu theo các ràng buộc bảo mật trong tài liệu.
- Phân mảnh ngang theo site, phân mảnh dẫn xuất, nhân bản dữ liệu dùng chung, Global Query và điều phối chuyển cơ sở.
- Nhật ký thao tác, trạng thái đồng bộ và kiểm chứng các kịch bản site lỗi.

### 2.2. Ngoài phạm vi hiện được chốt

- Portal tự phục vụ của học viên và thanh toán online chưa được duyệt vào phạm vi môn học. Source hiện có portal và tích hợp SePay. Admin quản lý hồ sơ và cấp tài khoản học viên theo thao tác riêng thuộc FS-STU-01; việc này không bật portal hoặc thanh toán online.
- Khẳng định transaction ACID nguyên tử xuyên hai SQL Server độc lập cho chuyển cơ sở. Thiết kế hiện tại là điều phối có trạng thái, idempotency và phục hồi tiến về phía trước.
- Xóa cứng học viên đã có tài khoản, đăng ký hoặc lịch sử nghiệp vụ; với hồ sơ chưa phát sinh dữ liệu liên quan, FS-STU-01 cho phép xóa tại site sở hữu hồ sơ. Không xóa cứng phiếu thu, điểm, điểm danh hoặc lịch sử nghiệp vụ.

## 3. Thuật ngữ và quy tắc phân tán

### Yêu cầu chung phải nghiệm thu cùng chức năng

Theo yêu cầu môn học, mỗi đề tài có **2–4 site** và phải triển khai **phân mảnh, replication, transaction, đồng bộ dữ liệu**. Ba site Q1/Q7/TD thuộc phạm vi này; kịch bản BT là site thứ tư. Mỗi nhóm được chọn kiểu phân mảnh phù hợp, nhưng phải chứng minh **ít nhất 1 phương pháp phân mảnh + 1 phương pháp replication + 1 distributed transaction + 1 tình huống concurrency + 1 distributed query**.

[YC-01–YC-07 và kịch bản kiểm chứng](../docs/QLTTNN-Yeu-Cau-Chung-Va-Kiem-Chung.md) là tiêu chí nghiệm thu bắt buộc. Các mục cơ chế còn mở không miễn yêu cầu. Điều phối chuyển hiện được thiết kế theo phục hồi tiến về phía trước; cần chốt mức bảo đảm phù hợp tiêu chí giảng viên, không tự khẳng định đã có ACID nguyên tử xuyên site.

| Thuật ngữ | Ý nghĩa trong dự án |
|---|---|
| Site/cơ sở | Một cơ sở nghiệp vụ và CSDL SQL Server độc lập tương ứng. |
| Site Router | Thành phần trong Django chọn cấu hình kết nối cho site đã được xác thực. |
| LOCAL | Đọc/ghi trong một CSDL site. |
| GLOBAL | Đọc các CSDL site cần thiết, sau đó chuẩn hóa/gộp kết quả tại API. |
| REPLICATED-WRITE | Ghi bảng dùng chung tới mọi site hoạt động theo một cơ chế đồng bộ tập trung. |
| DISTRIBUTED-TX | Coordinator phối hợp các transaction cục bộ ở nhiều site, lưu trạng thái để tiếp tục/phục hồi. |
| Mảnh nguyên thủy | Dữ liệu thuộc trực tiếp một cơ sở, ví dụ HocVien hoặc LopHoc. |
| Mảnh dẫn xuất | Dữ liệu ở cùng site với bản ghi cha, ví dụ DangKy theo LopHoc. |
| Bản nhân bản | Bản sao nhất quán của danh mục/tài khoản dùng chung tại các site hoạt động. |
| Bản hiện hành | Bản HocVien có trạng thái dang_hoc tại site đang quản lý học viên. |

### 3.1. Quy tắc đặt và định vị dữ liệu

1. Mỗi site là một CSDL độc lập, không dùng một database với cột chi_nhanh để giả lập phân tán.
2. Không có khóa ngoại vật lý hoặc JOIN trực tiếp qua hai CSDL. Các kiểm tra liên site do Coordinator thực hiện bằng truy vấn riêng.
3. Bảng dùng chung theo schema hiện tại gồm CoSo, MonHoc, KhoaHoc và TaiKhoan; `google_subject`/`facebook_subject` là các cột danh tính provider trên TaiKhoan. Mọi thao tác ghi phải qua một service đồng bộ chung.
4. HocVien, GiaoVien, NhanVien, PhongHoc, LopHoc là các bảng phân mảnh theo cơ sở. BuoiHoc, DangKy, DiemDanh, HocPhi, PhieuThu và Diem ở cùng site với lớp/đăng ký cha.
5. `GiaoDichChuyenCoSo` lưu trạng thái tại site nguồn. `LichSuChuyenCoSo` và `Logs` là dữ liệu cục bộ theo site phát sinh; các log lịch sử chỉ được thêm trong luồng nghiệp vụ.
6. Tiền tố mã chỉ cho biết site tạo mã. Muốn tìm site hiện tại của học viên phải định vị bản dang_hoc, không suy ra từ mã.
7. Global Query không ghi bản tổng hợp trở lại CSDL nghiệp vụ. Nếu thiếu một site trong phạm vi, response phải ghi complete=false và liệt kê missing_sites.
8. Với REPLICATED-WRITE, không báo thành công toàn phần nếu một site bắt buộc chưa nhận được bản ghi. Lưu kết quả từng site và hỗ trợ retry/đối soát an toàn.

## 4. Vai trò và quyền

Quyền phải được xác định từ danh tính đã xác thực ở server. Frontend chỉ ẩn/hiện thao tác theo quyền để hỗ trợ người dùng; API vẫn phải kiểm tra quyền trên từng request và bản ghi.

| Vai trò | Biểu diễn theo schema hiện tại | Phạm vi |
|---|---|---|
| Admin Big | `TaiKhoan.vai_tro=admin_big`, `ma_co_so=NULL` | Toàn hệ thống |
| Admin Small | `TaiKhoan.vai_tro=nhan_vien`, hồ sơ `Admin.loai_admin=admin_small`, có site được giao | Một site được giao |
| Kế toán & Lễ tân | Tài khoản nhân viên, chức vụ `ke_toan` (hồ sơ `le_tan` cũ được chuyển bằng migration 41) | Tại site được giao: chỉ xem phòng, lớp/roster, hồ sơ học viên và công nợ; gửi email nhắc phí; xem đề nghị chuyển cùng công nợ lịch sử tại nguồn. Kế toán được xem phiếu thu và ghi nhận thu/hoàn; không CRUD phòng/lớp/học viên, không đăng ký/xếp lớp hoặc sửa kế hoạch đóng |
| Tư vấn & xếp lớp | Tài khoản nhân viên, chức vụ `tu_van` | Tại site được giao: CRUD hồ sơ học viên và phòng; tạo lớp, đăng ký/xếp lớp, phân công giáo viên, sửa tên/sĩ số lớp và hủy mềm lớp đủ điều kiện; xem công nợ, gửi email nhắc phí, chỉ sửa kế hoạch đóng; xem đề nghị chuyển và công nợ lịch sử read-only. Tiếp nhận/phản hồi liên hệ và tạo/sửa/xuất bản bài Blog dùng chung; không cấp tài khoản học viên |
| Giáo viên | TaiKhoan.vai_tro=giao_vien, liên kết hồ sơ GiaoVien | Lớp/buổi được phân công |
| Học viên | Admin có thể cấp tài khoản theo FS-STU-01; portal tự phục vụ chưa được duyệt | Không đưa các trang portal/SePay vào phạm vi đã chốt |
| Khách | Chưa xác thực | Xem nội dung công khai và gửi yêu cầu liên hệ tới cơ sở đang hoạt động |

### 4.1. Ma trận quyền chức năng

| Chức năng | Admin Big | Admin Small | Kế toán & Lễ tân | Tư vấn & xếp lớp | Giáo viên | Học viên |
|---|---:|---:|---:|---:|---:|---:|
| Quản lý cơ sở và danh mục dùng chung | Có | Đọc theo nhu cầu | Không | Không | Không | Không |
| Quản lý Admin Small/tài khoản nội bộ | Có | Không | Không | Không | Không | Không |
| Quản lý nhân viên nghiệp vụ | Chọn một site cho mỗi thao tác | Chỉ site được giao | Không | Không | Không | Không |
| CRUD hồ sơ học viên | Chọn một site cho mỗi thao tác | Chỉ site được giao | Không | CRUD tại site được giao | Không | Không |
| Cấp tài khoản học viên | Chọn một site cho mỗi thao tác | Chỉ site được giao | Không | Không | Không | Không |
| Tra cứu danh sách/hồ sơ học viên tại cơ sở | Toàn hệ thống theo quyền | Site được giao | Site làm việc, read-only | Site được giao | Học viên thuộc lớp được giao | Không |
| Đăng ký và xếp lớp | Giám sát/toàn hệ thống | Site được giao | Không | Site làm việc | Không | Không |
| Mở lớp, sửa tên/sĩ số, hủy lớp an toàn và phân công giáo viên | Toàn hệ thống theo site thao tác | Site được giao | Không | Site làm việc | Không | Không |
| Xem phòng, roster và công nợ theo lớp | Toàn hệ thống hoặc chọn site | Site được giao, read-only | Site làm việc, read-only | Site làm việc | Không | Không |
| Quản lý phòng học | Toàn hệ thống theo site thao tác | Site được giao | Không | CRUD tại site được giao | Không | Không |
| Gửi email nhắc học phí từ roster phòng | Theo site thao tác | Site được giao | Site làm việc | Site làm việc | Không | Không |
| Xem đề nghị chuyển và công nợ tại nguồn | Toàn hệ thống | Site được giao | Site làm việc, read-only | Site làm việc, read-only | Không | Không |
| Thu/hoàn học phí | Giám sát theo quyền | Giám sát tại site được giao | Site làm việc | Không | Không | Không |
| Điểm danh và điểm | Giám sát/đọc theo quyền | Site được giao | Không | Không | Chỉ lớp được phân công | Không |
| Tạo đề nghị chuyển | Có thể theo quy trình được duyệt | Chỉ học viên ở site mình | Không mặc định | Không | Không | Không |
| Duyệt/từ chối đề nghị chuyển | Có | Không | Không | Không | Không | Không |
| Thống kê | Toàn hệ thống | Site được giao | Báo cáo tài chính được cấp | Không mặc định | Lớp được giao nếu có | Không |
| Hộp thư liên hệ | GLOBAL hoặc chọn một site | Chỉ site được giao | Không | Site làm việc | Không | Không |
| Đăng/sửa bài Blog | Có | Không | Không | Toàn hệ thống (`REPLICATED-WRITE`) | Không | Không |
| Xóa bài hoặc quản lý danh mục Blog | Có | Không | Không | Không | Không | Không |

Không dùng vai trò do client gửi để cấp quyền. Không cho Admin Small truy cập dữ liệu site khác bằng cách đổi mã site trong URL/body. Không để giáo viên đọc/ghi lớp chưa được phân công.

## 5. Quy tắc dùng chung cho mọi chức năng

### 5.1. Kiểm tra dữ liệu và bảo mật

- Dùng Django ORM; nếu phải dùng SQL thô thì truyền tham số. Không nối chuỗi input vào câu SQL. Tên cột, sort và filter động lấy từ allowlist.
- Kiểm tra kiểu, độ dài, miền giá trị, quan hệ giữa trường, trạng thái bản ghi và quyền sở hữu/site tại API. Validation ở giao diện không thay thế validation server.
- Mật khẩu lưu bằng hash bcrypt qua cấu hình Django phù hợp; không lưu/ghi log mật khẩu gốc, hash, token, cookie, khóa ký hay secret.
- Phản hồi login, đăng ký và quên mật khẩu không tiết lộ tài khoản/email có tồn tại. Áp dụng rate limit theo IP và định danh; trả 429 cùng Retry-After.
- Ảnh nhị phân chỉ được đưa lên Cloudinary; không commit ảnh tải lên vào source hoặc thư mục media. Ảnh tài khoản lưu metadata trong `TaiKhoan` theo `REPLICATED-WRITE`; ảnh hồ sơ học viên lưu metadata trong `HocVien` tại site sở hữu theo `LOCAL`. Chưa có MediaAsset tổng quát hoặc bằng chứng upload thật.
- Lỗi API không trả SQL, stack trace, connection string hoặc secret. Có mã request để truy vết.

### 5.2. Thời gian, tiền và định dạng

- Múi giờ hiển thị/nghiệp vụ: Asia/Ho_Chi_Minh, định dạng 24 giờ. Ngày gửi dạng YYYY-MM-DD; timestamp có offset ISO/RFC3339.
- Ngày kết thúc không được trước ngày bắt đầu; lịch lớp/buổi không trùng phòng hoặc lịch giáo viên.
- Số tiền do server lấy từ HocPhi/site sở hữu hồ sơ, đơn vị VND; không tin số tiền và site do client gửi.
- Mọi phép tính số dư dùng kiểu decimal/đơn vị tiền nguyên phù hợp; không dùng số thực nhị phân cho tiền.

### 5.3. Gửi lặp và transaction

- Giao dịch LOCAL quan trọng phải ghi các bảng liên quan và nhật ký trong transaction cục bộ; nếu một bước thất bại thì rollback các bước của site đó.
- Mỗi thao tác ghi quan trọng phải có cách chống gửi lặp phù hợp. Khi nhận lại cùng request đã thành công, trả kết quả cũ hoặc báo xung đột theo hợp đồng; không tạo phiếu thu/đăng ký/điểm danh trùng.
- Không tuyên bố mọi thao tác nhiều site là ACID. Với Distributed-TX, trạng thái tiến trình và quy tắc phục hồi phải được lưu bền vững.
- DELETE chỉ dành cho dữ liệu nháp chưa phát sinh lịch sử và được quy định rõ. Học viên, thu/hoàn, điểm danh, điểm đã công bố và nhật ký phải được lưu lịch sử/điều chỉnh theo nghiệp vụ.

### 5.4. Mục tiêu hiệu năng cần đo

Đây là mục tiêu nghiệm thu ban đầu từ API/UI specs, không phải kết quả đã đo. Khi báo cáo kết quả phải ghi môi trường, kích thước dữ liệu, số site đang hoạt động, số request đồng thời, p50/p95 và công cụ đo.

| Nhóm | Mục tiêu ban đầu |
|---|---:|
| Đăng nhập và đọc thông tin phiên | API p95 không quá 500 ms |
| Đọc LOCAL | API p95 không quá 300 ms |
| Ghi LOCAL | API p95 không quá 500 ms |
| GLOBAL trang đầu/báo cáo | API p95 không quá 1500 ms; site chậm được thể hiện là thiếu theo deadline |
| Trang web | LCP không quá 2500 ms, INP không quá 200 ms, CLS không quá 0.1 tại p75 |

API phân trang ở server (mặc định 25 dòng, tối đa 100 theo API spec), chỉ lấy cột cần thiết, tránh truy vấn N+1 và đo query/execution plan trước khi thêm index. GLOBAL gọi các site với concurrency giới hạn và timeout từng site. Không đạt mục tiêu thì tối ưu rồi đo lại; không bỏ qua phân quyền, transaction, audit hay site lỗi để làm số đo đẹp hơn.

## 6. Yêu cầu chức năng

Các mục dưới đây mô tả hành vi và tiêu chí nghiệm thu, không khẳng định đã triển khai. Đối chiếu trạng thái source và bằng chứng hiện có theo [ma trận trạng thái](../docs/Trang-Thai-Trien-Khai.md); route hoặc unit test không thay thế TC phân tán chạy trên SQL Server.

### FS-PUB-01 — Xem nội dung công khai

**Người dùng:** khách, người dùng chưa đăng nhập. **Phân tán:** đọc bảng dùng chung hoặc truy vấn đọc phù hợp; không có quyền đọc hồ sơ nội bộ.

1. Người dùng xem trang chủ, danh sách/chi tiết khóa học và thông tin cơ sở đã được nhóm duyệt công khai.
2. Giao diện lấy dữ liệu qua API, không chứa dữ liệu khóa học/địa chỉ/học phí/đánh giá tự bịa.
3. Nếu một nguồn dữ liệu công khai lỗi, giao diện hiển thị trạng thái lỗi có thể thử lại, không giả lập dữ liệu thành công.

**Nghiệm thu:** trang công khai không yêu cầu đăng nhập; API không trả hồ sơ học viên, thông tin tài khoản hoặc dữ liệu nội bộ.

### FS-CONTACT-01 — Tiếp nhận và phản hồi yêu cầu liên hệ

**Người dùng:** khách chưa đăng nhập gửi form; Admin Big, Admin Small và Tư vấn & xếp lớp tiếp nhận/phản hồi. **Phân tán:** khách chọn một site đang hoạt động; API kiểm tra danh mục `CoSo` rồi ghi `LOCAL` trong CSDL site được chọn. Admin Big xem hộp thư `GLOBAL` hoặc lọc một site; Admin Small và Tư vấn & xếp lớp chỉ xem, phản hồi `LOCAL` tại site được giao. **Bảng:** `CoSo`, `YeuCauLienHe`, `Logs`.

1. Trang `/contact` tải danh sách cơ sở đang hoạt động từ API. Nếu một site chưa sẵn sàng, trang nêu rõ site thiếu và không đưa site lỗi vào lựa chọn gửi.
2. Khách nhập họ tên, email, cơ sở muốn liên hệ, tiêu đề và nội dung; số điện thoại không bắt buộc. API xác thực lại dữ liệu, giới hạn nội dung, giới hạn gửi theo IP/email và yêu cầu `Idempotency-Key` để retry không tạo yêu cầu trùng.
3. API chỉ ghi `YeuCauLienHe` và `Logs` vào CSDL site được chọn, trong một transaction cục bộ. Form gửi chưa tự phát email; yêu cầu mới ở trạng thái `cho_xu_ly` và xuất hiện tại trang `/admin/contacts`.
4. Admin Big đọc yêu cầu từ từng CSDL site riêng qua Global Query; Admin Small và Tư vấn & xếp lớp chỉ đọc site được phân công. Kết quả thiếu site phải có `complete=false`/`missing_sites`, không được trình bày như hộp thư đầy đủ.
5. Admin hoặc Tư vấn & xếp lớp xem người gửi, địa chỉ email, tiêu đề và nội dung rồi nhập phản hồi. API chỉ lấy email nhận từ bản ghi, gửi nội dung plain text qua SMTP và cập nhật trạng thái, nội dung phản hồi cùng `Logs` tại site sở hữu. Mỗi yêu cầu chỉ được phản hồi một lần theo trạng thái đã lưu.

**Lỗi và giới hạn:** dữ liệu sai không được ghi; site không hoạt động hoặc database lỗi không được báo đã nhận; gửi lại cùng key/body trả cùng yêu cầu, cùng key với body khác trả xung đột. Nếu SMTP chưa cấu hình hoặc từ chối thư thì yêu cầu vẫn ở `cho_xu_ly` để admin xử lý lại. SMTP và commit SQL không phải một giao dịch nguyên tử: nếu SMTP đã chấp nhận thư nhưng commit site lỗi, yêu cầu có thể vẫn ở `cho_xu_ly` và lần gửi lại có thể gửi trùng; cần transactional outbox nếu cần loại bỏ khoảng hở này. Rate limit dùng Django cache; cache mặc định giới hạn theo từng worker, cần cache dùng chung nếu chạy nhiều worker. Không trả stack trace/SQL, không ghi email hay nội dung form vào log. SMTP chấp nhận thư không chứng minh thư đã đến inbox người nhận.

**Nghiệm thu:** form khách chưa đăng nhập gửi được vào đúng site; Admin Big xem toàn hệ thống với cảnh báo site thiếu; Admin Small và Tư vấn & xếp lớp không thể đọc/phản hồi yêu cầu site khác dù sửa URL; vai trò khác bị từ chối; reply gửi đúng email bằng SMTP và lưu được lịch sử phản hồi; kiểm tra idempotency, rate limit, validation và lỗi database/SMTP. Các kiểm tra trên SQL Server thật, SMTP thật và kết quả site lỗi phải được ghi riêng; source không được tính là bằng chứng runtime.

### FS-BLOG-01 — Danh mục, bài viết công khai và quản trị Blog

**Người dùng:** khách chưa đăng nhập (đọc công khai), Admin Big (quản trị toàn bộ CMS), Tư vấn & xếp lớp (tạo/sửa/xuất bản bài viết). **Phân tán:** public `GLOBAL`; CMS `REPLICATED-WRITE` tới các bản `DanhMucBlog`/`BaiVietBlog` riêng tại từng site.

1. `GET /api/v1/blog/categories/` trả danh mục đang hoạt động cùng số bài đã xuất bản; chỉ tính bài đã xuất bản, không ẩn và không có ngày xuất bản trong tương lai.
2. `GET /api/v1/blog/{slug}/` trả một bài đã xuất bản theo slug, gồm tiêu đề, tóm tắt, nội dung Markdown giới hạn, thời gian đọc, ngày xuất bản và danh mục. Nội dung có thể dùng đoạn văn, tiêu đề `##`/`###`, danh sách đánh số (`1. Nội dung`) và bảng Markdown; bảng và danh sách là tùy chọn.
3. Blog không yêu cầu đăng nhập. Không trả bài nháp/ẩn, dữ liệu nội bộ hoặc HTML cần render thô; HTML nhập trong nội dung chỉ được hiển thị như văn bản.
4. API hỏi các CSDL site đang hoạt động, không dùng database trung tâm hoặc JOIN xuyên site. Các bản sao seed ban đầu phải nhất quán; nếu thiếu site hoặc dữ liệu lệch, response phải nêu `missing_sites`/`inconsistent_sites` và không giả là đầy đủ.
5. Slug không tồn tại ở bất kỳ site nào trả 404; bản ghi cùng slug khác nội dung giữa các site trả 409; không đọc đủ site để xác nhận slug trả 503.
6. Admin Big được đọc danh mục/bài viết ở mọi trạng thái, quản lý danh mục và tạo/sửa/xóa bài. Tư vấn & xếp lớp được đọc danh mục/bài viết và tạo/sửa/xuất bản bài qua CMS `/admin/blog`; không được sửa/xóa danh mục hoặc xóa bài. Quyền lấy từ phiên đã xác thực ở server. Bài viết là dữ liệu dùng chung; thao tác của Tư vấn & xếp lớp cũng ghi `REPLICATED-WRITE` tới mọi site hoạt động, không giới hạn ở site được phân công. Admin Small và các vai trò khác không được ghi Blog.
   - Khi tạo bài, CMS tự tạo slug từ tiêu đề; người dùng có thể tự sửa slug. Khi sửa bài đã có slug tùy chỉnh, đổi tiêu đề không tự thay URL đó.
   - Ngày xuất bản mặc định là ngày tạo theo `Asia/Ho_Chi_Minh`, chỉ chọn ngày; API nhận mốc 00:00 theo múi giờ này. Để trống ngày nếu muốn xuất bản ngay khi bật trạng thái.
   - Trình soạn Markdown có nút thêm một hàng vào bảng tại vị trí con trỏ; hàng mới dùng đúng số cột của bảng.
7. Ghi Blog là `REPLICATED-WRITE`: Coordinator dùng danh sách site hoạt động từ dữ liệu và cấu hình, ghi mỗi bản sao trong transaction cục bộ, lưu ACK vào `Logs`, yêu cầu `Idempotency-Key` và retry bằng cùng key. Không cam kết ACID nguyên tử xuyên database.
8. Nếu site thiếu trước khi ghi, trả lỗi dịch vụ; nếu một site lỗi sau khi các site khác đã commit, trả trạng thái chưa hoàn tất cùng `missing_sites`. Bản sao lệch hoặc key dùng lại với payload khác trả xung đột; không báo hoàn tất.
9. Không xóa danh mục đang có bài viết tham chiếu. Xóa bài viết lưu ảnh chụp trước thao tác vào nhật ký đồng bộ; bài viết chỉ xuất hiện công khai khi đã xuất bản, danh mục hoạt động và đến thời điểm xuất bản.

**Nghiệm thu:** danh sách và chi tiết công khai lấy từ SQL Server, bài nháp/ẩn hoặc chưa đến ngày xuất bản không xuất hiện; nội dung thường vẫn hiển thị khi không có bảng/danh sách, còn Markdown bảng và danh sách đánh số hiển thị đúng khi có; HTML thô không được thực thi. Trình soạn thảo thêm được hàng bảng đúng số cột tại vị trí con trỏ. Slug bài viết mới tự sinh từ tiêu đề và vẫn có thể nhập tay; slug tùy chỉnh của bài cũ không tự đổi khi sửa tiêu đề. Ngày xuất bản chỉ có ngày, mặc định ngày tạo theo `Asia/Ho_Chi_Minh` và được lưu ở đầu ngày địa phương; có thể để trống để xuất bản ngay. Admin Big quản lý toàn bộ danh mục/bài viết; Tư vấn & xếp lớp đọc danh mục/bài và tạo/sửa/xuất bản bài nhưng không xóa bài hoặc ghi danh mục. API từ chối thao tác ngoài quyền; validation, slug trùng, danh mục đang được dùng, retry cùng key, site thiếu và bản sao lệch có phản hồi đúng. Kịch bản chạy trên các database site thật và bằng chứng replication/sync được ghi riêng; source hoặc seed không được tính là bằng chứng đã đạt.

### FS-AUTH-01 — Đăng nhập tài khoản nội bộ

**Người dùng:** Admin Big, Admin Small, nhân viên, giáo viên. **Phân tán:** tra cứu bản TaiKhoan nhân bản; xác thực tại API.

**Điều kiện:** tài khoản tồn tại, mật khẩu khớp, trạng thái hoat_dong; Admin Big có ma_co_so NULL; nhân viên/giáo viên có site và hồ sơ hợp lệ.

1. Người dùng nhập email và mật khẩu trên một cửa đăng nhập chung. API vẫn nhận tên đăng nhập như định danh tương thích cho tài khoản cũ.
2. API chuẩn hóa định danh, áp rate limit, tìm tài khoản theo email hoặc tên đăng nhập trên các site theo cơ chế Global/định vị đã thống nhất, xác minh hash bcrypt.
3. API kiểm tra trạng thái tài khoản, vai trò, site và hồ sơ nhân sự. Không cho client chọn vai trò.
4. API tạo phiên đăng nhập an toàn; frontend chuyển người dùng đến workspace phù hợp.
5. Ghi sự kiện đăng nhập thành công/thất bại ở nơi quy định, không ghi mật khẩu hoặc token.

**Lỗi:** trả lỗi chung khi sai định danh/mật khẩu; 429 khi vượt giới hạn; từ chối tài khoản khóa/vô hiệu; nếu site cần tra cứu mất kết nối thì báo lỗi dịch vụ, không coi như tài khoản không tồn tại.

**Nghiệm thu:** cùng một form phục vụ mọi vai trò; đổi trường role/site trong request không nâng quyền; cookie phiên có HttpOnly, Secure khi HTTPS, SameSite và CSRF phù hợp; logout thu hồi phiên.

### FS-AUTH-02 — Đăng nhập Google/Facebook

**Trạng thái source:** Có route OAuth start/callback và code liên kết subject cho tài khoản học viên. Tích hợp provider thật chưa được kiểm chứng và OAuth học viên chưa thuộc phạm vi; việc Admin cấp tài khoản cho học viên được mô tả riêng tại FS-STU-01. **Phân tán:** Global đọc các bản `TaiKhoan`; liên kết/thu hồi cập nhật subject theo luồng nhân bản.

1. Người dùng chọn Google hoặc Facebook.
2. Backend tạo state/nonce chống CSRF/replay và khởi tạo OAuth Authorization Code flow.
3. Callback server xác minh state, code, issuer/audience, chữ ký/token và provider subject.
4. Chỉ đăng nhập nếu provider subject đã liên kết với tài khoản nội bộ còn hoạt động.
5. Không tự tạo tài khoản, không tự liên kết bằng email trùng nhau, không tin profile do browser gửi.

**Nghiệm thu:** callback lỗi/state không hợp lệ bị từ chối; access/refresh token của provider không lưu vào TaiKhoan hoặc Logs; một provider subject không thể gắn hai tài khoản.

**Điều kiện nghiệm thu:** cấu hình OAuth thật và HTTPS callback, áp dụng migration `27_move_oauth_identity_to_account.sql` cho database cũ, kiểm thử provider và quyết định phạm vi portal học viên. Có code/route không chứng minh provider đã hoạt động.

### FS-AUTH-03 — Quên và đặt lại mật khẩu

**Người dùng:** Admin Big/Admin Small theo source hiện tại. **Phân tán:** tra cứu tài khoản trên các site; OTP/ledger lưu ở database kỹ thuật được cấu hình; mật khẩu được cập nhật tới các bản `TaiKhoan`.

1. Người dùng gửi email/định danh đã đăng ký.
2. API luôn trả thông báo chung; với tài khoản đủ điều kiện, tạo OTP 6 số một lần, lưu hash và hạn dùng theo `PASSWORD_RESET_TIMEOUT` (mặc định 120 giây), rồi gửi qua SMTP.
3. Người dùng gửi OTP và mật khẩu mới; API kiểm tra mã, hạn, số lần sai, trạng thái và chính sách mật khẩu.
4. API cập nhật hash bcrypt tới tất cả site hoạt động bằng service đồng bộ chung, đánh dấu token đã dùng và thu hồi phiên cũ.

**Lỗi:** token sai/hết hạn/đã dùng không đổi mật khẩu; nếu replicated write chưa hoàn tất thì không báo thành công và lưu trạng thái để đối soát; giới hạn spam theo IP/email.

**Nghiệm thu:** token thô chỉ xuất hiện trong liên kết gửi người dùng, không lưu/log; cùng một token chỉ dùng một lần; email không tiết lộ account existence.

**Trạng thái source:** Có endpoint reset, bảng OTP/event và ledger phục hồi mật khẩu; luồng hiện áp dụng cho Admin Big/Admin Small. Cần xác nhận SMTP và kiểm tra end-to-end ở môi trường nhóm; secret không được ghi vào repo.

### FS-AUTH-04 — Tự đăng xuất sau 1 giờ không hoạt động

**Người dùng:** mọi tài khoản nội bộ đã đăng nhập: Admin Big, Admin Small, nhân viên, giáo viên. **Phân tán:** phiên là trạng thái kỹ thuật có thể thu hồi được lưu ở database site cấu hình `AUTH_SESSION_SITE_CODE`, không phải database nghiệp vụ trung tâm.

**Quy tắc:**

1. Mỗi phiên đăng nhập có hạn idle **60 phút (3600 giây)** từ hoạt động người dùng thật gần nhất. Mỗi thiết bị/trình duyệt là một phiên riêng.
2. Hoạt động thật gồm thao tác bàn phím, nhấn/chạm, cuộn trang có chủ ý và thao tác nghiệp vụ do người dùng khởi tạo. Request nền, polling, health check, tự refresh, timer, tab chỉ mở và thao tác reload không làm mới hạn.
3. API lưu/kiểm tra thời điểm hoạt động và thời điểm hết hạn theo đồng hồ server. Sau hạn, mọi API cần xác thực trả `401 SESSION_IDLE_TIMEOUT`, thu hồi phiên và xóa cookie. Frontend đưa người dùng về trang đăng nhập.
4. Khi đăng nhập hoặc tải lại trang, API trả `expires_at` của phiên; frontend khôi phục danh tính bằng `GET /auth/session/` từ cookie HttpOnly. Reload không gia hạn idle timeout. Frontend đặt bộ đếm theo `expires_at`, khi tới hạn hỏi API để xác nhận; trong bước phục hồi, chỉ `401` mới xóa trạng thái đăng nhập. Lỗi mạng/5xx phải giữ nguyên cookie, không điều hướng nhầm về đăng nhập và cho phép thử xác minh lại.
5. Frontend đồng bộ hoạt động giữa các tab cùng phiên. Có thể cảnh báo ở phút 55; nút “Tiếp tục phiên” phải được API xác nhận và không được dùng để hồi sinh phiên đã hết hạn.
6. Logout thủ công, khóa/vô hiệu tài khoản hoặc reset mật khẩu phải thu hồi phiên theo chính sách bảo mật; không ghi cookie/token vào log.

**Nghiệm thu:** phiên còn hiệu lực tại 59:59 nếu có hoạt động; sau 60:00 không hoạt động thì API từ chối và giao diện tự về đăng nhập; hoạt động thật đặt lại hạn; polling nền không đặt lại; reload khôi phục phiên còn hiệu lực nhưng không gia hạn; reload sau khi phiên hết hạn phải về đăng nhập; lỗi 503 không bị hiểu thành logout; test riêng Admin Big, Admin Small và giáo viên cho cùng kết quả. Schema/API lưu phiên đã có; cần kiểm chứng timeout và đồng bộ tab trên frontend.

**Trạng thái source:** API có cookie session, trả `expires_at` khi đăng nhập/khôi phục/gia hạn, endpoint khôi phục phiên, thu hồi phiên và idle timeout; frontend khôi phục qua `/auth/session/`, tự kiểm tra tại hạn hết phiên và giữ cookie khi gặp lỗi không phải 401. Kiểm chứng tích hợp, nhiều tab và runtime vẫn phải ghi riêng.

### FS-ACC-01 — Tạo và phân công tài khoản Admin Small/giáo viên

**Người dùng:** Admin Big. **Phân tán:** TaiKhoan Replicated-Write; hồ sơ Admin/GiaoVien Local tại site được giao. Nhân viên nghiệp vụ theo FS-EMP-01.

Admin Big đọc danh sách giáo viên bằng Global Query khi bỏ `site_code`: mỗi CSDL site được hỏi riêng, kết quả có `site_code` trên từng dòng và báo `complete=false`/`missing_sites` nếu thiếu site. Truyền `site_code` để lọc một site; xem chi tiết và mọi thay đổi hồ sơ/trạng thái vẫn định tuyến tới site cụ thể. Danh sách Admin Small cũng đọc toàn hệ thống mặc định và có thể lọc theo site.

1. Admin Big nhập thông tin tài khoản Admin Small hoặc giáo viên cùng site và chức vụ được giao.
2. API kiểm tra site hoạt động, chức vụ hợp lệ, email/tên đăng nhập duy nhất toàn hệ thống và quyền Admin Big.
3. API tạo định danh tài khoản một lần, bản sao TaiKhoan theo chính sách nhân bản và hồ sơ Admin Small hoặc GiaoVien tại site được phân công. Vòng đời hồ sơ nhân viên nghiệp vụ nằm riêng trong FS-EMP-01.
4. Cấp mật khẩu khởi tạo theo cấu hình backend, lưu hash và gửi thông tin tài khoản qua luồng email có thể retry; email dùng địa chỉ email làm thông tin đăng nhập chính, không yêu cầu người nhận dùng username được sinh tự động. API vẫn chấp nhận username như định danh thay thế. Buộc đổi mật khẩu theo chính sách hiện có. Không gửi mật khẩu dạng rõ qua log hoặc response API.
5. Nếu một bước nhiều site lỗi, ghi tiến trình; không cho đăng nhập bằng tài khoản mới ở trạng thái tạo dở; có thao tác retry/đối soát hoặc vô hiệu hóa an toàn.

**Quy tắc vai trò:** Admin Big dùng `admin_big` và không có site; Admin Small đăng nhập bằng `nhan_vien`, có hồ sơ `Admin.loai_admin=admin_small`; nhân viên có hồ sơ `NhanVien` và chức vụ nghiệp vụ; giáo viên dùng `giao_vien` và liên kết hồ sơ `GiaoVien`.

**Nghiệm thu:** trùng username/email bị chặn toàn hệ thống; Admin Small/giáo viên không thể đổi site qua client; thao tác tạo dở không tạo tài khoản hoạt động một phần.

**Trạng thái source:** Có API tạo Admin Small/giáo viên, nhân bản tài khoản, hồ sơ site và cấp email thông tin đăng nhập; giao dịch email thật và lỗi nhiều site cần kiểm chứng. Source không dùng luồng token kích hoạt được mô tả trước đây.

### FS-EMP-01 — Quản lý hồ sơ nhân viên nghiệp vụ

**Người dùng:** Admin Big và Admin Small. Admin Big mặc định đọc danh sách toàn hệ thống (`GLOBAL`) khi không truyền `site_code`, hoặc đọc một site (`LOCAL`) khi chọn cơ sở; chi tiết và mọi thao tác ghi luôn gắn với một cơ sở. Admin Small chỉ được làm tại cơ sở gắn với phiên đăng nhập. **Phân tán:** danh sách đọc riêng `NhanVien`, `TaiKhoan`, `Logs` tại các CSDL site hoạt động rồi tổng hợp trong API; nếu thiếu site phải trả `complete=false` và `missing_sites`. Tạo `NhanVien` tại site (`LOCAL`) và nhân bản `TaiKhoan` theo chính sách tài khoản hiện có (`REPLICATED-WRITE`); đọc/sửa hồ sơ và ghi trạng thái email tại site (`LOCAL`); gửi mật khẩu qua SMTP theo thao tác người dùng; chỉ ngưng đăng nhập bằng cách đồng bộ `TaiKhoan` và thu hồi phiên (`REPLICATED-WRITE`); xóa tài khoản đồng bộ giữa các site và xóa/giữ hồ sơ cục bộ theo ràng buộc chứng từ.

**Bảng:** `CoSo`/cấu hình site để xác định cơ sở hoạt động; `NhanVien`, `TaiKhoan` và `Logs` được đọc riêng ở từng CSDL site khi truy vấn toàn cục hoặc tại site được chọn khi đọc cục bộ; trạng thái/phiên/token/đánh dấu đã đọc thông báo được xử lý tại các bản sao tài khoản. Không có database nhân sự trung tâm hoặc JOIN xuyên site.

Endpoint gửi mật khẩu đối chiếu các bản sao `TaiKhoan` đang hoạt động (`GLOBAL` read), kiểm tra hồ sơ và ghi kết quả email vào `Logs` tại site sở hữu (`LOCAL`); SMTP là dịch vụ ngoài, không phải database thứ tư.

1. **Tạo (`POST /admin/employees/`):** nhận `full_name`, `email`, tùy chọn `username`/`phone`, `avatar_requested`, `job_title` và `site_code`. Chức vụ mới chỉ gồm `tu_van` (hiển thị Tư vấn & xếp lớp) và `ke_toan` (hiển thị Kế toán & Lễ tân); email/tên đăng nhập phải duy nhất trên các bản sao tài khoản. Admin Big phải chọn site; Admin Small không được chọn site khác.
2. API tạo hồ sơ `NhanVien` tại site được giao và tài khoản đăng nhập `nhan_vien` bằng service nhân bản hiện có. Mật khẩu khởi tạo chỉ lấy từ cấu hình backend, lưu dạng hash, không trả trong response/log và bắt buộc đổi mật khẩu lần đầu. Tạo tài khoản không gửi email; API ghi `employee_credential_email_ready` vào `Logs` tại site. Admin Big/Admin Small chủ động bấm **Gửi mật khẩu** để gọi `POST /admin/employees/{account_id}/credential-email/?site_code=...`. Chỉ trạng thái `ready` hoặc SMTP xác nhận thất bại (`failed`) mới cho gửi/thử lại; `sent`, `processing`, `unknown` hoặc `changed` khóa gửi lại để tránh lộ/gửi trùng mật khẩu. Email cấp tài khoản dùng email làm thông tin đăng nhập chính; username vẫn dùng được như định danh thay thế. Mỗi CSDL commit riêng; site lỗi thì không trả thành công toàn phần, retry cùng dữ liệu để tiếp tục đối soát, không tuyên bố ACID xuyên site.
   `avatar_requested` mặc định là `false`. Nếu được bật, response trả setup token ngắn hạn; giao diện xin upload intent, gửi bytes ảnh trực tiếp tới Cloudinary rồi gọi endpoint hoàn tất với public ID. API xác minh intent/asset và cập nhật `TaiKhoan.avatar_public_id`/`avatar_secure_url` theo chính sách `REPLICATED-WRITE`. Chỉ nhận JPG/JPEG, PNG, WebP tối đa 5 MB; không lưu bytes ảnh ở SQL Server/source. Upload ảnh lỗi không xóa tài khoản vừa tạo; giao diện phải báo rõ ảnh chưa lưu.
3. **Đọc danh sách/chi tiết (`GET`):** Admin Big bỏ `site_code` để đọc `GLOBAL` qua từng site hoạt động; truyền `site_code` để lọc `LOCAL`. Admin Small chỉ đọc site của mình. Danh sách trả `site_code` trên từng dòng cùng email, username, số điện thoại, chức vụ, trạng thái tài khoản và trạng thái gửi mật khẩu lấy từ `Logs`. Khi site lỗi, trả kết quả một phần cùng `complete=false`/`missing_sites`; không coi site thiếu là không có nhân viên. Chi tiết theo `slug` luôn kết hợp hồ sơ `NhanVien` với bản `TaiKhoan` cục bộ của site được chỉ rõ, không gộp nhiều CSDL.
4. **Sửa (`PATCH /admin/employees/{slug}/`):** chỉ cho phép `full_name`, `phone`, `job_title`, cần gửi ít nhất một trường. API chỉ sửa nhân viên đang làm việc, khóa bản ghi trong transaction tại site và ghi audit `Logs` cùng transaction. Gửi `phone: null` hoặc chuỗi rỗng để xóa số điện thoại.
5. Email và tên đăng nhập là danh tính `TaiKhoan` được nhân bản; `site_code` quyết định vị trí phân mảnh. Không nhận các trường này trong PATCH. Đổi danh tính hoặc điều chuyển nơi công tác cần nghiệp vụ đồng bộ/điều chuyển riêng, không giả lập bằng cập nhật hồ sơ cục bộ.
6. **Ngưng tài khoản (`PATCH /admin/employees/{slug}/status/`):** chỉ nhận trạng thái `inactive` cho tài khoản đang `active`; đồng bộ `TaiKhoan.trang_thai` đến các site đang hoạt động, tăng phiên bản và thu hồi phiên hiện có. Không có thao tác kích hoạt lại qua màn hình/API này. Không đổi `NhanVien.trang_thai`, vì trạng thái làm việc khác trạng thái đăng nhập.
7. **Xóa vĩnh viễn (`DELETE /admin/employees/{slug}/`):** yêu cầu xác nhận và xóa các bản sao `TaiKhoan`, phiên đăng nhập, token/giao dịch đặt lại mật khẩu, trạng thái đọc thông báo và ảnh Cloudinary; không đổi tài khoản sang `inactive`. Trước khi ghi, từ chối nếu tài khoản còn hồ sơ học viên/giáo viên/Admin, yêu cầu thanh toán hoặc giao dịch chuyển cơ sở đang mở. Tại site sở hữu, nếu `NhanVien` chưa được phiếu thu tham chiếu thì xóa vật lý hồ sơ; nếu đã có `PhieuThu`, giữ hồ sơ, đặt `ma_tai_khoan=NULL` và `trang_thai=nghi_viec` để bảo toàn chứng từ. Giữ `Logs` và phiếu thu. Mỗi site commit riêng và ghi dấu retry; site chưa hoàn tất thì không báo thành công toàn phần, có thể gọi lại cùng slug. Không tuyên bố ACID xuyên CSDL.

**Nghiệm thu:** người không phải Admin Big/Admin Small nhận 403; Admin Small không truy cập/sửa/xóa nhân viên ở site khác; site không hoạt động hoặc slug không thuộc site bị từ chối; danh sách mặc định của Admin Big gộp đúng các site hoạt động, mỗi dòng có `site_code`, username, phone và trạng thái gửi mật khẩu; lọc site chỉ trả dữ liệu site đó; lỗi site được đánh dấu `complete=false`/`missing_sites`; POST tạo nhân viên không gửi email và ghi trạng thái `ready`; chỉ thao tác bấm gửi mới gọi SMTP, `sent`/`unknown`/`changed` không thể gửi lại, SMTP xác nhận thất bại mới cho thử lại; email/username đều đăng nhập được; tạo nhân viên ở site khác không làm mất chế độ xem toàn hệ thống; upload ảnh sai MIME/loại/kích thước, token hết hạn hoặc public ID không khớp bị từ chối; ảnh chỉ được báo hoàn tất sau khi metadata đồng nhất trên các site; trạng thái tài khoản chỉ chuyển `active` → `inactive` và việc ngưng thu hồi phiên; DELETE làm tài khoản biến mất khỏi mọi bản sao, giữ Logs/phiếu thu, chỉ giữ hồ sơ rời tài khoản khi phiếu thu tham chiếu; lỗi site không bị báo thành công toàn phần và retry tiếp tục theo dấu đã lưu.

**Trạng thái source:** `GET` danh sách/chi tiết, `POST`, `PATCH` hồ sơ/ngưng tài khoản, `DELETE` vĩnh viễn và `POST .../credential-email/` gửi mật khẩu theo thao tác người quản lý có route/service; upload avatar ban đầu qua Cloudinary. Vai trò mới gộp Lễ tân vào Kế toán; chạy migration 37 rồi 41 trên mọi site trước khi triển khai code. Vẫn cần kiểm chứng SQL Server, SMTP, quyền từng vai trò/site và lỗi/khôi phục đồng bộ nhiều site.

### FS-ACC-02 — Xóa vĩnh viễn Admin Small

**Người dùng:** chỉ Admin Big. Nút `Kích hoạt/Ngưng` là thao tác đổi trạng thái riêng; nút `Xóa vĩnh viễn` không được thay bằng vô hiệu hóa.

**Phân tán:** `REPLICATED-WRITE` theo từng transaction cục bộ tại các CSDL site đang cấu hình. Không có CSDL trung tâm và không cam kết ACID xuyên site.

1. Admin Big xác nhận xóa không thể hoàn tác. API xác minh tài khoản là Admin Small, các bản sao `TaiKhoan` nhất quán và hồ sơ `Admin` nằm tại đúng site.
2. Nếu tài khoản còn liên kết hồ sơ `HocVien`, `GiaoVien`, `NhanVien`, yêu cầu thanh toán hoặc giao dịch chuyển cơ sở đang chờ/xử lý, API từ chối trước khi xóa site nào.
3. Khi đủ điều kiện, xóa vật lý hồ sơ `Admin`, các bản sao `TaiKhoan`, phiên đăng nhập, token/giao dịch đặt lại mật khẩu còn gắn tài khoản và ảnh Cloudinary. Không đổi tài khoản sang `inactive` để giả làm xóa.
4. Giữ nguyên `Logs`, điểm danh, lịch sử chuyển cơ sở, phiếu thu và dữ liệu nghiệp vụ. Mã tài khoản người thao tác trong dữ liệu lịch sử là giá trị lưu vết, không phải khóa ngoại bắt buộc tới tài khoản đang tồn tại.
5. Mỗi site được xử lý trong transaction riêng, có dấu tiến trình để retry an toàn sau khi site mất kết nối. UI chỉ báo xóa xong khi API xác nhận hoàn tất toàn bộ site bắt buộc.

**Nghiệm thu:** chỉ Admin Big gọi được DELETE; sau thành công không còn tài khoản/hồ sơ/phiên ở các site và đăng nhập bằng tài khoản đó thất bại; thao tác kích hoạt/ngưng vẫn chỉ đổi trạng thái; `Logs` và lịch sử nghiệp vụ còn nguyên; lỗi một site trả lỗi có thể retry, không báo thành công toàn phần.

### FS-SITE-01 — Quản lý cơ sở và danh mục dùng chung

**Người dùng:** Admin Big. **Phân tán:** đọc/ghi CoSo, MonHoc, KhoaHoc bằng Replicated-Write.

1. Admin Big tạo hoặc cập nhật cơ sở, môn học, khóa học, giá chuẩn và trạng thái.
2. API kiểm tra mã ổn định, quan hệ môn-khóa, miền dữ liệu và không cho đóng site đang có nghiệp vụ mở mà chưa xử lý. Mã khóa học tối đa 30 ký tự, bắt đầu bằng chữ in hoa, tiếp theo là chữ in hoa/chữ số; có thể có các đoạn bổ sung ngăn bằng dấu gạch nối đơn. Giao diện chuẩn hóa mã thành chữ in hoa; cùng mã phải được giữ nhất quán trên mọi site.
3. API danh mục môn học có đọc toàn cục và tạo/cập nhật/xóa đồng bộ qua các site đang hoạt động; API khóa học có tạo/cập nhật/xóa `KhoaHoc` theo cùng mô hình, kiểm tra môn học tồn tại giống nhau trên mọi site trước khi ghi. Mỗi site ghi ACK vào `Logs` trong transaction cục bộ. Runtime replication cho thay đổi `CoSo` và việc gom các luồng `TaiKhoan` về service chung vẫn còn thiếu. Cơ chế tại tầng API chưa thay cho bằng chứng kiểm chứng dữ liệu thực tế ở nhiều site.
4. Thời lượng khóa học lưu số tháng với tối đa hai chữ số thập phân (ví dụ `3,5 tháng`); nếu chọn ngày thì số lượng phải là số nguyên. API, ràng buộc SQL và các bản sao `KhoaHoc` phải áp dụng cùng quy tắc.
5. `so_buoi` là tổng số buổi theo chương trình đào tạo và được nhập riêng với thời lượng tháng/ngày. Không tự tính số buổi từ số tháng nếu chưa có tần suất học mỗi tuần.
6. Site mới chỉ chuyển sang hoat_dong sau khi tạo database riêng, cài schema, nạp bản sao danh mục, kiểm tra kết nối và cấu hình tài khoản quyền tối thiểu.
7. Site đóng cửa ngừng nhận giao dịch mới nhưng giữ dữ liệu lịch sử theo quy tắc lưu trữ.

**Nghiệm thu:** thiếu cấu hình hoặc lỗi một site được hiển thị cụ thể; không có trạng thái thành công toàn phần giả; các site sau đồng bộ có cùng mã và phiên bản. Đối với `MonHoc`, retry cùng `Idempotency-Key` và body tiếp tục site chưa ACK; cùng key khác body bị từ chối. Phải chạy TC-REP-01/TC-SYNC-01 trước khi kết luận đạt toàn phần.

### FS-STU-01 — Quản lý hồ sơ học viên tại cơ sở

**Người dùng:** Admin Big đọc danh sách mặc định toàn hệ thống và chọn site cụ thể khi ghi; Admin Small và Tư vấn & xếp lớp quản lý hồ sơ tại site được gán; Kế toán & Lễ tân chỉ đọc danh sách/chi tiết tại site được giao. **Phân tán:** danh sách Admin Big là `GLOBAL`, đọc `HocVien` riêng tại từng CSDL site rồi gộp trong API; chi tiết và thao tác ghi hồ sơ là `LOCAL` trên `HocVien`.

1. Admin Big có thể bỏ `site_code` khi đọc danh sách để xem toàn bộ cơ sở đang hoạt động; khi tạo/sửa/xóa/cấp tài khoản hoặc xem chi tiết, phải dùng một cơ sở cụ thể. Admin Small và nhân viên lấy cơ sở từ phiên đăng nhập; API từ chối `site_code` do các tài khoản này gửi lên. Global Query báo `complete=false` và `missing_sites` khi có site chưa đọc được.
2. Tạo hồ sơ với mã `Seq_HV` của site, `ma_co_so` và `co_so_goc` bằng site được chọn, trạng thái `dang_hoc`, `ma_tai_khoan = NULL`. Slug mặc định được chuẩn hóa từ họ tên; người tạo có thể chỉnh slug trước khi lưu. API bảo đảm slug duy nhất trong CSDL site bằng hậu tố số khi trùng. Tạo hồ sơ không tạo tài khoản hay gửi mật khẩu.
3. Admin Big/Admin Small/Tư vấn & xếp lớp được xem chi tiết và sửa họ tên, ngày sinh, giới tính (chỉ `Nam`, `Nữ`, `Khác`), điện thoại, email, địa chỉ tại đúng site. Slug đã tạo được giữ nguyên; không đổi mã, slug, site hoặc trạng thái qua form sửa; email đã liên kết tài khoản không được sửa.
4. Ảnh đại diện là tùy chọn. Sau khi lưu hồ sơ, giao diện xin upload intent có chữ ký, gửi ảnh trực tiếp lên Cloudinary rồi gọi API hoàn tất. API ràng buộc intent với người dùng, site và hồ sơ; xác minh asset, loại ảnh, dung lượng và kích thước; chỉ ghi `avatar_public_id`, `avatar_secure_url` cùng `Logs` vào `HocVien` tại site hồ sơ trong một transaction `LOCAL`. Ảnh không tạo tài khoản. Nếu lưu ảnh lỗi, hồ sơ vẫn được giữ và giao diện cho thử lại bước xác nhận khi đã tải ảnh lên.
5. Trước khi sửa hồ sơ hoặc ảnh, kiểm tra bản ghi thuộc site trong quyền người gọi. Từ chối sửa hồ sơ `da_chuyen_di` hoặc đang bị khóa bởi giao dịch chuyển `dang_xu_ly`.
6. Ghi thay đổi và `Logs` trong cùng transaction site-local. Kế toán & Lễ tân chỉ xem danh sách/chi tiết; Admin Big, Admin Small và Tư vấn & xếp lớp được ghi hồ sơ tại site có quyền.
7. DELETE của Admin Big/Admin Small/Tư vấn chỉ xóa hồ sơ chưa liên kết tài khoản, chưa có `DangKy` và chưa có lịch sử/giao dịch chuyển. Nếu có dữ liệu học tập, điểm danh, học phí hoặc lịch sử cần giữ, trả conflict; không xóa hồ sơ, bản sao tài khoản, chứng từ hay `Logs`.
8. Admin Big/Admin Small chủ động bấm `Cấp tài khoản` sau khi tạo hồ sơ. Chỉ hồ sơ đang `dang_hoc` và có email hợp lệ mới đủ điều kiện; không bắt buộc phải có `DangKy` trước khi cấp. `TaiKhoan` được ghi theo chính sách replication hiện có, `HocVien.ma_tai_khoan` ghi tại site hồ sơ, mật khẩu tạm chỉ được gửi qua email sau thao tác này. Thư ghi email làm thông tin đăng nhập chính; API vẫn chấp nhận username tương thích.

**Nghiệm thu:** danh sách mặc định của Admin Big gộp dữ liệu các site hoạt động, hiển thị site trên từng dòng và cảnh báo site thiếu; lọc một site chỉ đọc site đó; Admin Big/Admin Small/Tư vấn được CRUD hồ sơ tại đúng site; Kế toán & Lễ tân chỉ đọc và bị từ chối mọi thao tác ghi; Tư vấn/Kế toán không được cấp tài khoản; mã có tiền tố không được dùng để suy site hiện tại; slug tạo theo họ tên, chuẩn hóa và duy nhất trong site; giới tính chỉ nhận `Nam`, `Nữ`, `Khác` ở API; email/ngày sinh/điện thoại được validate ở server; tạo hồ sơ không cấp tài khoản; ảnh tùy chọn chỉ cập nhật metadata tại CSDL site hồ sơ sau khi API xác minh Cloudinary; lỗi upload không làm mất hồ sơ; xóa hồ sơ có lịch sử bị từ chối mà không mất dữ liệu; Admin có thể cấp tài khoản cho hồ sơ đang học có email hợp lệ trước khi tạo đăng ký khóa học, chỉ qua thao tác riêng và API không trả mật khẩu.

### FS-ENR-01 — Đăng ký khóa học

**Người dùng:** Admin Big chọn một site, Admin Small và Tư vấn & xếp lớp dùng site được giao. Kế toán & Lễ tân không đăng ký khóa học. **Kiểu:** LOCAL. **Site:** site hiện tại của học viên/lớp. **Bảng:** HocVien, KhoaHoc, LopHoc, DangKy, HocPhi, Logs.

**Điều kiện:** người dùng có quyền tại site; học viên đang học tại site; lớp thuộc site, nhận đăng ký và còn chỗ; học viên chưa có đăng ký còn hiệu lực trùng khóa/lớp theo quy tắc schema.

1. Nhân viên có quyền tìm học viên và chọn khóa/lớp tại cùng site; Kế toán & Lễ tân chỉ tra cứu học viên, không gửi thao tác đăng ký.
2. API lấy site từ phiên/quyền và định tuyến bằng Site Router; không nhận alias/database tùy ý từ client.
3. API kiểm tra trạng thái học viên/lớp, sức chứa, lịch xung đột, đăng ký trùng và mức học phí theo dữ liệu server.
4. Trong một transaction cục bộ, tạo DangKy, tạo HocPhi, cập nhật sĩ số nếu schema lưu sĩ số tổng hợp, ghi nhật ký.
5. API trả mã đăng ký và khoản học phí phát sinh.

**Lỗi:** dữ liệu không hợp lệ hoặc lớp đầy thì không ghi gì; lỗi ở bất kỳ bước ghi nào rollback toàn bộ transaction; request lặp không tạo đăng ký/học phí lần hai.

**Nghiệm thu:** không thể đăng ký lớp ở site khác; mọi bản ghi con ở đúng site lớp; kiểm tra đồng thời hai lượt cuối không vượt sức chứa.

**TC-CON-01 / YC-05:** hai học viên khác nhau, hai phiên độc lập, cùng lớp còn đúng một chỗ; hai yêu cầu phải chạy chồng lấp tại vùng tranh chấp. Chỉ một yêu cầu tạo `DangKy`/`HocPhi` và tăng sĩ số; yêu cầu còn lại nhận lỗi lớp đầy/xung đột theo hợp đồng, không ghi nghiệp vụ dở dang. Ghi cơ chế bảo vệ sức chứa phía API/DB và bằng chứng cạnh tranh; khóa nút giao diện không đủ chứng minh concurrency.

### FS-CLASS-01 — Mở lớp và tạo lịch học

**Người dùng:** Admin Big đọc danh sách toàn hệ thống hoặc chọn một site để quản lý; Admin Small và Tư vấn & xếp lớp thao tác lớp tại site được cấp; Kế toán & Lễ tân chỉ xem lớp/roster tại site. **Kiểu:** danh sách Admin Big là `GLOBAL`, đọc `LopHoc` cùng số liệu `DangKy` tại từng site rồi tổng hợp trong API; thao tác cơ sở là `LOCAL`. **Bảng:** KhoaHoc, GiaoVien, PhongHoc, LopHoc, BuoiHoc, DangKy, Logs.

Danh sách lớp của Admin Big mặc định đọc từng CSDL site riêng, có `site_code` trên mỗi dòng và trả `complete=false`/`missing_sites` khi thiếu site. Khi bộ lọc đang ở `Toàn hệ thống`, thao tác ghi yêu cầu chọn site cụ thể; API chỉ ghi `LOCAL`. Admin Small và Tư vấn có thể mở lớp, đăng ký/xếp lớp và phân công giáo viên; Kế toán & Lễ tân chỉ xem lớp và roster. Danh sách chọn giáo viên được đọc riêng tại site thao tác qua `GET /admin/teachers/assignment-options/`; nhân viên dùng site từ phiên đăng nhập và chỉ nhận mã cùng họ tên của giáo viên đang dạy, không nhận thông tin liên hệ/tài khoản. Tư vấn được sửa tên/sĩ số lớp trong giới hạn sức chứa; chỉ được hủy lớp `sap_mo` chưa có đăng ký và mọi buổi còn ở tương lai, trạng thái `du_kien`. Hủy mềm đặt `LopHoc.trang_thai='huy'`, giữ nguyên `LopHoc`, `BuoiHoc` và `Logs`; nếu có đăng ký hoặc lịch sử buổi học, API từ chối. Không JOIN xuyên site.

1. Nhân viên chọn khóa học, giáo viên, phòng, sức chứa, ngày bắt đầu/kết thúc, thứ trong tuần và khung giờ.
2. API kiểm tra tất cả dữ liệu thuộc site, giáo viên đang dạy, phòng khả dụng, ngày/giờ hợp lệ và không trùng lịch giáo viên/phòng.
3. Tạo LopHoc và các BuoiHoc theo mẫu lịch trong một transaction cục bộ.
4. Trả danh sách buổi đã tạo để nhân viên kiểm tra.

**Nghiệm thu:** không có buổi ngoài khoảng ngày; giờ hiển thị 24 tiếng Việt Nam; ngày kết thúc trước ngày bắt đầu bị từ chối; xung đột không tạo lớp/buổi một phần.

### FS-ROOM-01 — Quản lý phòng học

**Người dùng:** Admin Big/Small và Tư vấn & xếp lớp quản lý phòng; Kế toán & Lễ tân chỉ xem phòng tại site được giao. Danh sách của Admin Big có thể đọc toàn hệ thống; CRUD luôn chọn một site. **Kiểu:** đọc `GLOBAL` hoặc `LOCAL`; ghi `LOCAL`. **Bảng:** PhongHoc, LopHoc, BuoiHoc, DangKy, HocVien, HocPhi, Logs.

- Admin Big xem danh sách phòng qua Global Query hoặc lọc một site; Admin Small chỉ xem site trong phiên. Mỗi dòng Global mang `site_code`; nếu thiếu site, API/UI phải nêu `missing_sites` và không báo dữ liệu đầy đủ.
- Kế toán & Lễ tân và Tư vấn & xếp lớp xem phòng, số lớp và số học viên duy nhất tại site trong phiên; mở rộng phòng để xem học viên theo lớp, số phải thu/đã thu/còn nợ và trạng thái phí. Kế toán & Lễ tân chỉ xem; Tư vấn & xếp lớp được tạo/sửa/xóa phòng tại site trong phiên.
- Từ danh sách lớp trong phòng, các vai trò được cấp có thể yêu cầu gửi email nhắc cho học viên còn nợ. API tính dư nợ tại site, gửi tối đa một email cho mỗi lớp/học viên/ngày Việt Nam và ghi kết quả không chứa email/nội dung thư vào `Logs`; SMTP chấp nhận không chứng minh thư đã tới hộp thư.
- Admin có thể tạo phòng với tên và sức chứa; phòng mới ở trạng thái `hoat_dong`. Sửa tên, sức chứa hoặc trạng thái (`hoat_dong`/`bao_tri`) tại đúng site. Tên không được trùng trong cùng site; không cho giảm sức chứa thấp hơn sĩ số tối đa của lớp đang dùng phòng mặc định hoặc phòng của buổi học.
- Ghi thêm/sửa/xóa `PhongHoc` và `Logs` trong một transaction tại site được chọn; không ghi nhiều site trong một request. Admin Small không thể chọn site khác.
- Chỉ xóa vật lý phòng chưa được `LopHoc` hoặc `BuoiHoc` tham chiếu. Nếu đang được sử dụng, API từ chối với xung đột; không xóa lịch sử lớp/buổi và không bỏ qua khóa ngoại.
- Trang quản lý phòng riêng tại `/admin/rooms`; trang `/admin/classes` chỉ chọn phòng có sẵn khi mở lớp.

**Nghiệm thu:** Admin Big xem được các site hoạt động và nhận cảnh báo site thiếu; Admin Big/Small và Tư vấn đúng site thêm/sửa/xóa được phòng; Kế toán & Lễ tân ghi phòng bị từ chối; nhân viên/Admin Small vượt site bị từ chối; tên trùng hoặc sức chứa không hợp lệ nhận xung đột; phòng đang được lớp/buổi sử dụng nhận `409` và dữ liệu giữ nguyên. Email nhắc chỉ tính học viên còn nợ tại site/lớp, không gửi trùng trong ngày và kết quả SMTP được báo riêng.

### FS-CLASS-02 — Xếp học viên vào lớp hoặc đổi lớp

**Người dùng:** Admin Big chọn một site; Admin Small hoặc Tư vấn & xếp lớp tại site được giao. Kế toán & Lễ tân chỉ xem đăng ký/lớp. **Kiểu:** LOCAL. **Bảng:** HocVien, DangKy, LopHoc, Logs.

1. Nhân viên chọn đăng ký hiện hành và lớp đích.
2. API xác nhận học viên/đăng ký/lớp cùng site, lớp đích còn chỗ, lịch phù hợp, đăng ký chưa hoàn tất/hủy/chuyển đi và không tạo bản ghi trùng.
3. Cập nhật quan hệ lớp của DangKy, sĩ số lớp cũ/mới và nhật ký trong một transaction cục bộ.
4. Trả lớp cũ/mới và trạng thái đăng ký sau cập nhật.

**Lỗi:** lớp đầy, sai site, trạng thái đăng ký không cho đổi hoặc xung đột lịch thì không cập nhật sĩ số; thao tác cạnh tranh dùng khóa/version hoặc kiểm tra lại trong transaction.

**Nghiệm thu:** tổng sĩ số không âm/vượt sức chứa; không chuyển đăng ký qua site bằng chức năng đổi lớp; giữ lịch sử theo mô hình schema.

### FS-ATT-01 — Điểm danh buổi học

**Người dùng:** giáo viên được phân công; nhân viên có quyền giám sát nếu được cấu hình. **Kiểu:** LOCAL. **Bảng:** BuoiHoc, DangKy, DiemDanh, Logs.

1. Giáo viên mở buổi học thuộc lớp được phân công.
2. API trả danh sách học viên có đăng ký hợp lệ ở site của lớp.
3. Giáo viên ghi mỗi học viên một trạng thái: co_mat, tre, vang_co_phep hoặc vang_khong_phep.
4. API kiểm tra ma_buoi, đăng ký cùng lớp/site, không trùng (ma_buoi, ma_dang_ky) và thời điểm được phép điểm danh.
5. Lưu tất cả điểm danh hợp lệ trong transaction site; thao tác sửa có nhật ký người sửa/thời gian/giá trị trước-sau.

**Nghiệm thu:** giáo viên lớp khác bị 403; bản ghi trùng không nhân đôi; lỗi ghi giữa chừng rollback theo hợp đồng batch.

### FS-TUI-01 — Thu học phí tại cơ sở

**Người dùng:** Admin Big xem danh sách toàn hệ thống; Kế toán & Lễ tân xem công nợ, xem phiếu thu và ghi nhận thu/hoàn tại site được cấp; Admin Small giám sát; Tư vấn xem công nợ, gửi email nhắc phí và chỉ đổi kế hoạch đóng tại site. **Kiểu:** danh sách Admin Big là `GLOBAL`, đọc `HocPhi` cùng `DangKy`/`HocVien`/`LopHoc` riêng ở mỗi site; các thao tác còn lại là `LOCAL`. **Site:** nơi lưu HocPhi. **Bảng:** DangKy, HocPhi, PhieuThu, DotHocPhi, NhanVien, Logs.

1. Kế toán & Lễ tân và Tư vấn xem danh sách theo site; mặc định lọc khoản có số dư dương và mỗi dòng thể hiện học viên, lớp, tổng học phí, đã thu, còn lại và trạng thái.
2. Có thể tìm theo tên/mã học viên hoặc tên/mã lớp, chọn trạng thái và phân trang trên server; báo cáo tổng công nợ không chỉ cộng trang hiện tại.
3. Chỉ Kế toán & Lễ tân nhập số tiền dương không vượt quá số còn nợ, phương thức hợp lệ và ghi chú không chứa dữ liệu thanh toán nhạy cảm. Tư vấn không được ghi thu/hoàn hoặc sửa tổng học phí/giảm giá.
4. API kiểm tra quyền, trạng thái khoản phí và khóa chống gửi lặp/idempotency. Tư vấn chỉ đổi kế hoạch đóng trước lần thu đầu tiên qua API lịch học phí.
5. Trong transaction site, thêm PhieuThu loại thu, cập nhật trạng thái HocPhi, ghi audit; không sửa/xóa lịch sử phiếu đã phát hành.
6. Trả mã phiếu, số tiền, số dư và trạng thái mới.

**Nghiệm thu:** gửi lại cùng idempotency key và payload trả cùng kết quả; cùng key nhưng payload khác bị conflict; hai request cạnh tranh không thể thu vượt số dư; lỗi DB không để phiếu thu và HocPhi lệch nhau.

**Giới hạn triển khai:** thu tại quầy dùng mã phiếu site-prefixed tạo từ idempotency key để nhận diện retry; chưa có request ledger riêng. Hoàn tiền dùng cột UUID idempotency mới trong `PhieuThu` sau migration 40. Cần kiểm chứng retry sau timeout trên SQL Server của từng site trước khi kết luận nghiệm thu.

### FS-TUI-02 — Hoàn hoặc điều chỉnh học phí

**Người dùng:** Kế toán & Lễ tân có quyền hoàn; Admin Small giám sát theo phân quyền. **Kiểu:** LOCAL. **Bảng:** HocPhi, PhieuThu, DotHocPhi, NhanVien, Logs.

1. Người dùng chọn phiếu thu gốc và lý do hoàn/điều chỉnh.
2. API xác định site và số tiền có thể hoàn từ dữ liệu lưu; không cho hoàn vượt tổng số đã thu trừ số đã hoàn.
3. Trong transaction, thêm bút toán loại hoan tham chiếu phiếu gốc, cập nhật trạng thái HocPhi và audit.
4. Phiếu gốc giữ nguyên; không xóa hoặc ghi đè lịch sử.

**Nghiệm thu:** hoàn vượt mức bị từ chối; gửi lại cùng idempotency key và nội dung trả cùng phiếu, key dùng cho nội dung khác bị từ chối; tổng thu-trừ-hoàn khớp số dư và các kỳ học phí; người không có quyền không thể hoàn.

### FS-TUI-03 — Báo cáo tài chính học phí

**Người dùng:** Kế toán & Lễ tân tại site được giao; Admin Small tại site được giao; Admin Big theo site hoặc toàn hệ thống. **Kiểu:** `LOCAL` hoặc `GLOBAL`. **Bảng:** `HocPhi`, `PhieuThu`.

1. Kế toán & Lễ tân và Admin Small chỉ đọc CSDL site trong phiên; Admin Big chọn một site hoặc để trống để đọc toàn bộ site hoạt động.
2. API truy vấn độc lập từng CSDL rồi tổng hợp tại ứng dụng, trả số khoản, số khoản còn nợ, tổng phải thu, đã thu ròng, còn nợ, tổng phiếu thu và tổng phiếu hoàn.
3. Nếu thiếu site trong Global Query, trả `complete=false` cùng `missing_sites`, không trình bày phần đã đọc như tổng đầy đủ.

**Nghiệm thu:** số liệu từng site khớp `HocPhi`/`PhieuThu` tại site đó; vai trò bị giới hạn đúng phạm vi; khi một site lỗi, API và giao diện chỉ rõ kết quả chưa đầy đủ. Báo cáo hiện là snapshot tổng hợp, chưa lọc theo khoảng ngày.

### FS-PAY-01 — Thanh toán trực tuyến học phí

**Trạng thái phạm vi:** Có code/schema/API cho SePay, nhưng portal học viên và thanh toán online chưa được nhóm duyệt vào phạm vi đồ án; `SEPAY_ENABLED=false` mặc định và chưa có bằng chứng giao dịch thật. **Kiểu:** `LOCAL` tại site chứa `HocPhi`; không phải giao dịch xuyên site.

Khi nhóm duyệt phạm vi và bật tích hợp, luồng phải đáp ứng:

1. API lấy site, số tiền, loại tiền, chủ khoản nợ từ HocPhi; frontend không được quyết định giá trị này.
2. Tạo YeuCauThanhToan bền vững cùng idempotency key trước khi chuyển người dùng đến cổng. Một HocPhi chỉ có tối đa một yêu cầu còn mở theo trạng thái được chốt.
3. Reload, quay lại website hoặc đăng nhập lại chỉ đọc trạng thái đã lưu; không tự tạo lượt thanh toán mới. URL redirect/query string không chứng minh đã trả tiền.
4. Webhook phải xác minh chữ ký, merchant, amount/currency, timestamp/replay và mã giao dịch provider; callback lặp phải idempotent.
5. Chỉ sau khi callback hợp lệ và transaction site đã commit PhieuThu, HocPhi và sự kiện thanh toán mới trả trạng thái thành công.
6. Timeout hoặc DB lỗi khi kết quả cổng chưa rõ chuyển sang can_doi_soat; chặn tạo lượt mới cho đến khi đối soát/retry có kết quả rõ.
7. Hoàn online là bút toán bù trừ tham chiếu giao dịch gốc. Không lưu PAN/CVV, secret, token provider hoặc payload thô.

**Điều kiện nghiệm thu trước khi bật:** cấu hình merchant/webhook và HTTPS; đối chiếu schema hiện có `YeuCauThanhToan`/`SuKienThanhToan`; kiểm thử webhook đúng/sai chữ ký, phát lại, reload, thoát giữa chừng, timeout, lỗi database và refund. Không coi schema hoặc code là bằng chứng giao dịch đã chạy.

### FS-GRADE-01 — Nhập, sửa và xem điểm

**Người dùng:** giáo viên được phân công; Admin Small/Admin Big đọc hoặc giám sát theo quyền. **Kiểu:** LOCAL. **Bảng:** GiaoVien, LopHoc, DangKy, Diem, Logs.

1. Giáo viên mở lớp được phân công và chọn học viên có đăng ký hợp lệ.
2. Nhập điểm từ 0 đến 10 và loại điểm trong danh sách schema cho phép: giua_ky, cuoi_ky, nghe, noi, doc, viet.
3. API kiểm tra lớp/site/phân công, loại điểm và ràng buộc duy nhất (ma_dang_ky, loai_diem).
4. Tạo mới nếu chưa có; sửa nếu đã có và người dùng có quyền. Ghi giá trị cũ/mới, người sửa và thời gian trong nhật ký phù hợp.

**Nghiệm thu:** giáo viên ngoài lớp bị từ chối; điểm ngoài khoảng hoặc loại lạ bị từ chối; mỗi đăng ký không có hai điểm cùng loại; lỗi log/ghi theo thiết kế không làm mất tính nhất quán.

### FS-TRF-01 — Admin Small tạo đề nghị chuyển cơ sở

**Người dùng:** Admin Small tại site nguồn. **Kiểu:** LOCAL tạo đề nghị; có thể dùng Global để xác định bản HocVien hiện hành. **Bảng nguồn:** HocVien, HocPhi/DangKy để kiểm tra điều kiện, GiaoDichChuyenCoSo, LichSuChuyenCoSo.

1. Admin Small chọn học viên, site đích đang hoạt động và nhập lý do. Không có bước Admin Small tự xác nhận chuyển hoàn tất.
2. API lấy site nguồn từ tài khoản Admin Small, xác định bản HocVien dang_hoc hiện hành bằng định vị site; không nhận nguồn tin cậy từ client và không suy từ prefix ID.
3. Kiểm tra học viên thuộc nguồn; không có đề nghị/giao dịch mở; không còn công nợ theo quy tắc nghiệp vụ hiện hành; site đích khác nguồn và hoạt động.
4. Trong transaction nguồn, tạo GiaoDichChuyenCoSo trạng thái cho_duyet và sự kiện append-only de_nghi. Chưa tạo hồ sơ đích, chưa đánh dấu nguồn da_chuyen_di.
5. Trả mã đề nghị và trạng thái chờ duyệt để Admin Small theo dõi tại site mình.

**Lỗi:** hồ sơ không thuộc quyền, site đích không khả dụng, còn nợ, request trùng hoặc site nguồn lỗi thì không tạo đề nghị; lịch sử không bị sửa/xóa.

**Nghiệm thu:** đề nghị mới chưa làm thay đổi cơ sở hiện tại hoặc thống kê; Admin Small không thể gọi API duyệt.

### FS-TRF-02 — Admin Big xem, duyệt hoặc từ chối đề nghị

**Người dùng:** Admin Big xem hộp thư `GLOBAL` và duyệt/từ chối; Admin Small/Kế toán & Lễ tân/Tư vấn & xếp lớp chỉ đọc đề nghị tại site được giao. **Kiểu:** hộp thư `GLOBAL`; đọc của nhân viên là `LOCAL`; quyết định ghi `LOCAL` tại CSDL nguồn. **Bảng:** GiaoDichChuyenCoSo, LichSuChuyenCoSo, CoSo, HocVien, DangKy, HocPhi.

1. API truy vấn riêng các site hoạt động để tạo hộp thư; kết quả ghi rõ complete và missing_sites.
2. Admin Big đọc site hoạt động toàn cục; nhân viên cơ sở chỉ đọc nguồn trong phiên và không thể gửi site khác.
3. Mỗi dòng hiển thị công nợ lịch sử tại nguồn, tính cục bộ qua DangKy/HocPhi; không JOIN sang site đích. Không có khoản học phí thì hiện riêng, không suy ra đã đóng.
4. Nếu site nguồn không đọc được thì không cho quyết định trên đề nghị chưa tải được; không hiển thị hộp thư thiếu site như toàn bộ.
5. Khi duyệt/từ chối, API định tuyến về site nguồn đã được xác định từ đề nghị và kiểm tra quyền Admin Big.
6. Kiểm tra lại trạng thái đề nghị, học viên hiện hành, nợ, site đích và xung đột vì điều kiện có thể đổi trong lúc chờ.
7. Từ chối: ghi tu_choi, người/thời điểm/lý do và sự kiện tu_choi tại nguồn; hồ sơ học viên không đổi.
8. Duyệt: ghi trạng thái dang_xu_ly, bước da_tiep_nhan, người/thời điểm quyết định và sự kiện duyet tại nguồn. Chỉ sau commit quyết định mới giao Coordinator chạy distributed transfer.

**Nghiệm thu:** Kế toán & Lễ tân/Tư vấn đọc được đề nghị và công nợ tại site được giao nhưng không thể tạo/duyệt/từ chối/retry; Admin Small/giáo viên không được quyết định; hai Admin Big duyệt đồng thời chỉ một quyết định thắng; quyết định idempotent; không gọi coordinator chuyển nếu quyết định chưa commit.

### FS-TRF-03 — Thực hiện và phục hồi giao dịch chuyển

**Người dùng:** Coordinator chạy sau khi Admin Big duyệt; Admin Big được gọi route retry cho giao dịch chưa hoàn tất. Đây không phải thao tác tự do của Admin Small. **Kiểu:** DISTRIBUTED-TX giữa nguồn và đích. **Bảng:** GiaoDichChuyenCoSo tại nguồn; HocVien/DangKy tại nguồn; HocVien tại đích; LichSuChuyenCoSo tại site phát sinh.

1. Coordinator chỉ nhận giao dịch đã duyệt. Tải trạng thái nguồn, khóa chống lặp và bước cuối đã commit.
2. Tạo hồ sơ HocVien cùng mã ở đích trong transaction đích; giữ slug nguồn nếu chưa được dùng tại site đích, nếu trùng thì thêm hậu tố số; sao chép `avatar_public_id`/`avatar_secure_url` nếu có để ảnh tiếp tục hiển thị; ghi sự kiện tao_ho_so_dich. Bản đích phải duy nhất theo mã và ma_chuyen. Hai hồ sơ site-local có thể cùng tham chiếu một asset Cloudinary; metadata nguồn vẫn được giữ làm lịch sử.
3. Sau khi xác nhận đích commit, lưu bước da_tao_ho_so_dich tại nguồn.
4. Cập nhật nguồn: HocVien thành da_chuyen_di; đóng/đánh dấu các DangKy cũ theo trạng thái chuyen_di; cập nhật bước da_cap_nhat_nguon và ghi sự kiện.
5. Đối soát hai site; đánh dấu giao dịch hoan_tat và ghi sự kiện kết thúc. Bản nguồn được giữ lại làm lịch sử.
6. Coordinator/retry có thể chạy lại an toàn. Nếu đích chưa commit, nguồn vẫn là bản hiện hành; nếu đích đã commit, phải tiếp tục tiến về phía trước, không xóa đích. Source hiện có route retry của Admin Big; lịch chạy tự động chưa được xác nhận.

| Điểm dừng/ lỗi | Hành vi bắt buộc |
|---|---|
| Chưa được duyệt | Không tạo dữ liệu đích; không xử lý tự động |
| Trước khi đích commit | Giữ nguồn dang_hoc; lỗi tạm thời thì chờ retry, lỗi nghiệp vụ dứt điểm có trạng thái thất bại rõ |
| Đích đã commit, nguồn chưa cập nhật | Giữ dang_xu_ly; ẩn/không tính bản đích trong Global Query cho đến khi tiến trình qua mốc cập nhật nguồn; retry tiến về phía trước |
| Nguồn đã cập nhật, giao dịch chưa hoàn tất | Tính bản đích theo bước đã lưu; đối soát và hoàn thành trạng thái |
| Đích hoặc nguồn không phản hồi | Không báo hoàn tất; lưu trạng thái cần retry/đối soát và không xóa bản ghi đã commit |

**Nghiệm thu:** retry không tạo hồ sơ đích thứ hai; nếu hồ sơ có ảnh thì metadata được giữ tại nguồn và sao chép sang đích; sau hoàn tất chỉ bản đích có trạng thái dang_hoc; bản nguồn da_chuyen_di còn nguyên; không tuyên bố ACID nguyên tử xuyên hai CSDL.

### FS-REPORT-01 — Thống kê học viên theo cơ sở

**Người dùng:** Admin Big toàn hệ thống; Admin Small tại site được giao. **Kiểu:** LOCAL cho một site, GLOBAL cho nhiều site. **Bảng:** CoSo, HocVien và trạng thái giao dịch chuyển nếu cần.

1. API xác định phạm vi theo vai trò. Admin Small không thể yêu cầu một site khác; Admin Big có thể chọn site hoặc toàn hệ thống.
2. Mỗi site được truy vấn độc lập; API tổng hợp kết quả ở ứng dụng, không JOIN giữa CSDL.
3. Đếm bản HocVien dang_hoc; không cộng da_chuyen_di, bao_luu, nghi_hoc vào chỉ tiêu đang học.
4. Trong giai đoạn chuyển dở, áp dụng quy tắc bước cuối: trước khi nguồn cập nhật thì tính nguồn và ẩn đích; sau khi nguồn cập nhật thì tính đích.
5. Nếu một site lỗi, trả phần kết quả đã đọc kèm complete=false và missing_sites; giao diện phân biệt số liệu một phần.

**Nghiệm thu:** tổng theo site khớp các truy vấn cục bộ; trạng thái chuyển không đếm đôi; site mất kết nối không bị biến thành số 0 im lặng.

### FS-AUD-01 — Nhật ký thao tác và đồng bộ

**Người dùng:** hệ thống ghi tự động; Admin Big đọc toàn cục, Admin Small đọc site được giao theo chính sách. **Kiểu:** Local theo site phát sinh; Global khi Admin Big xem nhiều site.

`Logs` lưu audit và ACK đồng bộ theo site; source có luồng replication cho `MonHoc` (được chọn làm YC-03 tối thiểu) và service riêng cho `KhoaHoc`, ghi ACK cùng transaction cập nhật từng bản sao. `CoSo` chưa có fan-out runtime đầy đủ và các luồng `TaiKhoan` chưa gom về một writer chung. Các cơ chế cần TC-REP-01/TC-SYNC-01 chạy thật; nhật ký chuyển nằm ở `LichSuChuyenCoSo` và chỉ append-only.

Không ghi password/hash, token, cookie, header xác thực, secret Cloudinary/SMTP/OAuth/SQL, PAN/CVV hay payload thanh toán thô. Không trả nội dung nội bộ trong lỗi API.

**Nghiệm thu:** log nghiệp vụ có thể truy vết theo mã log/tài khoản và bộ lọc ngày Việt Nam nhưng không chứa secret; Admin Big đọc toàn cục hoặc một site, Admin Small chỉ đọc site được gán; site lỗi phải được báo là dữ liệu chưa đầy đủ. API chỉ trả mã log, thời điểm, site, tài khoản, loại, thao tác, bảng, mã bản ghi, kết quả và site đích; không trả IP, hash định danh/IP, token, JSON dữ liệu trước/sau, ghi chú tự do hay nội dung lỗi nội bộ.

### FS-NOTIF-01 — Tạo thông báo quản trị

**Người dùng:** Admin Big và Admin Small. **Kiểu:** Admin Big dùng `REPLICATED-WRITE` ở tầng API tới các site đang hoạt động; Admin Small dùng `LOCAL` tại site được gán. **Bảng:** `ThongBao` và `Logs` tại từng site được ghi.

Người tạo nhập nhóm thông báo, mức độ, nhóm nhận, tiêu đề, nội dung và đường dẫn quản trị tùy chọn. API kiểm tra role từ phiên, giới hạn độ dài/giá trị, chỉ chấp nhận đường dẫn nội bộ `/admin/...`, và chỉ cho Admin Small nhắm `admin_all` hoặc `admin_small`. Admin Big gửi cùng thông báo tới các site hoạt động; Admin Small không được chỉ định site khác. Schema hiện có chỉ hỗ trợ nhóm nhận Admin Big, Admin Small hoặc cả hai, không dùng chức năng này để gửi cho học viên, giáo viên hay nhân viên.

Mỗi site ghi `ThongBao` và audit `Logs` trong transaction cục bộ. Bắt buộc `Idempotency-Key`; retry phải dùng lại cùng key và body. Nếu thiếu site, API trả trạng thái chưa hoàn tất cùng danh sách site thiếu để có thể tiếp tục; không tuyên bố ACID xuyên site và không báo thành công toàn phần. Không tạo CSDL/bảng mới, không lưu trạng thái đã đọc.

**Nghiệm thu:** người không phải Admin nhận 403; Admin Small chỉ tạo ở site của mình; Admin Big phát tới toàn bộ site hoạt động; nội dung sai/đường dẫn ngoài admin bị từ chối; gửi lại cùng key không tạo trùng, đổi body với key cũ nhận 409; khi một site lỗi, response liệt kê site thiếu và retry cùng request hoàn tất mà không nhân đôi các site đã ghi.

## 7. Quy tắc trạng thái nghiệp vụ

Tên trạng thái cuối cùng phải khớp check constraint trong schema. Bảng dưới tóm tắt hành vi dự kiến, không thay thế enum/ràng buộc chính thức.

| Đối tượng | Trạng thái liên quan | Quy tắc |
|---|---|---|
| Cơ sở | chuan_bi, hoat_dong, dong_cua | Chỉ hoat_dong nhận giao dịch mới và tham gia đồng bộ bắt buộc; dong_cua vẫn giữ lịch sử. |
| Học viên | dang_hoc, bao_luu, da_chuyen_di, nghi_hoc | Chỉ bản dang_hoc là hiện hành cho học tại site; không xóa bản da_chuyen_di. |
| Lớp | sap_mo, dang_hoc, ket_thuc, huy | Chỉ trạng thái cho phép mới nhận đăng ký; trạng thái cụ thể phải theo schema. |
| Đăng ký | da_dang_ky, dang_hoc, hoan_thanh, huy, chuyen_di | Không coi đăng ký đã hủy/chuyển/hoàn thành là đăng ký đang hoạt động. |
| Học phí | chua_dong, dong_mot_phan, da_dong, hoan_tien | Trạng thái suy ra từ phải thu, tổng thu và hoàn theo quy tắc kế toán. |
| Đề nghị chuyển | cho_duyet, tu_choi, dang_xu_ly, hoan_tat/that_bai theo schema | Chỉ cho_duyet chờ quyết định; chỉ đã duyệt mới chạy chuyển; lịch sử quyết định được giữ lại. |
| Giao dịch thanh toán trực tuyến | `cho_thanh_toan`, `da_thanh_toan`, `het_han`, `can_doi_soat`, `da_huy` | SePay có code/schema; tích hợp mặc định tắt, phạm vi chưa duyệt và chưa có bằng chứng giao dịch thật. |

## 8. Hành vi lỗi và thông tin trả về

| Tình huống | Kết quả chức năng |
|---|---|
| Chưa đăng nhập | Từ chối yêu cầu riêng tư; trả trạng thái xác thực theo hợp đồng API. |
| Đã đăng nhập nhưng sai vai trò/phạm vi | Từ chối; không tiết lộ bản ghi thuộc site khác. |
| Request không hợp lệ | Nêu lỗi theo trường/quy tắc có thể sửa; không ghi dữ liệu. |
| Bản ghi không tồn tại hoặc không thuộc site | Trả not found/forbidden theo chính sách không dò dữ liệu; không truy vấn site ngoài quyền. |
| Trùng khóa nghiệp vụ/idempotency | Trả kết quả cũ nếu cùng request hợp lệ; conflict nếu cùng key nhưng nội dung khác hoặc trạng thái đã đổi. |
| Site trong phạm vi GLOBAL không phản hồi | Trả kết quả từng site, complete=false, missing_sites; không nói tổng đầy đủ. |
| Một site lỗi trong REPLICATED-WRITE | Báo thất bại/chưa hoàn tất; giữ trạng thái đồng bộ và cho retry/đối soát. |
| Lỗi transaction LOCAL | Rollback dữ liệu cùng site; trả lỗi có mã request, không để trạng thái nửa chừng. |
| Coordinator dừng giữa DISTRIBUTED-TX | Đọc trạng thái đã lưu và tiếp tục theo mốc commit; không xóa dữ liệu đã commit. |
| Rate limit | Trả 429, Retry-After; không khóa tài khoản vô thời hạn. |
| Lỗi hệ thống | Không trả SQL/stack trace/secret; ghi log đã làm sạch. |

Response thành công/lỗi cuối cùng được chốt trong specs/api.md. Response GLOBAL phải có trường thể hiện độ đầy đủ và site thiếu; response payment/transfer phải phân biệt trạng thái cuối, đang xử lý và cần đối soát.

## 9. Traceability với yêu cầu môn học

| Yêu cầu đề tài | Yêu cầu FS | Dữ liệu chính | Kiểu phân tán |
|---|---|---|---|
| Đăng ký khóa học | FS-ENR-01 | HocVien, LopHoc, DangKy, HocPhi | LOCAL |
| Xếp lớp | FS-CLASS-02 | HocVien, LopHoc, DangKy | LOCAL |
| Chuyển cơ sở | FS-TRF-01, FS-TRF-02, FS-TRF-03 | HocVien, GiaoDichChuyenCoSo, LichSuChuyenCoSo, DangKy | LOCAL + GLOBAL + DISTRIBUTED-TX |
| Đóng học phí | FS-TUI-01; FS-PAY-01 nếu sau này duyệt online | HocPhi, PhieuThu | LOCAL |
| Quản lý điểm | FS-GRADE-01 | GiaoVien, DangKy, Diem | LOCAL |
| Thống kê học viên theo cơ sở | FS-REPORT-01 | CoSo, HocVien, trạng thái chuyển | LOCAL/GLOBAL |

## 10. Tiêu chí nghiệm thu tổng thể

### Đối chiếu yêu cầu chung ngoài sáu nghiệp vụ

| Yêu cầu chung | Phần chức năng/thiết kế liên quan | Bằng chứng bắt buộc |
|---|---|---|
| YC-01: 2–4 site | FS-SITE-01, định tuyến và schema; mặc định 3 site | TC-SITE-01: DB/alias và topology thực tế |
| YC-02: phương pháp phân mảnh | FS-CLASS-01, FS-ENR-01; ngang `LopHoc`, dẫn xuất `DangKy` | TC-FRAG-01: đầy đủ, không giao nhau, tái thiết |
| YC-03: phương pháp replication | FS-SITE-01, FS-ACC-01, FS-EMP-01; bảng dùng chung theo schema | TC-REP-01: một thay đổi thực tế truyền đến các bản sao |
| YC-04: distributed transaction | FS-TRF-01/02/03 | TC-DTX-01: thay đổi hai site, lỗi trước/sau commit đích và recovery |
| YC-05: concurrency | FS-ENR-01; kiểm soát cập nhật sức chứa trong site | TC-CON-01: hai phiên tranh chỗ cuối, chỉ một yêu cầu thành công |
| YC-06: distributed query | FS-REPORT-01; hộp thư FS-TRF-02 | TC-DQ-01: truy vấn từng site, gộp và thông báo site thiếu |
| YC-07: đồng bộ | FS-SITE-01, FS-AUD-01 | TC-SYNC-01: site lỗi, retry/đối soát, không ghi trùng |

Ma trận này bổ sung ma trận sáu nghiệp vụ ở mục 9; không thay thế yêu cầu chức năng nào. Các bước chi tiết nằm trong [tài liệu kiểm chứng](../docs/QLTTNN-Yeu-Cau-Chung-Va-Kiem-Chung.md).

### Điều kiện hoàn tất

Một chức năng chỉ được đánh dấu hoàn tất khi đáp ứng tất cả mục áp dụng:

1. Đúng vai trò, bản ghi và phạm vi site; thử sửa role/site trong request không vượt quyền.
2. Đọc/ghi đúng site và đúng loại bảng theo schema; không có cross-site JOIN/FK hoặc database nghiệp vụ trung tâm.
3. Kiểm tra được luồng thành công và các lỗi chính; lỗi không để dữ liệu sai hoặc nửa ghi.
4. Gửi lặp/đồng thời không tạo đăng ký, phiếu thu, điểm danh, quyết định hoặc hồ sơ chuyển trùng.
5. Site lỗi được thể hiện đúng; GLOBAL không giả làm đủ dữ liệu, REPLICATED-WRITE không báo toàn phần khi thiếu bản sao.
6. Mọi thao tác quan trọng có nhật ký đã lọc thông tin nhạy cảm.
7. UI có loading, empty, error, disabled và trạng thái thành công phù hợp; API vẫn là nơi thực thi validation/quyền.
8. Chạy kiểm tra cần thiết cho phần thay đổi: test, lint/typecheck/build theo repo; kiểm tra API và truy vấn SQL tại từng site bị ảnh hưởng.
9. Ghi rõ môi trường, kịch bản, kết quả và phần chưa thử. Không tuyên bố hiệu năng ms hoặc không còn bug khi chưa đo/chạy.
10. Cập nhật README, API/UI spec, schema/script/migration và tài liệu liên quan nếu thay đổi làm chúng lệch nhau.
11. Với phần liên quan, có mã YC/TC và kết quả thật; nghiệm thu toàn đồ án phải đủ YC-01–YC-07. Phải chứng minh concurrency bằng hai phiên thực sự cạnh tranh và replication bằng truyền thay đổi, không chỉ seed hay thao tác tuần tự.

## 11. Các quyết định và khoảng trống còn phải chốt

| Mã | Việc còn phải quyết định hoặc kiểm chứng | Tài liệu/bảng bị ảnh hưởng |
|---|---|---|
| OPEN-01 | Chuẩn hóa response lỗi, pagination/filter/sort và idempotency thu/hoàn tại quầy; schema chưa có request ledger bền vững cho phiếu thu | `specs/api.md`, `PhieuThu`, giao diện thu phí |
| OPEN-02 | Rate limit bền vững khi chạy nhiều worker và ngưỡng bcrypt theo benchmark | API settings/deployment |
| OPEN-03 | Tiến trình/retry khi tạo tài khoản và hồ sơ site lỗi một phần; cần thống nhất cách vận hành, email và đối soát | `TaiKhoan`, hồ sơ site, Coordinator |
| OPEN-04 | Có đưa portal tự phục vụ học viên vào phạm vi đồ án hay không; code/schema hiện có nhưng chưa được duyệt. Admin CRUD/cấp tài khoản đã tách riêng tại FS-STU-01 | README, schema, API, UI |
| OPEN-05 | Phạm vi vận hành SePay, merchant/webhook/HTTPS và đối soát; schema/API đã có nhưng tích hợp mặc định tắt | `YeuCauThanhToan`, `SuKienThanhToan`, API/UI |
| OPEN-06 | Cấu hình/tích hợp thật và chính sách dọn asset mồ côi cho Cloudinary; metadata avatar nằm trong `TaiKhoan` (nhân bản) và `HocVien` (site-local). Ảnh học viên có thể được cùng tham chiếu ở nguồn/đích sau chuyển nên chưa tự xóa asset cũ; không có `MediaAsset` | API media, `TaiKhoan`, `HocVien`, môi trường |
| OPEN-07 | Bổ sung runtime replication cho `CoSo` và thống nhất một điểm vào cho mọi luồng ghi `TaiKhoan`; `MonHoc`/`KhoaHoc` đã có service | README, schema, service dùng chung |
| OPEN-08 | Xác nhận với giảng viên mức bảo đảm của Coordinator chuyển cơ sở; nếu cần DBMS-managed transaction thì triển khai và kiểm thử bổ sung | README, tài liệu giao dịch, YC-04 |
| OPEN-09 | Chạy TC-SITE/FRAG/REP/SYNC/DTX/CON/DQ trên SQL Server site và lưu bằng chứng; còn thiếu outage/recovery, lỗi trước/sau commit đích, concurrency hai phiên và site thiếu | Ma trận trạng thái, YC/TC, evidence |
| OPEN-10 | Đo p50/p95 trên môi trường, kích thước dữ liệu và số site đã thống nhất | `specs/api.md`, `specs/ui-ux.md` |
Không tự coi các mục OPEN là đã chốt. Khi nhóm thống nhất, cập nhật các tài liệu liên quan trong cùng thay đổi và bổ sung tiêu chí nghiệm thu cụ thể.

## 12. Trạng thái triển khai hiện tại

Tình trạng source, các tích hợp phụ thuộc môi trường, topology và bằng chứng từng yêu cầu được duy trì trong [ma trận trạng thái triển khai](../docs/Trang-Thai-Trien-Khai.md) và [ma trận YC/TC](../docs/QLTTNN-Yeu-Cau-Chung-Va-Kiem-Chung.md). Đây là trạng thái đã ghi nhận trong tài liệu, không phải kết quả chạy mới của lần cập nhật FS này. Chỉ kết luận đạt yêu cầu môn học khi có bằng chứng cho đủ các kịch bản; có module API, schema hoặc unit test riêng lẻ chưa đủ.
