# Môn học: một Publisher, các bản sao SQL Server

## Quyết định triển khai

Liên hệ lý thuyết GV-03: đây là **lazy/centralized, một nơi ghi**, không phải eager/quorum/multi-master. Xem [đối chiếu tài liệu giảng viên](QLTTNN-De-Cuong-Bao-Cao.md#tai-lieu-giang-vien) và [sơ đồ cấp phát](DATABASE_SCHEMA.md#phan-manh). Từ “transactional” không tự bảo đảm ACID giữa các database.

`MonHoc` chuyển từ fan-out tại API sang transactional replication của SQL Server.
Publisher được cấu hình bằng `MONHOC_PUBLISHER_SITE_CODE` (mặc định `Q1`), độc lập
với `AUTH_SESSION_SITE_CODE`. Danh sách site bắt buộc lấy từ `CoSo.hoat_dong`,
không chỉ từ danh sách Subscription hoặc các kết nối hiện có.

Admin Big vẫn dùng POST/PATCH/DELETE `/api/v1/admin/shared/subjects/`.
API chỉ ghi `MonHoc` và biên nhận append-only `Logs` tại Publisher trong một
transaction cục bộ. SQL Server Agent chuyển `MonHoc` tới Subscriber; không nhân
bản `Logs` và không để API ghi lại `MonHoc` tại Subscriber. Đây là
`REPLICATED-WRITE` bất đồng bộ, không phải ACID xuyên site.

Trước yêu cầu mới, API kiểm tra các bản sao đang hoạt động đồng nhất; thiếu site
thì chưa ghi. Xóa còn kiểm tra `KhoaHoc` tại mọi site và dùng khóa điều phối
khóa học hiện có để tránh đua với tạo/sửa khóa học qua API.
Sau khi Publisher commit, API đọc lại từng bản sao theo `ma_mon`, so sánh mã,
slug, tên, mô tả và phiên bản (xóa thì xác nhận không còn mã hoặc slug cũ).
Chỉ trả `complete=true` khi mọi site hoạt động được xác nhận có kết quả đúng.
Nếu bản sao chậm, mất kết nối, hoặc TD chưa có Subscription và dữ liệu chưa đổi,
trả HTTP 202, `complete=false`, `missing_sites`; không ghi bù trực tiếp.

Retry cùng `Idempotency-Key`, người dùng, route và payload chỉ đọc biên nhận tại
Publisher và kiểm tra lại bản sao, không tăng phiên bản hay ghi lại dữ liệu.
Cùng key khác nội dung bị 409. Nếu Publisher đã thay đổi sau biên nhận thì trả
409 yêu cầu đối soát, không phát lại thay đổi cũ. Biên nhận xác nhận Publisher
commit, không phải ACK chứng minh Subscriber đã nhận. Lỗi không rõ commit trả
503 và giữ nguyên key để retry.

## Chuyển đổi và vận hành

1. Dừng ghi môn học trên website trong lúc chuyển đổi. Đối soát mọi thao tác
   fan-out cũ chưa hoàn tất trước khi dùng writer mới; key của cơ chế cũ không
   tự chuyển thành biên nhận SQL replication.
2. Chuẩn bị cùng schema/dữ liệu `MonHoc` và Subscription tại mọi site hoạt động.
   Không drop/truncate bảng đang được `KhoaHoc` tham chiếu. Khởi tạo dữ liệu có
   sẵn cần đối chiếu rồi dùng `replication support only` phù hợp.
3. Cấu hình Publisher và kết nối qua Site Router; chạy Log Reader/Distribution
   Agent. Không dùng tài khoản API để sửa trực tiếp bảng Subscriber.
4. Chạy POST/PATCH/DELETE qua API, kiểm tra 202 → retry cùng key → complete;
   thử trùng key khác body và mất kết nối/khôi phục. Chỉ xóa môn thử không có
   khóa học tham chiếu. Không tự động sửa dữ liệu trên các Subscriber.

`KhoaHoc`, tài khoản và Blog giữ cơ chế riêng; `KhoaHoc` dùng outbox/fan-out ở
tầng ứng dụng theo tài liệu schema. Chưa chuyển chúng sang SQL replication;
tuyệt đối không tự tạo Publication cho toàn bộ bảng nghiệp vụ.
Global Query trên website vẫn đọc từng kết nối và tổng hợp tại API, không JOIN
xuyên site. Linked Server chỉ dùng trong kiểm chứng SQL của bài thực hành.

## Bằng chứng hiện có và giới hạn

Ngày 20/11/2026, Quốc Hiếu cung cấp ảnh SSMS: sửa `MH-ENG` tại Q1 được truyền
sang Q7 trên Mac; dừng container Q7, sửa tại Q1, bật lại Q7 và đọc thấy thay đổi;
sau đó trả tên `Tiếng Anh` và đối chiếu hai bản sao. Đây là bằng chứng UPDATE và
đồng bộ bù Q1 → Q7 do người dùng thực hiện, không phải kiểm thử API tự động.
Người dùng cũng cung cấp ảnh tạo `MH-TEST-Q7` trên website và đọc được tại SQL
Server Q7 trên Mac bằng VS Code mssql. Đây là bằng chứng INSERT từ website tới
Q7; lúc đó TD thiếu môn thử nên trang quản trị khóa ghi đúng chính sách đối soát.

Kiểm tra code sau chuyển đổi: `manage.py test core.catalog --noinput` chạy 26
tests thành công (gồm kiểm tra Publisher-only, session Q7 không đổi Publisher,
retry không ghi lại, key/body/người dùng xung đột, đổi slug, chặn xóa khi có khóa
học ở Q7, rollback khi biên nhận lỗi, xác nhận sau commit và phục hồi giả lập).
Đây là kiểm thử giả lập, không thay thế runtime SQL nhiều site.

### Bổ sung TD hiện có và kiểm chứng API ngày 20/11/2026

Theo lựa chọn của Quốc Hiếu, TD vẫn ở Windows `DESKTOP-CK4K90F`, database
`QLTTNN_TD`; chưa chuyển sang máy Minh Đức. Đã lưu bản trước của `MonHoc` ngoài
repository, đối chiếu từng dòng: hai môn cũ khớp hoàn toàn, chỉ thiếu
`MH-TEST-Q7`. Bổ sung đúng dòng thiếu, không cập nhật/xóa môn cũ và không đụng
`HocVien`, `LopHoc`, `DangKy`, `HocPhi` hoặc `.env`/comment của người dùng.

Đã thêm push Subscription của `PUB_QLTTNN_MonHoc` tới database `QLTTNN_TD`
trên cùng instance Windows, khởi tạo `replication support only` sau khi dữ liệu
ban đầu khớp. Distribution Agent dùng Windows Authentication tại instance cục
bộ. Không drop/truncate bảng, không tạo lại Publication Q7 và không nhân bản
toàn bộ database. Việc bổ sung dữ liệu ban đầu tự nó không phải bằng chứng
replication; thay đổi mới qua Publisher dưới đây mới kiểm chứng truyền dữ liệu.
Quy trình khởi tạo tham chiếu [Microsoft Learn](https://learn.microsoft.com/en-us/sql/relational-databases/replication/initialize-a-subscription-manually).

| Phép thử với môn tạm `MH-RT-8A293A34` | Kết quả thực tế |
|---|---|
| POST tạo tại API view | 202 khi chờ bản sao; retry cùng key đến 201, `complete=true`, `sites=[Q1,Q7,TD]`, phiên bản 1 |
| PATCH tên/mô tả, thay slug | 202 → 200, đủ ba site, phiên bản 2 |
| Retry PATCH sau hoàn tất | 200, `idempotent_replay=true`, phiên bản vẫn 2 |
| Cùng key POST nhưng đổi body | 409, không ghi lại |
| DELETE môn tạm chưa có khóa học | 202 → 200; đọc từng kết nối xác nhận mã đã mất tại cả ba site |
| Danh sách cuối | `complete=true`, `missing_sites=[]`, `inconsistent_sites=[]`, giữ ba môn ban đầu kể cả môn thử do người dùng tạo |

Phép thử gọi Django API views bằng `APIRequestFactory` với danh tính Admin Big
được gán trong bộ chạy kiểm chứng, còn mọi đọc/ghi, commit và replication dùng
SQL Server thật. Không giả lập service/connection và không bọc phép thử trong
transaction rollback. Môn tạm được xóa qua chính API; biên nhận `Logs` giữ lại.
Đây chưa phải kiểm thử cookie/CSRF, HTTP hoặc thao tác trình duyệt end-to-end.

`manage.py test core.catalog --noinput`: 26 tests đạt. Bộ rộng hơn gồm catalog,
classes, students, academics chạy 65 tests nhưng còn 1 failure/7 errors ở các
test quyền lớp, học viên và fixture đăng nhập; không kết luận toàn bộ Q7 đã đạt.
Concurrency tranh chỗ cuối và chuyển cơ sở có fault injection chưa kiểm chứng
live trong đợt này. Khi chuyển TD sang máy Minh Đức phải cấu hình lại Subscriber
và kiểm chứng kết nối/đồng bộ; Subscription TD hiện tại chỉ phục vụ bản Windows.
