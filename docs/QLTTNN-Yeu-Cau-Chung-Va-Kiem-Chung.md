# Yêu cầu chung và kịch bản kiểm chứng CSDL phân tán

Đối chiếu các file gốc và mục/trang tại [bảng tham khảo giảng viên](QLTTNN-De-Cuong-Bao-Cao.md#tai-lieu-giang-vien). GV-06 trang 1 bổ sung yêu cầu lab ít nhất ba SQL Server: TC-SITE-01 phải ghi số instance/máy thật; ba database trên một instance chưa đạt bố trí này. TC-FRAG-01 dùng [script chỉ đọc](../db/README.md#kiem-chung-csdl) và [lược đồ phân tán](DATABASE_SCHEMA.md#phan-manh).

Tài liệu này ghi yêu cầu chung do giảng viên giao, áp dụng cùng sáu nghiệp vụ của Đề tài 10. Đây là tiêu chí phải triển khai và kiểm chứng, không phải xác nhận hệ thống đã đạt. [README](../README.md) mô tả kiến trúc/nghiệp vụ; [schema](DATABASE_SCHEMA.md) quy định bảng; [FS](../fs/Functional-Specification.md) và [API/UI specs](../specs/README.md) quy định hành vi cần xây dựng.

## 1. Yêu cầu chung của giảng viên

- Mỗi đề tài có **2–4 site**; triển khai tối thiểu có **phân mảnh, replication, transaction và đồng bộ dữ liệu**.
- Không bắt buộc các nhóm dùng cùng một kiểu phân mảnh.
- Mỗi nhóm phải chứng minh ít nhất **1 phương pháp phân mảnh + 1 phương pháp replication + 1 distributed transaction + 1 tình huống concurrency + 1 distributed query**.

Đồ án chọn **3 site Q1, Q7, TD**, mỗi site có CSDL SQL Server và kết nối riêng. Kịch bản mở rộng thêm BT là site thứ tư, vẫn nằm trong giới hạn bài học. Số site trong nghiệp vụ lấy từ `CoSo` và cấu hình; giới hạn demo 2–4 site không phải lý do viết cứng vòng lặp ba lần. Cài ba DB trên một instance phục vụ phát triển phải được ghi đúng là mô phỏng trên một máy; báo cáo phải ghi topology thực tế và đối chiếu yêu cầu cài đặt vật lý của giảng viên.

**Replication và distributed transaction không phải mục tùy chọn.** Có thể còn phải chốt công cụ/cơ chế, nhưng không được bỏ yêu cầu hoặc đổi thành “không áp dụng”. Seed cùng dữ liệu, kết nối VPN thành công, ảnh Swagger và màn hình web không tự chứng minh đã đạt các kỹ thuật này.

## 2. Ma trận yêu cầu và trách nhiệm

Các vai trò A–E theo [phân công nhóm](QLTTNN-Lam-Viec-Nhom.md); nhóm điền tên người thực hiện khi nhận task.

| Mã | Yêu cầu | Áp dụng trong đồ án | Kịch bản | Phụ trách/phối hợp |
|---|---|---|---|---|
| YC-01 | 2–4 site | Q1/Q7/TD có DB và kết nối riêng | TC-SITE-01 | A + B |
| YC-02 | Ít nhất 1 phương pháp phân mảnh | Ngang theo `ma_co_so` với `LopHoc`; dẫn xuất `DangKy` theo lớp | TC-FRAG-01 | A + D |
| YC-03 | Ít nhất 1 phương pháp replication | Nhân bản bảng dùng chung; dùng `MonHoc` để kiểm chứng truyền thay đổi | TC-REP-01 | A + B + C |
| YC-04 | Ít nhất 1 distributed transaction | Chuyển học viên Q1 → Q7 sau khi Admin Big hoặc Admin Small Q7 duyệt | TC-DTX-01 | B + A + D |
| YC-05 | Ít nhất 1 tình huống concurrency | Hai học viên tranh chỗ cuối trong cùng lớp bằng hai phiên đồng thời | TC-CON-01 | D + A + B |
| YC-06 | Ít nhất 1 distributed query | Thống kê học viên từ từng site rồi tổng hợp tại API | TC-DQ-01 | B + E |
| YC-07 | Đồng bộ dữ liệu | Đối soát, retry và phục hồi bản sao khi một site lỗi | TC-SYNC-01 | A + B + C |

E phối hợp lưu kết quả/demo; Quốc Hiếu review trước khi nhóm ghi đạt. Năm nội dung chứng minh tối thiểu là YC-02 đến YC-06; YC-01 và YC-07 vẫn bắt buộc. Sáu nghiệp vụ đề tài trong README/FS phải được thực hiện đồng thời với các yêu cầu chung này.

## 3. Cơ chế cần ghi rõ trước khi triển khai

| Nội dung | Đã xác định trong thiết kế | Cần chốt/kiểm chứng |
|---|---|---|
| Phân mảnh | Ngang theo site và dẫn xuất theo bảng cha; JOIN/FK chỉ trong site | Truy vấn kiểm tra độ đầy đủ, tính không giao nhau và khả năng tái thiết tập dữ liệu logic |
| Replication | MonHoc dùng SQL Server transactional Publication, API chỉ ghi Publisher cấu hình và đối soát mọi site sau commit | Ảnh người dùng chứng minh UPDATE/phục hồi Q1 → Q7; evidence ngày 20/11/2026 có API views CRUD/retry SQL thật đủ Q1/Q7/TD. Còn browser end-to-end, outage TD và TD trên máy Minh Đức; KhoaHoc, Blog (`sync_blog`) và TaiKhoan (`sync_accounts`) dùng hàng đợi/ACK do ứng dụng cài, chưa có bằng chứng ba SQL Server thật cho ba bảng này |
| Distributed transaction | Chuyển cơ sở có trạng thái nguồn, sự kiện append-only và phục hồi tiến về phía trước | Ghi đúng giao thức thực tế, bảo đảm nhất quán và kết quả fault injection. Thiết kế hiện tại không bảo đảm ACID nguyên tử xuyên hai CSDL; nếu tiêu chí giảng viên yêu cầu giao dịch do DBMS quản lý, phải chốt và triển khai bổ sung, không tự ghi đã có MSDTC/2PC |
| Concurrency | Sức chứa lớp phải được bảo vệ cùng transaction tạo đăng ký/học phí | Cơ chế khóa/mức cô lập hoặc cập nhật có điều kiện phù hợp SQL Server; thời điểm cạnh tranh và kết quả hai phiên thực tế |
| Đồng bộ | Chỉ báo hoàn tất khi mọi site bắt buộc được xác nhận đã nhận thay đổi | Cách tiếp tục sau lỗi giữa chừng, version conflict, kết quả không rõ sau timeout và đọc đối soát từng bản sao |

MonHoc chuyển sang SQL Server transactional Publication; API chỉ ghi Publisher và biên nhận Logs trong transaction cục bộ, sau commit đối soát các Subscriber. Đây là bất đồng bộ, không phải ACID xuyên site. [Chính sách, cutover và bằng chứng](MonHoc-SQL-Replication.md). Các kết quả thử fan-out cũ bên dưới là bằng chứng lịch sử trước chuyển đổi, không xác nhận writer mới.

## 4. Kịch bản kiểm chứng có thể chạy lại

Chạy trên dữ liệu kiểm thử riêng, không thử lỗi trên dữ liệu thật. Ghi commit, phiên bản schema, topology, danh sách site hoạt động và dữ liệu ban đầu. Tên endpoint/method theo hợp đồng API đã được nhóm chốt; không tự coi đường dẫn đề xuất là đã hoạt động.

### TC-SITE-01 — Xác nhận site độc lập

1. Lập bảng site → máy/instance → database → alias kết nối; che thông tin xác thực.
2. Mở từng kết nối và đọc tên database/instance để xác nhận đang truy cập đúng DB. Ghi nhận Q1, Q7, TD; BT chỉ xuất hiện nếu đã cấu hình kịch bản site thứ tư.
3. Đối chiếu cùng phiên bản schema nhưng dữ liệu `LopHoc` khác nhau theo site.

**Đạt khi:** có 2–4 site theo cấu hình demo, đồ án mặc định là 3; các kết nối trỏ tới DB độc lập. Không dùng một DB có ba giá trị `branch_id` làm bằng chứng ba site.

### TC-FRAG-01 — Phân mảnh và tái thiết

1. Chuẩn bị danh sách lớp kiểm thử dự kiến theo từng site. Mảnh `LopHoc` tại site S gồm các dòng `ma_co_so = S`.
2. Đọc từng DB riêng: không có lớp sai site; các `DangKy` của lớp ở cùng site với lớp đó và có cha hợp lệ.
3. Lấy danh sách kết quả của từng site vào công cụ kiểm thử/API, kiểm tra không trùng khóa lớp giữa các mảnh và hợp lại đúng tập lớp dự kiến. Không ghi tập hợp vào DB trung tâm, không JOIN xuyên DB.

**Đạt khi:** không thiếu/thừa dòng trong tập kiểm thử, các mảnh lớp không giao nhau và tái thiết được tập logic. Không áp dụng máy móc “mã học viên chỉ xuất hiện ở một site”: hồ sơ cũ sau chuyển được giữ lịch sử; học viên hiện hành theo trạng thái/bước giao dịch trong tài liệu chuyển cơ sở.

### TC-REP-01 — Nhân bản thay đổi thực tế

1. Xác nhận Q1/Q7/TD đều hoạt động và có cùng môn học/`phien_ban`. Ghi trước giá trị ở từng DB; chọn môn thử phù hợp, không dùng dữ liệu thật quan trọng.
2. Đăng nhập Admin Big; gửi `PATCH /api/v1/admin/shared/subjects/{slug}/` với `Idempotency-Key` mới và chỉ các trường cần đổi. Không chạy UPDATE thủ công từng DB.
3. Đọc từng DB, so sánh `ma_mon`, `slug`, `ten_mon`, `mo_ta`, `phien_ban`. Chỉ Publisher có biên nhận `Logs` cùng transaction thay đổi; không yêu cầu ACK Logs ở Subscriber. Nếu API trả 202, đợi Agent rồi retry cùng key/body để xác nhận complete; không tự UPDATE từng bản sao.
4. Gửi lại chính xác request và cùng `Idempotency-Key`: phiên bản không tăng lần hai. Gửi body khác với key đó: API phải trả `409`.

**Đạt khi:** mọi bản sao bắt buộc có nội dung/phiên bản giống nhau; retry không tăng version lần hai. Biên nhận Publisher không tự chứng minh Subscriber đã nhận; cần đọc từng bản sao. Chỉ nạp `02_seed_shared_catalog.sql` chưa đạt. Kiểm thử API giả lập không thay thế dữ liệu thật: cần demo lưu thay đổi và ảnh/log không nhạy cảm. Ảnh SQL Q1 → Q7 ngày 20/11/2026 là bằng chứng UPDATE/phục hồi, chưa phải API/UI hoặc TD.

### TC-DTX-01 — Chuyển cơ sở và phục hồi

1. Chuẩn bị học viên Q1 đủ điều kiện chuyển sang Q7; lưu trạng thái nguồn/đích, công nợ và đăng ký liên quan.
2. Tư vấn Q1 tạo đề nghị `cho_duyet`; xác nhận chưa tạo hồ sơ đích. Kiểm tra Admin Small Q1 không được tạo đề nghị, Admin Big và Admin Small Q7 được phép duyệt, Admin Small Q1 không thể duyệt đề nghị Q1→Q7; Coordinator mới thực hiện chuyển.
3. Trường hợp thành công: kiểm tra nguồn `da_chuyen_di`, đích `dang_hoc`, cùng mã học viên và `ma_tai_khoan`; lịch sử ở nguồn được giữ; trạng thái giao dịch `hoan_tat`, sự kiện từng site khớp và thông báo được tạo tại Q7 cho nhân sự cơ sở nhận.
4. Thử riêng lỗi trước commit đích: nguồn giữ nguyên; retry hoặc kết thúc thất bại theo loại lỗi. Thử riêng dừng tiến trình sau commit đích: khởi động lại và recovery làm nốt nguồn; không xóa đích hoặc tạo hồ sơ thứ hai.
5. Kiểm tra Global Query trong khi đang xử lý và sau phục hồi theo quy tắc chọn bản hiện hành; không đếm cả hai bản vật lý.

**Đạt khi:** có thay đổi thực sự trên hai CSDL, tiến trình/sự kiện bền vững và phục hồi đúng giao thức đã chọn; bảo đảm của giao thức được trình bày đúng tiêu chí đánh giá. Chưa thống nhất cơ chế đáp ứng tiêu chí distributed transaction của giảng viên thì giữ trạng thái cần chốt, không tự đánh dấu đã đạt ACID.

### TC-CON-01 — Hai yêu cầu tranh chỗ cuối

1. Chuẩn bị một lớp còn đúng một chỗ, hai học viên khác nhau cùng site đủ điều kiện đăng ký, chưa đăng ký lớp đó và không trùng lịch.
2. Dùng hai phiên API/DB độc lập với hai yêu cầu riêng; cho chạy chồng lấp tại vùng kiểm tra/cập nhật sức chứa. Ghi mốc thời gian hoặc dùng điểm chờ trong bộ kiểm thử để chứng minh cạnh tranh thực sự. Không chỉ bấm hai lần tuần tự hoặc gửi lại cùng idempotency key.
3. Để hai yêu cầu hoàn tất; đọc `LopHoc`, `DangKy`, `HocPhi` và nhật ký tại site đó.
4. Kiểm tra yêu cầu thắng có đăng ký/học phí và tăng sĩ số đúng một; yêu cầu còn lại báo lớp đầy/xung đột theo hợp đồng, không có dữ liệu nghiệp vụ dở dang. Lặp lại với dữ liệu kiểm thử mới để xác nhận kết quả không phụ thuộc phiên nào thắng.

**Đạt khi:** đúng một yêu cầu thành công, sĩ số không vượt tối đa, không lost update; giao dịch thất bại rollback sạch. Nêu cơ chế bảo vệ phía API/DB đã dùng. Khóa nút frontend hoặc unique `(ma_hoc_vien, ma_lop)` không tự ngăn hai học viên khác nhau lấy cùng chỗ cuối.

### TC-DQ-01 — Truy vấn phân tán và kết quả thiếu site

1. Chuẩn bị dữ liệu học viên khác nhau tại ba site, gồm bản lịch sử đã chuyển; giữ dữ liệu ổn định trong lần đối chiếu tổng.
2. Chạy thống kê qua API/Coordinator, lưu dấu vết kết nối từng site, kết quả từng phần và kết quả gộp. Đối chiếu truy vấn cục bộ, chỉ tính bản hiện hành theo quy tắc chuyển.
3. Làm một site không phản hồi rồi chạy lại: response có `complete=false`, `missing_sites` và phần dữ liệu đã đọc được. Kết nối lại và đọc đủ các site.

**Đạt khi:** số liệu khớp dữ liệu tại các DB độc lập; kết quả thiếu được phân biệt với số 0/danh sách rỗng; không tạo DB tổng hợp. Kịch bản kiểm thử chuyển đang chạy dùng quy tắc riêng của TC-DTX-01, không giả định Global Query có snapshot ACID chung cho mọi site.

### TC-SYNC-01 — Đồng bộ sau lỗi site

1. Làm một site đang `hoat_dong` mất kết nối trước khi ghi bảng dùng chung: tiền kiểm phải từ chối, không sửa các bản sao còn lại.
2. Thử riêng sự cố sau tiền kiểm, khi một số site có thể đã commit: giữ mã thao tác/trạng thái từng site và báo chưa hoàn tất/cần đối soát. Không khẳng định rollback toàn hệ thống nếu cơ chế không hỗ trợ.
3. Khôi phục site, đọc lại trạng thái để xử lý cả kết quả chưa rõ do mất phản hồi. Retry cùng thao tác theo tiến trình đã lưu, không tạo nghiệp vụ hoặc tăng phiên bản lần hai tại site đã nhận.
4. Đối chiếu nội dung/phiên bản trên mọi site bắt buộc và sự kiện đồng bộ trước khi xác nhận hoàn tất. Không đổi site lỗi thành `dong_cua` chỉ để loại khỏi tập ghi.

**Đạt khi:** lỗi không bị che, tiến trình có thể phục hồi và các bản sao hội tụ đúng thay đổi. Replication và đồng bộ có thể dùng chung cơ chế, nhưng phải lưu bằng chứng riêng cho truyền thay đổi bình thường và lỗi/phục hồi.

## 5. Mẫu lưu bằng chứng và trạng thái

Mỗi lần chạy ghi trong tài liệu kết quả tại `docs/evidence/<ma-kich-ban>/<lan-chay>/` khi có bằng chứng thật; đường dẫn này là quy ước dự kiến, không khẳng định thư mục/kết quả đã tồn tại.

| Trường | Nội dung phải ghi |
|---|---|
| Nhận diện | Mã YC/TC, commit, người chạy, thời gian Việt Nam có offset `+07:00` |
| Môi trường | Site/máy/instance/database, schema, phiên bản công cụ, dữ liệu ban đầu; không chứa credential |
| Cách chạy | Script/lệnh/API, thông số không nhạy cảm, thứ tự; TC-CON-01 phải ghi hai phiên và cách tạo cạnh tranh |
| Đối chiếu | Kết quả mong đợi, kết quả thực tế, truy vấn trước–sau từng site, response và log đã lọc bí mật |
| Phục hồi | Điểm gây lỗi, trạng thái sau lỗi, retry/recovery và kết quả đối soát |
| Kết luận | Đạt / Không đạt / Chưa kiểm chứng; lý do, vấn đề còn mở và người review |

## 6. Trạng thái kiểm tra hiện tại (2026-10-29)

| Kịch bản | Trạng thái kiểm tra | Phần còn thiếu để kết luận đạt |
|---|---|---|
| TC-SITE-01 | Đã xác nhận cấu hình Q1/Q7/TD trỏ tới ba database riêng; cả ba đang ở cùng một SQL Server instance | Demo vật lý vẫn là một instance; nếu giảng viên yêu cầu máy chủ/site vật lý tách riêng thì cần topology tương ứng |
| TC-FRAG-01 | Script `30_enforce_site_fragment_boundaries.sql` chạy thành công trên cả ba DB; mỗi DB có 16 `CHECK` site-local. Script kiểm tra dữ liệu trước khi thêm constraint | Bảng nghiệp vụ hiện ít/không có dữ liệu kiểm thử; cần tạo bộ dữ liệu để chứng minh tái thiết mảnh và quan hệ cha/con |
| TC-REP-01 | Luồng `MonHoc` chạy thật qua 3 DB trong transaction kiểm thử rollback; retry cùng key hoạt động; sau rollback không còn thay đổi/ACK thử | Cần chạy demo giữ thay đổi trên dữ liệu thử và chụp kết quả trước/sau ở từng site |
| TC-SYNC-01 | Unit test mô phỏng lỗi ghi một site và xác nhận phản hồi chưa hoàn tất có nêu site lỗi; đây chưa phải outage SQL Server thật | Cần fault injection/outage trên topology nhiều site, khôi phục kết nối, retry cùng key và đối chiếu `Logs`/version |
| TC-DTX-01 | Source có luồng đề nghị → Admin Big hoặc Admin Small site nhận duyệt → Coordinator chuyển/retry; chưa chạy fault injection trên hai site | Cần bộ hồ sơ thử nguồn/đích, kiểm tra quyền duyệt đúng site, lỗi trước/sau commit đích, retry/recovery, giữ tài khoản, thông báo site nhận và Global Query |
| TC-CON-01 | Source bảo vệ sĩ số trong transaction cục bộ; unit tests không phải kiểm thử hai SQL session chạy đồng thời | Cần hai request/session độc lập tranh đúng chỗ cuối và đọc dữ liệu sau cùng |
| TC-DQ-01 | Đã gọi thống kê qua API với ba site đang sẵn sàng và response đầy đủ | Cần lặp lại với dữ liệu có học viên tại các site và thử một site thiếu để lưu bằng chứng |

Các kết quả trên không chứng minh replication cho `CoSo`/`KhoaHoc`, ACID xuyên site, SQL Server Publication, ba máy chủ vật lý hoặc hoàn tất mọi yêu cầu môn học. Không đánh dấu toàn bộ YC-01–YC-07 là đạt cho tới khi các thiếu sót trong bảng được chạy và lưu bằng chứng.

### Bổ sung kiểm chứng ngày 20/11/2026

Q7 hiện ở SQL Server container trên Mac Minh Khôi; Q1 và TD vẫn ở hai database
riêng trên Windows Quốc Hiếu. Đã bổ sung Subscriber TD hiện có, kiểm chứng
API views thêm/sửa/xóa `MonHoc` với commit và replication thật tới Q1/Q7/TD,
retry không tăng phiên bản và key khác body bị 409. Kết quả cuối đủ ba bản sao;
xem [TC-REP-01 và response](evidence/TC-REP-01/2026-11-20/README.md).
Người dùng đã cung cấp ảnh outage/khôi phục Q7 truyền bù thay đổi. Chưa có
browser end-to-end, outage TD, chuyển máy TD, concurrency hoặc fault injection
chuyển cơ sở trong đợt này. Bảng ngày 29/10 ở trên là lịch sử, không phản ánh
topology hiện tại. Không kết luận toàn bộ YC-01–YC-07 đã đạt.
### Bổ sung đồng bộ ngoài MonHoc — 26/11/2026

Ngoài `MonHoc`, ba loại dữ liệu hiện có cơ chế đồng bộ do ứng dụng cài, ghi ở [giao dịch phân tán](QLTTNN-Giao-Dich-Phan-Tan.md): `KhoaHoc` (`sync_courses`), Blog (`sync_blog`, hàng đợi `BLINT-`/`BLFIN-`/`BLREV-` trong `Logs`) và `TaiKhoan` (trigger → `DongBoTaiKhoan` → `sync_accounts`). Bảng `NguoiDung` chỉ tồn tại tại authority và không nhân bản. Với TC-REP-01/TC-SYNC-01, ba cơ chế này mới có kiểm thử giả lập (bộ `manage.py test` đạt 264 ca ngày 26/11/2026) và kiểm tra SQL thật chỉ trên Q1; migration 47, 48, 49 đã chạy ở Q1, 47 và 48 đã chạy ở TD (database `QLTTNN_TD_MOI` trên máy khác Q1, ngày 26/11/2026), chưa chạy ở Q7 (không truy cập được). Cùng ngày đã chạy bốn kịch bản trên hai database tạm cùng instance (không phải ba server vật lý, không phải Q1/Q7/TD): [TC-FRAG-01](evidence/TC-FRAG-01/2026-11-26/README.md), [TC-CON-01](evidence/TC-CON-01/2026-11-26/README.md), [TC-DQ-01](evidence/TC-DQ-01/2026-11-26/README.md) và [TC-SYNC-01](evidence/TC-SYNC-01/2026-11-26/README.md) (hàng đợi tài khoản và Blog qua outage); bộ chạy lại ở [evidence/scripts](evidence/scripts/README.md). Cả bốn đạt trong phạm vi đó. Hai phát hiện, đều đã sửa và có test: lỗi hội tụ của hàng đợi Blog khi sửa liên tiếp một bài, và `InterfaceError` khi database offline trên instance còn sống (nay được báo là site thiếu, xem TC-DQ-01). Chưa có bằng chứng trên Q1/Q7/TD thật, chưa thử tắt máy hoặc ngắt VPN thật, nên YC-01 và YC-07 vẫn chưa đạt đầy đủ.

## 7. Tài liệu phải khớp nhau

- [AGENTS.md](../AGENTS.md): quy tắc bắt buộc cho thành viên/AI; giữ quy trình Git.
- [README](../README.md), [FS](../fs/Functional-Specification.md): phạm vi 2–4 site, năm nội dung chứng minh, đồng bộ và tiêu chí nghiệm thu.
- [Schema, ERD và mô hình dữ liệu](DATABASE_SCHEMA.md), [DB/scripts](../db/README.md): phân mảnh, bản sao, ràng buộc và giới hạn của seed/verify cục bộ.
- [Kiến trúc và source](QLTTNN-Huong-Dan-Source.md), [giao dịch](QLTTNN-Giao-Dich-Phan-Tan.md): trách nhiệm module, commit, cạnh tranh và phục hồi.
- [API](../specs/api.md), [UI](../specs/ui-ux.md): API quyết định kết quả; UI thể hiện xung đột, đang xử lý, chưa đồng bộ và kết quả thiếu site.
- [Làm việc nhóm và kế hoạch](QLTTNN-Lam-Viec-Nhom.md), [đề cương](QLTTNN-De-Cuong-Bao-Cao.md), [hướng dẫn mạng](QLTTNN-Huong-Dan-Ket-Noi-ZeroTier-SQL-Server.md): người phụ trách, trình tự chạy, ảnh và bằng chứng cần thu.
