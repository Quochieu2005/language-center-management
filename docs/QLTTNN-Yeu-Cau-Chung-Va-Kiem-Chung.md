# Yêu cầu chung và kịch bản kiểm chứng CSDL phân tán

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
| YC-04 | Ít nhất 1 distributed transaction | Chuyển học viên Q1 → Q7 sau khi Admin Big duyệt | TC-DTX-01 | B + A + D |
| YC-05 | Ít nhất 1 tình huống concurrency | Hai học viên tranh chỗ cuối trong cùng lớp bằng hai phiên đồng thời | TC-CON-01 | D + A + B |
| YC-06 | Ít nhất 1 distributed query | Thống kê học viên từ từng site rồi tổng hợp tại API | TC-DQ-01 | B + E |
| YC-07 | Đồng bộ dữ liệu | Đối soát, retry và phục hồi bản sao khi một site lỗi | TC-SYNC-01 | A + B + C |

E phối hợp lưu kết quả/demo; Quốc Hiếu review trước khi nhóm ghi đạt. Năm nội dung chứng minh tối thiểu là YC-02 đến YC-06; YC-01 và YC-07 vẫn bắt buộc. Sáu nghiệp vụ đề tài trong README/FS phải được thực hiện đồng thời với các yêu cầu chung này.

## 3. Cơ chế cần ghi rõ trước khi triển khai

| Nội dung | Đã xác định trong thiết kế | Cần chốt/kiểm chứng |
|---|---|---|
| Phân mảnh | Ngang theo site và dẫn xuất theo bảng cha; JOIN/FK chỉ trong site | Truy vấn kiểm tra độ đầy đủ, tính không giao nhau và khả năng tái thiết tập dữ liệu logic |
| Replication | Bản sao đầy đủ của các bảng dùng chung được schema cho phép; một điểm vào ghi trong Coordinator | Phương pháp truyền thay đổi, nơi được phép ghi, phiên bản, ACK từng site, xử lý xung đột, lưu tiến trình và retry. Nếu dùng SQL Server Publication, ghi publisher/distributor/subscriber và article; không có hai cơ chế ghi trùng cùng bảng |
| Distributed transaction | Chuyển cơ sở có trạng thái nguồn, sự kiện append-only và phục hồi tiến về phía trước | Ghi đúng giao thức thực tế, bảo đảm nhất quán và kết quả fault injection. Thiết kế hiện tại không bảo đảm ACID nguyên tử xuyên hai CSDL; nếu tiêu chí giảng viên yêu cầu giao dịch do DBMS quản lý, phải chốt và triển khai bổ sung, không tự ghi đã có MSDTC/2PC |
| Concurrency | Sức chứa lớp phải được bảo vệ cùng transaction tạo đăng ký/học phí | Cơ chế khóa/mức cô lập hoặc cập nhật có điều kiện phù hợp SQL Server; thời điểm cạnh tranh và kết quả hai phiên thực tế |
| Đồng bộ | Chỉ báo hoàn tất khi mọi site bắt buộc được xác nhận đã nhận thay đổi | Cách tiếp tục sau lỗi giữa chừng, version conflict, kết quả không rõ sau timeout và đọc đối soát từng bản sao |

Đây không phải lựa chọn công cụ mới đã được duyệt. Người triển khai ghi quyết định vào README mục 9, FS mục 11 và tài liệu kỹ thuật liên quan; cập nhật schema/script nếu cơ chế cần thêm bảng/cột. Schema hiện chỉ định nghĩa `NhatKyDongBo` dạng log append-only, chưa chốt liệu log có đủ làm tiến trình durable/đối soát replication hay cần outbox/bảng trạng thái riêng; phải giải quyết OPEN-14 trước khi code phụ thuộc vào retry. Đăng ký với transaction cục bộ giúp kiểm chứng rollback, nhưng không thay thế YC-04. Phục hồi chuyển cơ sở cũng không thay thế việc chứng minh replication YC-03.

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

1. Chốt cơ chế replication và xác nhận các site hoạt động sẵn sàng. Chụp dữ liệu/`phien_ban` của một môn học kiểm thử ở từng site trước thao tác.
2. Admin Big sửa môn học qua điểm vào ghi được phép. Cơ chế replication truyền thay đổi; không chạy tay cùng một lệnh UPDATE trên từng DB để giả lập.
3. Đọc riêng từng bản sao, đối chiếu khóa, nội dung và phiên bản; lưu dấu vết truyền thay đổi/ACK hoặc log cơ chế thực tế.

**Đạt khi:** mọi bản sao bắt buộc có nội dung và phiên bản của thay đổi đã xác nhận. Chỉ nạp `02_seed_shared_catalog.sql` chưa đạt kịch bản này. Có Publication nhưng chưa chứng minh thay đổi đến subscriber cũng chưa đạt.

### TC-DTX-01 — Chuyển cơ sở và phục hồi

1. Chuẩn bị học viên Q1 đủ điều kiện chuyển sang Q7; lưu trạng thái nguồn/đích, công nợ và đăng ký liên quan.
2. Admin Small Q1 tạo đề nghị `cho_duyet`; xác nhận chưa tạo hồ sơ đích. Admin Big duyệt; Coordinator mới thực hiện chuyển.
3. Trường hợp thành công: kiểm tra nguồn `da_chuyen_di`, đích `dang_hoc`, cùng mã học viên; lịch sử ở nguồn được giữ; trạng thái giao dịch `hoan_tat` và sự kiện từng site khớp.
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

Trong đợt cập nhật tài liệu này **chưa chạy các kịch bản trên hệ thống thật**. Không chuyển trạng thái sang “Đạt” chỉ vì đã bổ sung bảng tiêu chí. Bộ script SQL, Swagger và UI phải có kiểm thử tại các site thực tế trước khi được dùng làm bằng chứng.

## 6. Tài liệu phải khớp nhau

- [AGENTS.md](../AGENTS.md): quy tắc bắt buộc cho thành viên/AI; giữ quy trình Git.
- [README](../README.md), [FS](../fs/Functional-Specification.md): phạm vi 2–4 site, năm nội dung chứng minh, đồng bộ và tiêu chí nghiệm thu.
- [Schema](DATABASE_SCHEMA.md), [mô hình dữ liệu](QLTTNN-Du-Lieu.md), [db/README](../db/README.md): phân mảnh, bản sao, ràng buộc và giới hạn của seed/verify cục bộ.
- [Kiến trúc](QLTTNN-Kien-Truc.md), [source](QLTTNN-Huong-Dan-Source.md), [giao dịch](QLTTNN-Giao-Dich-Phan-Tan.md): trách nhiệm module, commit, cạnh tranh và phục hồi.
- [API](../specs/api.md), [UI](../specs/ui-ux.md): API quyết định kết quả; UI thể hiện xung đột, đang xử lý, chưa đồng bộ và kết quả thiếu site.
- [Kế hoạch](QLTTNN-Ke-Hoach-Trien-Khai.md), [làm việc nhóm](QLTTNN-Lam-Viec-Nhom.md), [đề cương](QLTTNN-De-Cuong-Bao-Cao.md), [hướng dẫn mạng](QLTTNN-Huong-Dan-Ket-Noi-ZeroTier-SQL-Server.md): người phụ trách, trình tự chạy, ảnh và bằng chứng cần thu.
