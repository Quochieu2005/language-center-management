# Đặc tả chức năng hệ thống

**Tên hệ thống:** Quản lý trung tâm đào tạo ngoại ngữ

**Môn học:** Cơ sở dữ liệu phân tán

**Phiên bản:** 1.0

**Trạng thái:** Bản đặc tả nền để nhóm triển khai và nghiệm thu; các chức năng nghiệp vụ chưa được xác nhận là đã có trong source.

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
- Phân quyền Admin Big, Admin Small, lễ tân, kế toán và giáo viên.
- Đăng nhập nội bộ; thiết kế đăng nhập Google/Facebook và khôi phục mật khẩu theo các ràng buộc bảo mật trong tài liệu.
- Phân mảnh ngang theo site, phân mảnh dẫn xuất, nhân bản dữ liệu dùng chung, Global Query và điều phối chuyển cơ sở.
- Nhật ký thao tác, trạng thái đồng bộ và kiểm chứng các kịch bản site lỗi.

### 2.2. Ngoài phạm vi hiện được chốt

- Tài khoản/portal để học viên tự đăng nhập, tự đăng ký hoặc tự thanh toán. Chỉ đưa vào sau khi nhóm duyệt và cập nhật đồng bộ schema, API, UI và FS.
- Một nhà cung cấp thanh toán trực tuyến cụ thể. Chưa chốt cổng, thông tin merchant, webhook và quy trình đối soát thực tế.
- Khẳng định transaction ACID nguyên tử xuyên hai SQL Server độc lập cho chuyển cơ sở. Thiết kế hiện tại là điều phối có trạng thái, idempotency và phục hồi tiến về phía trước.
- Xóa cứng học viên, phiếu thu, điểm, điểm danh hoặc lịch sử nghiệp vụ đã phát sinh.

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
3. Bảng dùng chung theo schema hiện tại gồm CoSo, MonHoc, KhoaHoc, TaiKhoan và TaiKhoanLienKetOAuth; các thao tác ghi phải qua một service đồng bộ chung.
4. HocVien, GiaoVien, NhanVien, PhongHoc, LopHoc là các bảng phân mảnh theo cơ sở. BuoiHoc, DangKy, DiemDanh, HocPhi, PhieuThu và Diem ở cùng site với lớp/đăng ký cha.
5. GiaoDichChuyenCoSo lưu trạng thái tại site nguồn. LichSuChuyenCoSo, NhatKyHeThong và NhatKyDongBo là nhật ký cục bộ theo nơi phát sinh; nhật ký lịch sử chỉ được thêm.
6. Tiền tố mã chỉ cho biết site tạo mã. Muốn tìm site hiện tại của học viên phải định vị bản dang_hoc, không suy ra từ mã.
7. Global Query không ghi bản tổng hợp trở lại CSDL nghiệp vụ. Nếu thiếu một site trong phạm vi, response phải ghi complete=false và liệt kê missing_sites.
8. Với REPLICATED-WRITE, không báo thành công toàn phần nếu một site bắt buộc chưa nhận được bản ghi. Lưu kết quả từng site và hỗ trợ retry/đối soát an toàn.

## 4. Vai trò và quyền

Quyền phải được xác định từ danh tính đã xác thực ở server. Frontend chỉ ẩn/hiện thao tác theo quyền để hỗ trợ người dùng; API vẫn phải kiểm tra quyền trên từng request và bản ghi.

| Vai trò | Biểu diễn theo schema hiện tại | Phạm vi |
|---|---|---|
| Admin Big | TaiKhoan.vai_tro=admin, ma_co_so=NULL | Toàn hệ thống |
| Admin Small | TaiKhoan.vai_tro=nhan_vien, ma_co_so là site được giao; NhanVien.chuc_vu=quan_ly_co_so | Một site được giao |
| Lễ tân | Tài khoản nhân viên, chức vụ lễ tân | Hồ sơ, đăng ký và xếp lớp tại site |
| Kế toán | Tài khoản nhân viên, chức vụ kế toán | Công nợ, thu/hoàn và phiếu thu tại site |
| Giáo viên | TaiKhoan.vai_tro=giao_vien, liên kết hồ sơ GiaoVien | Lớp/buổi được phân công |
| Học viên | Chưa có tài khoản/portal trong phạm vi đã chốt | Không đăng nhập trực tiếp |
| Khách | Chưa xác thực | Chỉ xem nội dung công khai được phép |

### 4.1. Ma trận quyền chức năng

| Chức năng | Admin Big | Admin Small | Lễ tân | Kế toán | Giáo viên | Học viên |
|---|---:|---:|---:|---:|---:|---:|
| Quản lý cơ sở và danh mục dùng chung | Có | Đọc theo nhu cầu | Không | Không | Không | Không |
| Quản lý Admin Small/tài khoản nội bộ | Có | Không | Không | Không | Không | Không |
| Hồ sơ học viên tại cơ sở | Toàn hệ thống theo quyền | Site được giao | Site làm việc | Đọc tối thiểu theo nghiệp vụ | Học viên thuộc lớp được giao | Không |
| Đăng ký và xếp lớp | Giám sát/toàn hệ thống | Site được giao | Site làm việc | Không | Không | Không |
| Thu/hoàn học phí | Giám sát theo quyền | Site được giao | Không mặc định | Site làm việc | Không | Không |
| Điểm danh và điểm | Giám sát/đọc theo quyền | Site được giao | Không | Không | Chỉ lớp được phân công | Không |
| Tạo đề nghị chuyển | Có thể theo quy trình được duyệt | Chỉ học viên ở site mình | Không mặc định | Không | Không | Không |
| Duyệt/từ chối đề nghị chuyển | Có | Không | Không | Không | Không | Không |
| Thống kê | Toàn hệ thống | Site được giao | Không mặc định | Báo cáo tài chính được cấp | Lớp được giao nếu có | Không |

Không dùng vai trò do client gửi để cấp quyền. Không cho Admin Small truy cập dữ liệu site khác bằng cách đổi mã site trong URL/body. Không để giáo viên đọc/ghi lớp chưa được phân công.

## 5. Quy tắc dùng chung cho mọi chức năng

### 5.1. Kiểm tra dữ liệu và bảo mật

- Dùng Django ORM; nếu phải dùng SQL thô thì truyền tham số. Không nối chuỗi input vào câu SQL. Tên cột, sort và filter động lấy từ allowlist.
- Kiểm tra kiểu, độ dài, miền giá trị, quan hệ giữa trường, trạng thái bản ghi và quyền sở hữu/site tại API. Validation ở giao diện không thay thế validation server.
- Mật khẩu lưu bằng hash bcrypt qua cấu hình Django phù hợp; không lưu/ghi log mật khẩu gốc, hash, token, cookie, khóa ký hay secret.
- Phản hồi login, đăng ký và quên mật khẩu không tiết lộ tài khoản/email có tồn tại. Áp dụng rate limit theo IP và định danh; trả 429 cùng Retry-After.
- Ảnh nhị phân chỉ được đưa lên Cloudinary; không commit ảnh tải lên vào source hoặc thư mục media. Chỉ bật upload sau khi schema có metadata và API kiểm tra quyền, MIME thực tế, dung lượng và chữ ký upload.
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

Trạng thái của mọi yêu cầu trong bảng dưới là **đặc tả, chưa triển khai**, trừ khi một mục ghi rõ khác. Theo trạng thái hiện tại của API project README, chỉ endpoint liveness đang hoạt động; chưa có endpoint nghiệp vụ.

### FS-PUB-01 — Xem nội dung công khai

**Người dùng:** khách, người dùng chưa đăng nhập. **Phân tán:** đọc bảng dùng chung hoặc truy vấn đọc phù hợp; không có quyền đọc hồ sơ nội bộ.

1. Người dùng xem trang chủ, danh sách/chi tiết khóa học và thông tin cơ sở đã được nhóm duyệt công khai.
2. Giao diện lấy dữ liệu qua API, không chứa dữ liệu khóa học/địa chỉ/học phí/đánh giá tự bịa.
3. Nếu một nguồn dữ liệu công khai lỗi, giao diện hiển thị trạng thái lỗi có thể thử lại, không giả lập dữ liệu thành công.

**Nghiệm thu:** trang công khai không yêu cầu đăng nhập; API không trả hồ sơ học viên, thông tin tài khoản hoặc dữ liệu nội bộ.

### FS-AUTH-01 — Đăng nhập tài khoản nội bộ

**Người dùng:** Admin Big, Admin Small, nhân viên, giáo viên. **Phân tán:** tra cứu bản TaiKhoan nhân bản; xác thực tại API.

**Điều kiện:** tài khoản tồn tại, mật khẩu khớp, trạng thái hoat_dong; Admin Big có ma_co_so NULL; nhân viên/giáo viên có site và hồ sơ hợp lệ.

1. Người dùng nhập tên đăng nhập hoặc email và mật khẩu trên một cửa đăng nhập chung.
2. API chuẩn hóa định danh, áp rate limit, tìm tài khoản trên các site theo cơ chế Global/định vị đã thống nhất, xác minh hash bcrypt.
3. API kiểm tra trạng thái tài khoản, vai trò, site và hồ sơ nhân sự. Không cho client chọn vai trò.
4. API tạo phiên đăng nhập an toàn; frontend chuyển người dùng đến workspace phù hợp.
5. Ghi sự kiện đăng nhập thành công/thất bại ở nơi quy định, không ghi mật khẩu hoặc token.

**Lỗi:** trả lỗi chung khi sai định danh/mật khẩu; 429 khi vượt giới hạn; từ chối tài khoản khóa/vô hiệu; nếu site cần tra cứu mất kết nối thì báo lỗi dịch vụ, không coi như tài khoản không tồn tại.

**Nghiệm thu:** cùng một form phục vụ mọi vai trò; đổi trường role/site trong request không nâng quyền; cookie phiên có HttpOnly, Secure khi HTTPS, SameSite và CSRF phù hợp; logout thu hồi phiên.

### FS-AUTH-02 — Đăng nhập Google/Facebook

**Trạng thái:** đề xuất chưa bật. **Phân tán:** đọc TaiKhoanLienKetOAuth và TaiKhoan qua Global; liên kết/thu hồi danh tính là Replicated-Write.

1. Người dùng chọn Google hoặc Facebook.
2. Backend tạo state/nonce chống CSRF/replay và khởi tạo OAuth Authorization Code flow.
3. Callback server xác minh state, code, issuer/audience, chữ ký/token và provider subject.
4. Chỉ đăng nhập nếu provider subject đã liên kết với tài khoản nội bộ còn hoạt động.
5. Không tự tạo tài khoản, không tự liên kết bằng email trùng nhau, không tin profile do browser gửi.

**Nghiệm thu:** callback lỗi/state không hợp lệ bị từ chối; access/refresh token của provider không lưu vào TaiKhoanLienKetOAuth hoặc log; một provider identity không thể gắn hai tài khoản.

**Điều kiện mở chức năng:** cấu hình OAuth thật, HTTPS callback, quản lý session/revoke, migration OAuth ở mọi CSDL cũ và kiểm thử provider. API hiện chưa triển khai endpoint OAuth.

### FS-AUTH-03 — Quên và đặt lại mật khẩu

**Người dùng:** tài khoản nội bộ. **Phân tán:** yêu cầu tìm tài khoản qua site; token cục bộ; đổi TaiKhoan bằng Replicated-Write.

1. Người dùng gửi email/định danh đã đăng ký.
2. API luôn trả thông báo chung; nếu có tài khoản, tạo token ngẫu nhiên một lần, lưu hash và hạn dùng 15 phút tại site chịu trách nhiệm, rồi gửi liên kết qua SMTP.
3. Người dùng mở liên kết, nhập mật khẩu mới; API kiểm tra token, hạn, trạng thái và chính sách mật khẩu.
4. API cập nhật hash bcrypt tới tất cả site hoạt động bằng service đồng bộ chung, đánh dấu token đã dùng và thu hồi phiên cũ.

**Lỗi:** token sai/hết hạn/đã dùng không đổi mật khẩu; nếu replicated write chưa hoàn tất thì không báo thành công và lưu trạng thái để đối soát; giới hạn spam theo IP/email.

**Nghiệm thu:** token thô chỉ xuất hiện trong liên kết gửi người dùng, không lưu/log; cùng một token chỉ dùng một lần; email không tiết lộ account existence.

**Điều kiện mở chức năng:** SMTP settings hiện có nhưng API gửi thư và endpoint reset chưa triển khai. Kiểm thử gửi thật cần tài khoản SMTP cục bộ, không ghi secret vào repo.

### FS-ACC-01 — Tạo và phân công tài khoản nội bộ

**Người dùng:** Admin Big. **Phân tán:** TaiKhoan Replicated-Write; hồ sơ NhanVien/GiaoVien Local tại site được giao.

1. Admin Big nhập thông tin nhân sự, vai trò nội bộ, site, chức vụ và trạng thái dự kiến.
2. API kiểm tra site hoạt động, chức vụ hợp lệ, email/tên đăng nhập duy nhất toàn hệ thống và quyền Admin Big.
3. API tạo định danh tài khoản một lần, bản sao TaiKhoan theo chính sách nhân bản và hồ sơ nhân sự tại site được phân công.
4. Sau khi hoàn tất, gửi liên kết kích hoạt/đặt mật khẩu dùng một lần; không tự đặt mật khẩu gửi qua email.
5. Nếu một bước nhiều site lỗi, ghi tiến trình; không cho đăng nhập bằng tài khoản mới ở trạng thái tạo dở; có thao tác retry/đối soát hoặc vô hiệu hóa an toàn.

**Quy tắc vai trò:** Admin Big dùng admin và không có site; Admin Small là nhân viên chức vụ quan_ly_co_so và chỉ một site; giáo viên dùng vai trò giao_vien và liên kết hồ sơ GiaoVien.

**Nghiệm thu:** trùng username/email bị chặn toàn hệ thống; nhân viên/giáo viên không thể đổi site qua client; thao tác tạo dở không tạo tài khoản hoạt động một phần.

**Điều kiện mở chức năng:** schema hiện có TaiKhoan nhưng chưa có luồng tạo tài khoản/invitation ledger và trạng thái kích hoạt đủ dùng. Cập nhật schema/API trước khi triển khai.

### FS-SITE-01 — Quản lý cơ sở và danh mục dùng chung

**Người dùng:** Admin Big. **Phân tán:** đọc/ghi CoSo, MonHoc, KhoaHoc bằng Replicated-Write.

1. Admin Big tạo hoặc cập nhật cơ sở, môn học, khóa học, giá chuẩn và trạng thái.
2. API kiểm tra mã ổn định, quan hệ môn-khóa, miền dữ liệu và không cho đóng site đang có nghiệp vụ mở mà chưa xử lý.
3. Service đồng bộ phát cùng mã/phiên bản tới mọi site hoạt động, ghi NhatKyDongBo theo từng site.
4. Site mới chỉ chuyển sang hoat_dong sau khi tạo database riêng, cài schema, nạp bản sao danh mục, kiểm tra kết nối và cấu hình tài khoản quyền tối thiểu.
5. Site đóng cửa ngừng nhận giao dịch mới nhưng giữ dữ liệu lịch sử theo quy tắc lưu trữ.

**Nghiệm thu:** thiếu cấu hình hoặc lỗi một site được hiển thị cụ thể; không có trạng thái thành công toàn phần giả; các site sau đồng bộ có cùng mã và phiên bản danh mục.

### FS-STU-01 — Quản lý hồ sơ học viên tại cơ sở

**Người dùng:** Admin Small/lễ tân tại site; Admin Big theo phạm vi được cấp. **Phân tán:** Local trên HocVien.

1. Nhân viên tạo hoặc cập nhật thông tin định danh/liên hệ học viên tại site được phép.
2. API tạo mã theo quy ước site tạo bản ghi; ghi ma_co_so hiện tại, co_so_goc và trạng thái.
3. Trước khi sửa, kiểm tra bản ghi thuộc site trong quyền người gọi. Từ chối sửa hồ sơ đang bị khóa bởi giao dịch chuyển đã duyệt/đang xử lý, trừ thao tác phục hồi.
4. Lưu thay đổi và NhatKyHeThong trong transaction site.
5. Hồ sơ đã có đăng ký/thu/điểm không được xóa cứng; dùng trạng thái nghiệp vụ phù hợp.

**Nghiệm thu:** Admin Small không đọc/sửa hồ sơ site khác; mã có tiền tố không được dùng để suy site hiện tại; email/điện thoại được validate ở server.

### FS-ENR-01 — Đăng ký khóa học

**Người dùng:** Admin Small hoặc lễ tân. **Kiểu:** LOCAL. **Site:** site hiện tại của học viên/lớp. **Bảng:** HocVien, KhoaHoc, LopHoc, DangKy, HocPhi, NhatKyHeThong.

**Điều kiện:** người dùng có quyền tại site; học viên đang học tại site; lớp thuộc site, nhận đăng ký và còn chỗ; học viên chưa có đăng ký còn hiệu lực trùng khóa/lớp theo quy tắc schema.

1. Nhân viên tìm học viên và chọn khóa/lớp tại cùng site.
2. API lấy site từ phiên/quyền và định tuyến bằng Site Router; không nhận alias/database tùy ý từ client.
3. API kiểm tra trạng thái học viên/lớp, sức chứa, lịch xung đột, đăng ký trùng và mức học phí theo dữ liệu server.
4. Trong một transaction cục bộ, tạo DangKy, tạo HocPhi, cập nhật sĩ số nếu schema lưu sĩ số tổng hợp, ghi nhật ký.
5. API trả mã đăng ký và khoản học phí phát sinh.

**Lỗi:** dữ liệu không hợp lệ hoặc lớp đầy thì không ghi gì; lỗi ở bất kỳ bước ghi nào rollback toàn bộ transaction; request lặp không tạo đăng ký/học phí lần hai.

**Nghiệm thu:** không thể đăng ký lớp ở site khác; mọi bản ghi con ở đúng site lớp; kiểm tra đồng thời hai lượt cuối không vượt sức chứa.

**TC-CON-01 / YC-05:** hai học viên khác nhau, hai phiên độc lập, cùng lớp còn đúng một chỗ; hai yêu cầu phải chạy chồng lấp tại vùng tranh chấp. Chỉ một yêu cầu tạo `DangKy`/`HocPhi` và tăng sĩ số; yêu cầu còn lại nhận lỗi lớp đầy/xung đột theo hợp đồng, không ghi nghiệp vụ dở dang. Ghi cơ chế bảo vệ sức chứa phía API/DB và bằng chứng cạnh tranh; khóa nút giao diện không đủ chứng minh concurrency.

### FS-CLASS-01 — Mở lớp và tạo lịch học

**Người dùng:** Admin Small/lễ tân theo quyền. **Kiểu:** LOCAL. **Bảng:** KhoaHoc, GiaoVien, PhongHoc, LopHoc, BuoiHoc, NhatKyHeThong.

1. Nhân viên chọn khóa học, giáo viên, phòng, sức chứa, ngày bắt đầu/kết thúc, thứ trong tuần và khung giờ.
2. API kiểm tra tất cả dữ liệu thuộc site, giáo viên đang dạy, phòng khả dụng, ngày/giờ hợp lệ và không trùng lịch giáo viên/phòng.
3. Tạo LopHoc và các BuoiHoc theo mẫu lịch trong một transaction cục bộ.
4. Trả danh sách buổi đã tạo để nhân viên kiểm tra.

**Nghiệm thu:** không có buổi ngoài khoảng ngày; giờ hiển thị 24 tiếng Việt Nam; ngày kết thúc trước ngày bắt đầu bị từ chối; xung đột không tạo lớp/buổi một phần.

### FS-CLASS-02 — Xếp học viên vào lớp hoặc đổi lớp

**Người dùng:** Admin Small/lễ tân. **Kiểu:** LOCAL. **Bảng:** HocVien, DangKy, LopHoc, NhatKyHeThong.

1. Nhân viên chọn đăng ký hiện hành và lớp đích.
2. API xác nhận học viên/đăng ký/lớp cùng site, lớp đích còn chỗ, lịch phù hợp, đăng ký chưa hoàn tất/hủy/chuyển đi và không tạo bản ghi trùng.
3. Cập nhật quan hệ lớp của DangKy, sĩ số lớp cũ/mới và nhật ký trong một transaction cục bộ.
4. Trả lớp cũ/mới và trạng thái đăng ký sau cập nhật.

**Lỗi:** lớp đầy, sai site, trạng thái đăng ký không cho đổi hoặc xung đột lịch thì không cập nhật sĩ số; thao tác cạnh tranh dùng khóa/version hoặc kiểm tra lại trong transaction.

**Nghiệm thu:** tổng sĩ số không âm/vượt sức chứa; không chuyển đăng ký qua site bằng chức năng đổi lớp; giữ lịch sử theo mô hình schema.

### FS-ATT-01 — Điểm danh buổi học

**Người dùng:** giáo viên được phân công; nhân viên có quyền giám sát nếu được cấu hình. **Kiểu:** LOCAL. **Bảng:** BuoiHoc, DangKy, DiemDanh, NhatKyHeThong.

1. Giáo viên mở buổi học thuộc lớp được phân công.
2. API trả danh sách học viên có đăng ký hợp lệ ở site của lớp.
3. Giáo viên ghi mỗi học viên một trạng thái: co_mat, tre, vang_co_phep hoặc vang_khong_phep.
4. API kiểm tra ma_buoi, đăng ký cùng lớp/site, không trùng (ma_buoi, ma_dang_ky) và thời điểm được phép điểm danh.
5. Lưu tất cả điểm danh hợp lệ trong transaction site; thao tác sửa có nhật ký người sửa/thời gian/giá trị trước-sau.

**Nghiệm thu:** giáo viên lớp khác bị 403; bản ghi trùng không nhân đôi; lỗi ghi giữa chừng rollback theo hợp đồng batch.

### FS-TUI-01 — Thu học phí tại cơ sở

**Người dùng:** kế toán; Admin Small chỉ khi có quyền được cấp. **Kiểu:** LOCAL. **Site:** nơi lưu HocPhi. **Bảng:** DangKy, HocPhi, PhieuThu, NhanVien, NhatKyHeThong.

1. Kế toán mở khoản phải thu theo đăng ký; API tự xác định site, số phải thu, tổng đã thu/hoàn và số còn lại.
2. Người dùng nhập số tiền dương không vượt quá số còn nợ, phương thức hợp lệ và ghi chú không chứa dữ liệu thanh toán nhạy cảm.
3. API kiểm tra quyền, trạng thái khoản phí và khóa chống gửi lặp/idempotency.
4. Trong transaction site, thêm PhieuThu loại thu, cập nhật trạng thái HocPhi, ghi audit; không sửa/xóa lịch sử phiếu đã phát hành.
5. Trả mã phiếu, số tiền, số dư và trạng thái mới.

**Nghiệm thu:** gửi lại cùng idempotency key và payload trả cùng kết quả; cùng key nhưng payload khác bị conflict; hai request cạnh tranh không thể thu vượt số dư; lỗi DB không để phiếu thu và HocPhi lệch nhau.

**Khoảng trống:** schema hiện chưa có request ledger/khóa bền vững cho idempotency thu-quầy. Phải bổ sung trước khi khẳng định chống gửi lặp sau timeout đã được bảo đảm.

### FS-TUI-02 — Hoàn hoặc điều chỉnh học phí

**Người dùng:** kế toán có quyền hoàn; Admin Small giám sát theo phân quyền. **Kiểu:** LOCAL. **Bảng:** HocPhi, PhieuThu, NhatKyHeThong.

1. Người dùng chọn phiếu thu gốc và lý do hoàn/điều chỉnh.
2. API xác định site và số tiền có thể hoàn từ dữ liệu lưu; không cho hoàn vượt tổng số đã thu trừ số đã hoàn.
3. Trong transaction, thêm bút toán loại hoan tham chiếu phiếu gốc, cập nhật trạng thái HocPhi và audit.
4. Phiếu gốc giữ nguyên; không xóa hoặc ghi đè lịch sử.

**Nghiệm thu:** hoàn vượt mức bị từ chối; hoàn lặp được chặn bằng idempotency; tổng thu-trừ-hoàn khớp số dư; người không có quyền không thể hoàn.

### FS-PAY-01 — Thanh toán trực tuyến học phí

**Trạng thái:** yêu cầu tương lai, chưa thể triển khai/ nghiệm thu end-to-end vì chưa chọn nhà cung cấp và schema chưa có bảng lần thanh toán/sự kiện/idempotency. **Kiểu dự kiến:** khởi tạo/cập nhật Local ở site chứa HocPhi; callback được xác thực rồi commit tại đúng site.

Khi được nhóm duyệt nhà cung cấp và cập nhật schema, luồng phải đáp ứng:

1. API lấy site, số tiền, loại tiền, chủ khoản nợ từ HocPhi; frontend không được quyết định giá trị này.
2. Tạo YeuCauThanhToan bền vững cùng idempotency key trước khi chuyển người dùng đến cổng. Một HocPhi chỉ có tối đa một yêu cầu còn mở theo trạng thái được chốt.
3. Reload, quay lại website hoặc đăng nhập lại chỉ đọc trạng thái đã lưu; không tự tạo lượt thanh toán mới. URL redirect/query string không chứng minh đã trả tiền.
4. Webhook phải xác minh chữ ký, merchant, amount/currency, timestamp/replay và mã giao dịch provider; callback lặp phải idempotent.
5. Chỉ sau khi callback hợp lệ và transaction site đã commit PhieuThu, HocPhi và sự kiện thanh toán mới trả trạng thái thành công.
6. Timeout hoặc DB lỗi khi kết quả cổng chưa rõ chuyển sang can_doi_soat; chặn tạo lượt mới cho đến khi đối soát/retry có kết quả rõ.
7. Hoàn online là bút toán bù trừ tham chiếu giao dịch gốc. Không lưu PAN/CVV, secret, token provider hoặc payload thô.

**Điều kiện nghiệm thu trước khi bật:** chốt provider/merchant; thêm YeuCauThanhToan, SuKienThanhToan, liên kết idempotency với PhieuThu tại từng CSDL site; cập nhật schema/script/API/UI; kiểm thử webhook đúng/sai chữ ký, phát lại, reload, thoát giữa chừng, timeout, lỗi database và refund.

### FS-GRADE-01 — Nhập, sửa và xem điểm

**Người dùng:** giáo viên được phân công; Admin Small/Admin Big đọc hoặc giám sát theo quyền. **Kiểu:** LOCAL. **Bảng:** GiaoVien, LopHoc, DangKy, Diem, NhatKyHeThong.

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

**Người dùng:** Admin Big. **Kiểu:** hộp thư GLOBAL; quyết định ghi LOCAL tại CSDL nguồn. **Bảng:** GiaoDichChuyenCoSo, LichSuChuyenCoSo, CoSo, HocVien.

1. API truy vấn riêng các site hoạt động để tạo hộp thư; kết quả ghi rõ complete và missing_sites.
2. Nếu site nguồn không đọc được thì không cho quyết định trên đề nghị chưa tải được; không hiển thị hộp thư thiếu site như toàn bộ.
3. Khi duyệt/từ chối, API định tuyến về site nguồn đã được xác định từ đề nghị và kiểm tra quyền Admin Big.
4. Kiểm tra lại trạng thái đề nghị, học viên hiện hành, nợ, site đích và xung đột vì điều kiện có thể đổi trong lúc chờ.
5. Từ chối: ghi tu_choi, người/thời điểm/lý do và sự kiện tu_choi tại nguồn; hồ sơ học viên không đổi.
6. Duyệt: ghi trạng thái dang_xu_ly, bước da_tiep_nhan, người/thời điểm quyết định và sự kiện duyet tại nguồn. Chỉ sau commit quyết định mới giao Coordinator chạy distributed transfer.

**Nghiệm thu:** Admin Small/giáo viên bị từ chối; hai Admin Big duyệt đồng thời chỉ một quyết định thắng; quyết định idempotent; không gọi coordinator chuyển nếu quyết định chưa commit.

### FS-TRF-03 — Thực hiện và phục hồi giao dịch chuyển

**Người dùng:** Coordinator/worker được ủy quyền; không phải thao tác tự do của Admin Small. **Kiểu:** DISTRIBUTED-TX giữa nguồn và đích. **Bảng:** GiaoDichChuyenCoSo tại nguồn; HocVien/DangKy tại nguồn; HocVien tại đích; LichSuChuyenCoSo tại site phát sinh.

1. Coordinator chỉ nhận giao dịch đã duyệt. Tải trạng thái nguồn, khóa chống lặp và bước cuối đã commit.
2. Tạo hồ sơ HocVien cùng mã ở đích trong transaction đích; ghi sự kiện tao_ho_so_dich. Bản đích phải duy nhất theo mã và ma_chuyen.
3. Sau khi xác nhận đích commit, lưu bước da_tao_ho_so_dich tại nguồn.
4. Cập nhật nguồn: HocVien thành da_chuyen_di; đóng/đánh dấu các DangKy cũ theo trạng thái chuyen_di; cập nhật bước da_cap_nhat_nguon và ghi sự kiện.
5. Đối soát hai site; đánh dấu giao dịch hoan_tat và ghi sự kiện kết thúc. Bản nguồn được giữ lại làm lịch sử.
6. Worker có thể chạy lại an toàn. Nếu đích chưa commit, nguồn vẫn là bản hiện hành; nếu đích đã commit, phải tiếp tục tiến về phía trước, không xóa đích.

| Điểm dừng/ lỗi | Hành vi bắt buộc |
|---|---|
| Chưa được duyệt | Không tạo dữ liệu đích; không xử lý tự động |
| Trước khi đích commit | Giữ nguồn dang_hoc; lỗi tạm thời thì chờ retry, lỗi nghiệp vụ dứt điểm có trạng thái thất bại rõ |
| Đích đã commit, nguồn chưa cập nhật | Giữ dang_xu_ly; ẩn/không tính bản đích trong Global Query cho đến khi tiến trình qua mốc cập nhật nguồn; retry tiến về phía trước |
| Nguồn đã cập nhật, giao dịch chưa hoàn tất | Tính bản đích theo bước đã lưu; đối soát và hoàn thành trạng thái |
| Đích hoặc nguồn không phản hồi | Không báo hoàn tất; lưu trạng thái cần retry/đối soát và không xóa bản ghi đã commit |

**Nghiệm thu:** retry không tạo hồ sơ đích thứ hai; sau hoàn tất chỉ bản đích có trạng thái dang_hoc; bản nguồn da_chuyen_di còn nguyên; không tuyên bố ACID nguyên tử xuyên hai CSDL.

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

Nhật ký nghiệp vụ chứa tối thiểu người thực hiện, site, hành động, loại/mã bản ghi, thời điểm, kết quả và correlation/request ID phù hợp với schema. NhatKyDongBo lưu bảng/mã bản ghi/hành động/site đích/trạng thái/lỗi đã lọc. LichSuChuyenCoSo chỉ append-only.

Không ghi password/hash, token, cookie, header xác thực, secret Cloudinary/SMTP/OAuth/SQL, PAN/CVV hay payload thanh toán thô. Không trả nội dung nội bộ trong lỗi API.

**Nghiệm thu:** log nghiệp vụ có thể truy vết theo request ID nhưng không chứa secret; nhân sự cơ sở không đọc log của site khác; Admin Big thấy được trạng thái thiếu site khi truy vấn toàn cục.

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
| Giao dịch thanh toán trực tuyến | trạng thái chưa chốt trong schema | Không triển khai production trước khi thêm bảng/trạng thái và chốt provider. |

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
| YC-03: phương pháp replication | FS-SITE-01, FS-ACC-01; bảng dùng chung theo schema | TC-REP-01: một thay đổi thực tế truyền đến các bản sao |
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

| Mã | Việc cần chốt trước khi triển khai | Tài liệu/bảng bị ảnh hưởng |
|---|---|---|
| OPEN-01 | Session cookie, CSRF, logout/revoke và thời hạn phiên | specs/api.md, API auth |
| OPEN-02 | Pagination/filter/sort và danh mục lỗi API thống nhất | specs/api.md, frontend |
| OPEN-03 | Cơ chế bền vững cho rate limit khi chạy nhiều worker; ngưỡng bcrypt theo benchmark | API settings/deployment |
| OPEN-04 | Quy trình bootstrap tài khoản, activation token và trạng thái chưa kích hoạt | DATABASE_SCHEMA.md, TaiKhoan, API email |
| OPEN-05 | Tiến trình và retry khi tạo TaiKhoan nhân bản cùng hồ sơ site bị lỗi một phần | Schema/control tables, Coordinator |
| OPEN-06 | Request ledger/idempotency bền vững cho thu/hoàn tại quầy | DATABASE_SCHEMA.md, PhieuThu/payment service |
| OPEN-07 | Nhà cung cấp thanh toán, YeuCauThanhToan, SuKienThanhToan, webhook, đối soát và hoàn online | DATABASE_SCHEMA.md, specs/api.md, UI |
| OPEN-08 | Metadata Cloudinary, quyền upload/xóa và ràng buộc site sở hữu ảnh | DATABASE_SCHEMA.md, API upload |
| OPEN-09 | Có đưa tài khoản/portal học viên vào phạm vi không; nếu có phải thiết kế vai trò và liên kết HocVien | README, schema, API, UI, FS |
| OPEN-10 | Ngưỡng thời gian truy vấn p50/p95 và thiết bị/mạng đo cho mục tiêu hiệu năng | specs/api.md, specs/ui-ux.md |
| OPEN-11 | Phương pháp replication, nơi được phép ghi, tiến trình/ACK từng site, phiên bản và phục hồi; tránh API/Publication ghi trùng | README mục 9, schema, tài liệu đồng bộ, YC-03/YC-07 |
| OPEN-12 | Giao thức distributed transaction và mức bảo đảm đáp ứng tiêu chí giảng viên; nếu cần DBMS quản lý phải triển khai/kiểm thử bổ sung | README mục 9, tài liệu giao dịch, YC-04 |
| OPEN-13 | Cơ chế khóa/mức cô lập hoặc cập nhật có điều kiện để bảo vệ chỗ cuối, bộ kiểm thử hai phiên | FS-ENR-01, specs/api.md, source, YC-05 |
| OPEN-14 | Cách lưu bền vững một thao tác replication cùng trạng thái/phiên bản xác nhận ở từng site để có thể phân biệt chưa gửi, đã nhận, timeout chưa rõ và cần retry. `NhatKyDongBo` hiện chỉ là log append-only; xác định log đủ dùng hay cần outbox/bảng tiến trình và migration trước khi code | `NhatKyDongBo`, schema/migration, README mục 9, specs/api.md, TC-REP-01/TC-SYNC-01 |

Không tự coi các mục OPEN là đã chốt. Khi nhóm thống nhất, cập nhật các tài liệu liên quan trong cùng thay đổi và bổ sung tiêu chí nghiệm thu cụ thể.

## 12. Trạng thái triển khai hiện tại

Đây là baseline chức năng, không phải báo cáo tiến độ thay cho source. Theo [src/api/README.md](../src/api/README.md), API hiện có scaffold Django REST Framework, Swagger/OpenAPI sinh tự động, cấu hình nền và liveness check. Liveness chỉ xác nhận tiến trình API còn chạy, không xác nhận SQL Server hoặc nghiệp vụ hoạt động.

Các luồng đăng nhập, OAuth, quản lý tài khoản, hồ sơ học viên, đăng ký, xếp lớp, thu/hoàn, điểm danh, điểm, đề nghị/duyệt/chuyển cơ sở, Global Query và đồng bộ dữ liệu dùng chung chưa có endpoint nghiệp vụ hoạt động theo trạng thái tài liệu API hiện tại. Mỗi luồng chỉ được chuyển sang “đã triển khai” sau khi có code, migration/script cần thiết, kiểm thử tại các site liên quan và cập nhật trạng thái trong README/API docs.
