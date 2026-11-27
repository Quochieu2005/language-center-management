# Báo cáo đồ án CSDL phân tán — bản nháp

**Đề tài 10 · Quản lý trung tâm đào tạo ngoại ngữ · Ba cơ sở Q1, Q7, TD · Hạn nộp 17/12/2026.**

Đây là bản nháp để cả nhóm hoàn thiện rồi chuyển sang file nộp. Sườn theo yêu cầu của giảng viên (GV-01); nguồn chi tiết là [đề cương](QLTTNN-De-Cuong-Bao-Cao.md), [schema](DATABASE_SCHEMA.md), [giao dịch phân tán](QLTTNN-Giao-Dich-Phan-Tan.md) và [bộ yêu cầu/kiểm chứng](QLTTNN-Yeu-Cau-Chung-Va-Kiem-Chung.md). Các đoạn dưới đây dùng được ngay; chỗ nào thiếu thì có thẻ:

- `[CẦN ẢNH Exx]`: cần chụp ảnh, mã khớp với [phụ lục A](#phụ-lục-a-danh-sách-ảnh-và-bằng-chứng-cần-thu).
- `[CẦN BỔ SUNG]`: cần thông tin hoặc kết quả mà nhóm chưa có.
- Trạng thái bằng chứng: **ĐÃ CÓ** (chạy trên hệ thống thật), **MỘT PHẦN** (chỉ trên database tạm hoặc giả lập), **THIẾU** (chưa làm).

Nguyên tắc khi hoàn thiện: chỉ ghi điều đã chạy thật; kết quả trên database tạm phải nói rõ là database tạm; không đưa mật khẩu, token, IP riêng vào báo cáo; không viết "ba bản giống nhau tại một thời điểm" hay "ACID xuyên site" vì hệ thống không đảm bảo hai điều đó.

## Tiến độ theo mục

| Mục | Trạng thái | Còn thiếu |
|---|---|---|
| 1. Đề tài và thành viên | THIẾU | Danh sách 5 sinh viên và phân công |
| 2.1 Đặt vấn đề | ĐÃ CÓ (văn bản) | Đọc lại cho đúng giọng của nhóm |
| 2.2.1 Phân tích | ĐÃ CÓ (văn bản) | Tần suất mới là ước lượng định tính |
| 2.2.2 Thiết kế | ĐÃ CÓ (văn bản và sơ đồ) | ERD và sơ đồ định vị đã dựng ở [QLTTNN-So-Do.md](QLTTNN-So-Do.md); chèn vào file nộp |
| 3.1 VPN | MỘT PHẦN | Ảnh từng máy trong mạng ZeroTier |
| 3.2 Kết nối giữa server | MỘT PHẦN | Xác nhận máy nào của ai; Q7 và TD hiện offline |
| 3.3 Cài DBMS | MỘT PHẦN | Phiên bản và edition của Q1, Q7; ảnh |
| 3.4 Agent | MỘT PHẦN | Ảnh Agent và job trên máy Publisher |
| 3.5 Linked Server | THIẾU | Ảnh cấu hình `LS_Q7` và truy vấn đọc thử |
| 3.6 Replication | MỘT PHẦN | Đã có `MonHoc`; còn ảnh Replication Monitor và thử ngắt/phục hồi `KhoaHoc`, `TaiKhoan`, Blog trên ba site |
| 3.7 Thử quyền, giao tác, truy vấn | MỘT PHẦN | CON và DQ đã chạy trên Q1 thật (27/11); còn FRAG và SYNC trên nhiều site thật, và DTX chưa có |

## 1. Đề tài được giao

Đề tài 10: **Quản lý trung tâm đào tạo ngoại ngữ** trên cơ sở dữ liệu phân tán, môn Cơ sở dữ liệu phân tán.

`[CẦN BỔ SUNG]` Danh sách 5 sinh viên (họ tên, mã số) và vai trò trong nhóm. Phân công hiện tại theo [làm việc nhóm](QLTTNN-Lam-Viec-Nhom.md): Q1 do Quốc Hiếu, Q7 do Minh Khôi, TD do Minh Đức giữ; năm luồng công việc A đến E.

## 2. Viết tài liệu

### 2.1. Đặt vấn đề

Một trung tâm ngoại ngữ có nhiều cơ sở. Mỗi cơ sở hằng ngày tiếp nhận học viên, mở lớp, xếp lịch, thu học phí, điểm danh và nhập điểm. Quản trị viên cần xem tình hình toàn hệ thống, và học viên đôi khi chuyển từ cơ sở này sang cơ sở khác. Nếu mọi nghiệp vụ dùng chung một cơ sở dữ liệu đặt tại một nơi thì mọi thao tác ở cơ sở đều phụ thuộc đường truyền tới nơi đó, và khi nơi đó hỏng thì toàn bộ hệ thống ngừng.

Đồ án dùng ba cơ sở dữ liệu SQL Server độc lập cho Quận 1 (Q1), Quận 7 (Q7) và Thủ Đức (TD), cùng một lớp điều phối (Coordinator) ở ứng dụng. Dữ liệu nghiệp vụ như học viên, lớp, đăng ký, học phí và điểm được lưu tại cơ sở phát sinh. Danh mục dùng chung (cơ sở, môn học, khóa học) và tài khoản được nhân bản tới mọi cơ sở đang hoạt động. Truy vấn toàn cục hỏi từng cơ sở rồi gộp ở ứng dụng. Chuyển cơ sở là giao dịch tác động lên hai cơ sở.

Vì sao cần phân tán:

- Mỗi cơ sở lưu dữ liệu học viên, nhân viên, phòng và lớp của riêng mình, nên thao tác hằng ngày chạy cục bộ.
- Danh mục và tài khoản phải có ở mọi cơ sở để đăng nhập và đăng ký lớp không phụ thuộc cơ sở khác.
- Một cơ sở mất kết nối thì các cơ sở còn lại vẫn làm việc; báo cáo toàn cục nói rõ cơ sở nào thiếu thay vì báo sai số.
- Thêm cơ sở mới là thêm cấu hình và dữ liệu, không sửa vòng lặp cố định trong code.

Vai trò sử dụng: Admin Big (toàn hệ thống), Admin Small (một cơ sở), Kế toán & Lễ tân, Tư vấn & xếp lớp, Giáo viên, và người dùng website. Chi tiết quyền ở [đề cương](QLTTNN-De-Cuong-Bao-Cao.md) và README mục 3.

### 2.2. Phân tích và thiết kế

#### 2.2.1. Phân tích

**Chức năng chính:** đăng nhập và phân quyền; quản lý học viên, giáo viên, nhân viên; quản lý môn và khóa học; mở lớp, sinh buổi học; đăng ký và đổi lớp; thu và hoàn học phí; điểm danh; quản lý điểm; chuyển cơ sở; thống kê toàn cục; nhật ký; blog và liên hệ; trang cấp tài khoản cho người đăng ký khóa học.

**Phân loại thao tác theo cách truy cập dữ liệu:**

| Kiểu | Ý nghĩa | Ví dụ |
|---|---|---|
| `LOCAL` | Chỉ một cơ sở, một transaction cục bộ | Đăng ký lớp, thu học phí, điểm danh |
| `GLOBAL` | Đọc từng cơ sở rồi gộp ở ứng dụng | Thống kê học viên, nhật ký toàn hệ thống |
| `REPLICATED-WRITE` | Ghi một thay đổi cần có ở mọi cơ sở | Sửa môn học, khóa học, tài khoản, bài blog |
| `DISTRIBUTED-TX` | Thao tác tác động hai cơ sở | Chuyển học viên sau khi được duyệt |

**Tần suất dự kiến.** Chưa có log vận hành của một trung tâm thật, nên tần suất dưới đây là ước lượng định tính để thiết kế, không phải số đo:

| Mức | Thao tác |
|---|---|
| Cao | Đăng nhập; xem khóa học và lớp còn chỗ; đăng ký khóa học (theo mùa tuyển sinh); thu học phí |
| Trung bình | Đổi lớp; mở lớp; điểm danh; nhập điểm; xem thống kê một cơ sở |
| Thấp | Thống kê toàn cục; nhật ký; sửa danh mục và tài khoản; đề nghị và thực hiện chuyển cơ sở |

Bảng đầy đủ kèm bảng đọc/ghi nằm ở [đề cương, mục 2.2.1](QLTTNN-De-Cuong-Bao-Cao.md).

**Phân tích CSDL.** ERD đầy đủ (có khóa, kiểu rút gọn, nhóm phân tán) ở [QLTTNN-So-Do.md](QLTTNN-So-Do.md), mục 1 và 2, ảnh `docs/diagrams/erd-*.png`; sơ đồ quan hệ gốc ở [DATABASE_SCHEMA.md, mục 5](DATABASE_SCHEMA.md#5-các-bảng-liên-quan-với-nhau-thế-nào). Điểm cần nói rõ: chỉ có khóa ngoại cục bộ trong từng cơ sở; không có khóa ngoại hay JOIN xuyên cơ sở. Học viên chuyển cơ sở để lại bản lịch sử ở nguồn (`da_chuyen_di`), nên thống kê phải chọn bản hiện hành theo bước của Coordinator.

#### 2.2.2. Thiết kế

**Các nhóm bảng:**

| Nhóm | Bảng |
|---|---|
| Danh mục và tài khoản nhân bản | `CoSo`, `MonHoc`, `KhoaHoc`, `TaiKhoan`, `DanhMucBlog`, `BaiVietBlog` |
| Phân mảnh ngang nguyên thủy theo `ma_co_so` | `HocVien`, `GiaoVien`, `NhanVien`, `Admin` (Small), `PhongHoc`, `LopHoc`, `YeuCauLienHe` |
| Phân mảnh ngang dẫn xuất | `BuoiHoc`, `DangKy`, `DiemDanh`, `HocPhi`, `DotHocPhi`, `PhieuThu`, `Diem` |
| Trạng thái giao dịch và nhật ký cục bộ | `GiaoDichChuyenCoSo`, `LichSuChuyenCoSo`, `ThongBao`, `Logs` |
| Chỉ tại cơ sở xác thực (authority, hiện là Q1) | `PhienDangNhap`, `DatChoEmailHocVien`, `DongBoTaiKhoan`, `NguoiDung` |

**Phân mảnh ngang.** Với mỗi cơ sở `s`, mảnh `LopHoc_s = σ(ma_co_so = s)(LopHoc)`, tương tự cho các bảng nguyên thủy. Các bảng dẫn xuất giữ cùng `ma_co_so` với bảng cha và được bảo vệ bằng khóa ngoại ghép cùng `CHECK` site: `DangKy_s` dẫn xuất từ `LopHoc_s`, `HocPhi_s` từ `DangKy_s`, `Diem_s` từ `DangKy_s`. Ba tính chất:

- Đầy đủ: mỗi lớp nằm ở một mảnh.
- Tái thiết: `LopHoc = ⋃ LopHoc_s` với `s` thuộc các cơ sở được cấp phát, thực hiện trong công cụ kiểm thử hoặc ở API, không có cơ sở dữ liệu trung tâm.
- Không giao nhau: hai mảnh không có mã lớp chung.

Dự án chặn ghi sai cơ sở bằng 16 `CHECK` (migration 30) cộng 1 `CHECK` cho `YeuCauLienHe` (migration 43) trong mỗi cơ sở dữ liệu, thay cho Publication có bộ lọc ở tài liệu GV-02. Đây là điểm khác cần nêu trong báo cáo.

**Ánh xạ và tái thiết toàn cục.**

| Yêu cầu | Cách xử lý |
|---|---|
| `LOCAL` | Site Router chọn đúng kết nối; transaction trong một cơ sở dữ liệu |
| `GLOBAL` | Hỏi từng cơ sở đang hoạt động, gắn mã cơ sở, gộp ở Django; thiếu cơ sở thì trả `complete=false` và `missing_sites`, không đổi thành 0 |
| `REPLICATED-WRITE` | Theo cơ chế riêng của từng bảng, xem bảng dưới |
| `DISTRIBUTED-TX` | Coordinator điều phối nguồn và đích, phục hồi tiến về phía trước |

**Định vị dữ liệu.** Sơ đồ định vị dữ liệu ở [QLTTNN-So-Do.md](QLTTNN-So-Do.md), mục 3 (`docs/diagrams/dinh-vi-du-lieu.png`); lược đồ phân mảnh ở [DATABASE_SCHEMA.md, mục 8](DATABASE_SCHEMA.md#phan-manh). Sơ đồ bố trí máy (mục 4 của tài liệu sơ đồ) phải ghi theo thực tế, xem 3.2.

**Đồng bộ hóa — cơ chế theo bảng:**

| Dữ liệu | Nơi ghi | Cách tới cơ sở khác | Khi một cơ sở offline |
|---|---|---|---|
| `MonHoc` | Publisher (Q1) | SQL Server transactional replication, đẩy bất đồng bộ | Từ chối ghi nếu thiếu cơ sở hoạt động; bản sao chậm thì trả 202 |
| `KhoaHoc` | Từng cơ sở đang kết nối | Ứng dụng ghi và lưu ACK trong `Logs`; worker `sync_courses` | Ghi cơ sở còn sống, trả 202, tiếp tục sau |
| Blog | Từng cơ sở đang kết nối | Như trên; worker `sync_blog`, hàng đợi `BLINT-`, `BLFIN-`, `BLREV-` | Vẫn ghi cơ sở còn sống, cơ sở thiếu được phát lại theo thứ tự |
| `TaiKhoan` | Authority | Trigger đưa vào `DongBoTaiKhoan`, worker `sync_accounts` | Giữ trong hàng đợi, báo `replication_pending_sites` |

Đối chiếu lý thuyết (GV-03): `MonHoc` và `TaiKhoan` là lazy một nơi ghi; `KhoaHoc` và Blog gần ROWAA (ghi cơ sở còn sống, nhớ cơ sở thiếu, phát lại sau). Không dùng 2PC, MSDTC hay quorum. Mức nhất quán là nhất quán ngầm: các bản sao có thể lệch tạm thời và hội tụ sau.

**Quản lý giao tác (QTLPT).** Kiến trúc Client/Server có Coordinator: máy trạm gọi ứng dụng, Coordinator định tuyến và điều phối; mỗi cơ sở có cơ sở dữ liệu riêng, không có kho nghiệp vụ trung tâm. Chuyển cơ sở là chuỗi transaction cục bộ cùng sự kiện bền vững và phục hồi tiến về phía trước, không phải giao dịch nguyên tử xuyên hai cơ sở. `[CẦN BỔ SUNG]` Nếu giảng viên yêu cầu giao dịch do DBMS quản lý (MSDTC/2PC), phải làm thêm trước khi nộp (xem mục "Hạn chế").

## 3. Cài đặt vật lý thực tế

Mỗi bước ghi: ngày, người làm, máy, phiên bản, thao tác, kết quả, ảnh. Không chụp hoặc ghi mật khẩu, token, IP riêng.

### 3.1. Cài VPN và công cụ hỗ trợ từ xa

Nhóm dùng ZeroTier để các máy ở các vị trí khác nhau cùng một mạng ảo; TeamViewer hoặc Remote Desktop chỉ để điều khiển từ xa, không thay đường mạng SQL. Hướng dẫn cài đặt: [QLTTNN-Huong-Dan-Ket-Noi-ZeroTier-SQL-Server.md](QLTTNN-Huong-Dan-Ket-Noi-ZeroTier-SQL-Server.md). Trạng thái: **MỘT PHẦN**.

`[CẦN ẢNH E-3.1-01]` Từng máy đã vào mạng ZeroTier. `[CẦN ẢNH E-3.1-02]` Kết quả kiểm tra cổng 1433 từ máy chạy API tới từng máy SQL Server.

### 3.2. Tạo đường kết nối giữa server

Máy chạy Django API kết nối riêng tới từng SQL Server qua alias theo cấu hình (`SITE_DATABASES_JSON`), mỗi cơ sở một kết nối. Next.js chỉ gọi API, không giữ chuỗi kết nối.

Bố trí máy tại thời điểm viết: Q1 trên máy Windows của Quốc Hiếu; TD trên máy `DESKTOP-N47BBPH` (database `QLTTNN_TD_MOI`); Q7 trên SQL Server trong Docker trên Mac. `[CẦN BỔ SUNG]` Xác nhận máy nào của ai, vì nhiều tài liệu cũ vẫn ghi TD cùng máy với Q1. Trạng thái: **MỘT PHẦN**. Kết nối tới Q7 và TD hiện chập chờn hoặc offline.

`[CẦN XÁC NHẬN]` Sơ đồ máy thật: đã có bản nháp `docs/diagrams/bo-tri-vat-ly.png`, cần xác nhận máy nào của ai rồi sửa và vẽ lại. `[CẦN BỔ SUNG]` Bảng `site | máy | instance | port | kiểm tra từ đâu | kết quả`.

### 3.3. Cài hệ quản trị CSDL

DBMS: Microsoft SQL Server; quản trị bằng SSMS. Ba cơ sở dữ liệu `QLTTNN_Q1`, `QLTTNN_Q7` và `QLTTNN_TD_MOI` (TD) cùng một schema (`db/01_create_schema.sql` và các migration). Đã ghi nhận TD chạy SQL Server 16.0.1000.6. `[CẦN BỔ SUNG]` Phiên bản và edition của Q1 và Q7. `[CẦN ẢNH E-3.3-01]` Phiên bản từng instance và danh sách bảng cùng cấu trúc ở cả ba cơ sở dữ liệu. Trạng thái: **MỘT PHẦN**.

### 3.4. Kiểm tra dịch vụ Agent

Replication của `MonHoc` cần SQL Server Agent (Log Reader và Distribution Agent) trên máy Publisher. Đã có ảnh do thành viên cung cấp ngày 20/11/2026 cho thấy sửa ở Q1 truyền sang Q7, và sau khi dừng rồi bật lại Q7 thì thay đổi được truyền bù. `[CẦN ẢNH E-3.4-01]` Trạng thái dịch vụ Agent và lịch sử job. Trạng thái: **MỘT PHẦN**.

### 3.5. Tạo và kiểm tra Linked Server

Nhóm có Linked Server `LS_Q7` để đọc dữ liệu Q7 từ máy Windows, dùng cho phần trình diễn; nghiệp vụ của ứng dụng không dùng Linked Server để JOIN xuyên cơ sở. Trạng thái: **THIẾU** (tài liệu có ghi nhưng repo chưa có ảnh hay kết quả).

`[CẦN ẢNH E-3.5-01]` Cấu hình Linked Server đã che tài khoản. `[CẦN ẢNH E-3.5-02]` Truy vấn đọc thử kiểu `SELECT ... FROM LS_Q7.QLTTNN_Q7.dbo.LopHoc` và kết quả đến từ đúng cơ sở.

### 3.6. Tạo Publication/Replication

Phương pháp: SQL Server **transactional replication**, kiểu push, một Publisher (Q1) cho `MonHoc`. API chỉ ghi tại Publisher; SQL Server chuyển tới Subscriber (Q7, TD); API đối soát lại từng bản sao mới báo hoàn tất. Không dùng merge replication vì chỉ một nơi được ghi (không có xung đột). Chi tiết và bằng chứng: [MonHoc-SQL-Replication.md](MonHoc-SQL-Replication.md), [evidence TC-REP-01](evidence/TC-REP-01/2026-11-20/README.md).

Kết quả đã có (20/11/2026, SQL Server thật, ba site): thêm, sửa, xóa `MonHoc` qua API; trả 202 khi chờ bản sao rồi hoàn tất; gửi lại cùng khóa không tăng phiên bản; cùng khóa khác nội dung bị 409. Trạng thái `MonHoc`: **ĐÃ CÓ**.

Các bảng còn lại (`KhoaHoc`, Blog, `TaiKhoan`) dùng hàng đợi do ứng dụng cài, không phải Publication; trạng thái: **MỘT PHẦN** (đã kiểm chứng trên database tạm, xem 3.7).

`[CẦN ẢNH E-3.6-01]` Publication, Subscription và Replication Monitor. `[CẦN ẢNH E-3.6-02]` Kết quả trước và sau khi sửa một môn học ở cả ba cơ sở. `[CẦN BỔ SUNG]` Thử ngắt rồi phục hồi một cơ sở thật cho `KhoaHoc`, Blog, `TaiKhoan`.

### 3.7. Thử quyền, nhập/đọc dữ liệu và giao tác

Dữ liệu thử: bộ dữ liệu LAB có đánh dấu, nạp bằng `manage.py seed_lab_data` (xem [db/README.md](../db/README.md#dữ-liệu-mẫu-cho-các-lần-chạy-bằng-chứng-seed_lab_data)); không dùng dữ liệu cá nhân thật.

Kết quả đã chạy ngày 26/11/2026 trên **hai database tạm cùng một instance** (không phải ba máy, không phải Q1/Q7/TD thật):

| Kịch bản | Kết quả | Bằng chứng |
|---|---|---|
| TC-FRAG-01 phân mảnh, tái thiết | Đạt: hợp 3 + 2 = 5 lớp đúng tập kỳ vọng, hai mảnh không giao nhau; 4 ca ghi sai cơ sở đều bị đúng ràng buộc chặn | [TC-FRAG-01](evidence/TC-FRAG-01/2026-11-26/README.md) |
| TC-CON-01 tranh chỗ cuối | Đạt: phiên thứ hai phải chờ rồi bị từ chối; 20 vòng đều chỉ một phiên thắng; lớp 5 chỗ với 12 phiên ra đúng 5 | [TC-CON-01](evidence/TC-CON-01/2026-11-26/README.md) |
| TC-DQ-01 truy vấn phân tán | Đạt: số khớp từng cơ sở; một cơ sở mất kết nối thì báo thiếu, không báo 0; phục hồi khớp lại | [TC-DQ-01](evidence/TC-DQ-01/2026-11-26/README.md) |
| TC-SYNC-01 đồng bộ sau lỗi | Đạt cho hàng đợi tài khoản và Blog sau khi sửa một lỗi hội tụ | [TC-SYNC-01](evidence/TC-SYNC-01/2026-11-26/README.md) |
| TC-REP-01 replication `MonHoc` | Đạt trên ba site thật | [TC-REP-01](evidence/TC-REP-01/2026-11-20/README.md) |
| TC-CON-01 trên **Q1 thật** (27/11) | Đạt: phiên thứ hai chờ rồi bị từ chối; 10 vòng đều một phiên thắng; lớp 5 chỗ với 12 phiên ra đúng 5 | [TC-CON-01 Q1 thật](evidence/TC-CON-01/2026-11-27-site-that/README.md) |
| TC-DQ-01 khi **mất site thật** (27/11) | Đạt: Q7 và TD mất kết nối thật, API báo `complete=false`, `missing_sites=["Q7","TD"]`, tổng khớp SQL trực tiếp ở Q1, không báo 0; hai endpoint công khai qua HTTP cũng báo đúng | [TC-DQ-01 site thật](evidence/TC-DQ-01/2026-11-27-site-that/README.md) |
| TC-DTX-01 chuyển cơ sở | **THIẾU**: có luồng đề nghị, duyệt, điều phối và retry trong code; chưa chạy thử lỗi trước và sau commit đích | — |

Hai lỗi do các lần chạy này tìm ra và đã sửa: hàng đợi Blog không hội tụ khi sửa liên tiếp một bài lúc một cơ sở mất kết nối; và API văng lỗi 500 thay vì báo thiếu cơ sở khi database offline trên instance còn chạy. Nên nêu trong báo cáo vì đó là kết quả trực tiếp của việc kiểm chứng.

`[CẦN BỔ SUNG]` TC-CON và TC-DQ đã chạy trên Q1 thật (27/11, dòng trên); còn chạy TC-FRAG và TC-SYNC trên nhiều site thật, chạy lại CON và DQ trên cả ba site khi Q7 và TD lên, và chạy TC-DTX-01. Các thử nghiệm quyền theo vai trò, nhật ký, giao tác chuyển cơ sở và trigger bảo vệ nhật ký (`TR_Logs_AppendOnly`) cần ảnh thao tác: `[CẦN ẢNH E-3.7-01]` đến `[CẦN ẢNH E-3.7-06]`.

## 4. Kết luận, hạn chế và hướng phát triển

**Đã đạt:** bốn kỹ thuật bắt buộc đều có cài đặt: phân mảnh ngang (nguyên thủy và dẫn xuất), replication (SQL Server cho `MonHoc`, hàng đợi ứng dụng cho các bảng còn lại), giao dịch phân tán (chuyển cơ sở), truy vấn phân tán (Global Query), cùng đồng bộ sau lỗi và một tình huống concurrency.

**Hạn chế cần nói thẳng:**

- Chưa có 2PC hay MSDTC. Chuyển cơ sở là transaction cục bộ cộng phục hồi tiến về phía trước. `[CẦN BỔ SUNG]` Cần hỏi giảng viên có yêu cầu giao dịch do DBMS quản lý không.
- Phần lớn bằng chứng mới chạy trên hai database tạm cùng một máy; ba máy thật và thử tắt máy hoặc ngắt VPN thật còn thiếu.
- Chỉ `MonHoc` dùng Publication; chưa làm demo Publication có bộ lọc theo bảng cha như GV-02.
- Cơ sở xác thực (Q1) và API chưa có dự phòng (HA): mất Q1 thì đăng nhập gián đoạn. Đây là lựa chọn thiết kế đã biết (một authority để tránh trùng email và phiên đăng nhập), không phải thiếu sót chưa phát hiện; hướng khắc phục là bản sao đồng bộ cho authority.
- Hai tiến trình nền `sync_blog` và `sync_accounts` mới được thử theo từng lượt (một lần chạy sau khi site hồi phục), chưa chạy liên tục nhiều giờ hoặc nhiều ngày; chưa có giám sát hàng đợi tồn đọng ngoài số đếm `pending_count` và `review_count`.
- Ảnh trên Cloudinary: ba ảnh đại diện cũ của tài khoản và học viên vẫn nằm ngoài thư mục gốc của dự án (mã dạng UUID, tải lên trước khi có cấu trúc thư mục). Chúng còn đang được dùng nên giữ nguyên; chưa di chuyển vì phải đổi tham chiếu đồng thời ở cả ba site.
- Kiểm tra giao diện dùng dữ liệu giả lập cho các trang cần đăng nhập; chưa thử trên thiết bị thật.

**Hướng phát triển:** giao dịch do DBMS quản lý nếu được yêu cầu; dự phòng cho authority; đối soát tự động định kỳ cho mọi bảng nhân bản; thêm cơ sở mới bằng cấu hình.

## Phụ lục A. Danh sách ảnh và bằng chứng cần thu

| Mã | Mục | Máy/site | Cần chụp | Trạng thái |
|---|---|---|---|---|
| E-2.2-01 | 2.2.1 | — | ERD | ĐÃ CÓ (`docs/diagrams/erd-*.png`) |
| E-2.2-02 | 2.2.2 | — | Sơ đồ định vị dữ liệu | ĐÃ CÓ (`docs/diagrams/dinh-vi-du-lieu.png`) |
| E-3.1-01 | 3.1 | Mỗi máy | Máy trong mạng ZeroTier | Chưa chụp |
| E-3.1-02 | 3.1 | Máy API | Kiểm tra cổng 1433 tới từng SQL Server | Chưa chụp |
| E-3.2-01 | 3.2 | — | Sơ đồ máy thật | Bản nháp, cần xác nhận máy (`docs/diagrams/bo-tri-vat-ly.png`) |
| E-3.3-01 | 3.3 | Q1, Q7, TD | Phiên bản instance và danh sách bảng | Chưa chụp |
| E-3.4-01 | 3.4 | Publisher | SQL Server Agent và lịch sử job | Chưa chụp |
| E-3.5-01 | 3.5 | Máy có Linked Server | Cấu hình `LS_Q7` (che tài khoản) | Chưa chụp |
| E-3.5-02 | 3.5 | Máy có Linked Server | Truy vấn đọc thử qua `LS_Q7` | Chưa chụp |
| E-3.6-01 | 3.6 | Publisher | Publication, Subscription, Replication Monitor | Chưa chụp |
| E-3.6-02 | 3.6 | Q1, Q7, TD | `MonHoc` trước và sau khi sửa ở cả ba site | Chưa chụp (có ảnh 20/11 do thành viên giữ) |
| E-3.7-01 | 3.7 | Q1, Q7, TD | Dữ liệu LAB đã nạp, từng site | Chờ site lên |
| E-3.7-02 | 3.7 | Q1, Q7, TD | TC-FRAG-01 chạy trên site thật | Chờ site lên |
| E-3.7-03 | 3.7 | Q1 (hoặc site có lớp) | TC-CON-01: hai phiên tranh chỗ cuối | Đã chạy trên Q1 thật 27/11 (kết quả JSON); còn ảnh chụp |
| E-3.7-04 | 3.7 | API và các site | TC-DQ-01: tổng khớp, thử thiếu một site | Đã chạy 27/11 khi Q7 và TD mất thật (kết quả JSON); còn ảnh chụp cảnh báo thiếu site ở trang admin |
| E-3.7-05 | 3.7 | Nguồn và đích | TC-DTX-01: trạng thái trước, sau, khi lỗi, khi phục hồi | Chưa làm |
| E-3.7-06 | 3.7 | Mỗi vai trò | Quyền được và bị từ chối; trigger bảo vệ nhật ký | Chưa chụp |

Lưu ảnh vào `docs/evidence/<mã TC>/<ngày>/`. Che mật khẩu, token và IP riêng trước khi lưu.

## Phụ lục B. Kế hoạch đến hạn nộp

| Khoảng ngày | Việc |
|---|---|
| 27/11 đến 29/11 | Đưa Q7 và TD lên ổn định; xác nhận máy nào của ai; hỏi giảng viên về 2PC; chốt các quyết định còn mở. Chốt một buổi khoảng 2 giờ cả ba chủ máy cùng có mặt |
| 30/11 đến 5/12 | Chạy buổi theo [kịch bản chạy bằng chứng](QLTTNN-Chay-Bang-Chung-Site-That.md): migration Q7, nạp dữ liệu LAB ba site, TC-FRAG, CON, DQ, SYNC, DTX, REP trên site thật, chụp ảnh E-3.x |
| 6/12 đến 14/12 | Hoàn thiện văn bản từ bản nháp này, chèn ảnh, vẽ ERD và sơ đồ định vị |
| 15/12 đến 16/12 | Dự phòng, rà lại từng mục với mã ảnh, nộp 17/12 |
