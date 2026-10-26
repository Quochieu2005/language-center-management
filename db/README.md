# Khởi tạo CSDL phân tán

Thư mục này chứa script SQL Server để dựng **ba CSDL riêng**, cùng schema nhưng lưu dữ liệu theo từng cơ sở. Cần SQL Server 2012 trở lên và SSMS có SQLCMD Mode. Đây là phần cài đặt vật lý ban đầu của Đề tài 10; nó không tạo một CSDL trung tâm có cột phân loại chi nhánh.

## Yêu cầu chung và giới hạn của bộ script

Môn học yêu cầu **2–4 site**; nhóm dùng 3 DB Q1/Q7/TD. Phải có phân mảnh, replication, transaction và đồng bộ; chứng minh ít nhất một phương pháp phân mảnh, một phương pháp replication, một distributed transaction, một tình huống concurrency và một distributed query. Các nhóm được chọn kiểu phân mảnh phù hợp. Xem [yêu cầu chung](../README.md#yêu-cầu-chung-áp-dụng-cho-mọi-đề-tài) và [kịch bản demo](../README.md#6-kịch-bản-demo) trong README chính.

- Schema/seed/verify hỗ trợ TC-SITE-01 và TC-FRAG-01; đọc riêng từng DB để đối chiếu mảnh và dữ liệu cha/con.
- `02_seed_shared_catalog.sql` là nạp ban đầu; không tự triển khai phương pháp replication runtime. YC-03/YC-07 phải có TC-REP-01/TC-SYNC-01: một thay đổi truyền đến bản sao và lỗi/phục hồi.
- Bảng trạng thái/sự kiện hỗ trợ Coordinator, không tự chạy distributed transaction hoặc bảo đảm ACID xuyên site. TC-DTX-01 cần nghiệp vụ nguồn/đích và cơ chế đã chốt chạy thật.
- TC-CON-01 cần hai phiên cạnh tranh chỗ cuối, cơ chế bảo vệ sức chứa và đọc lại `LopHoc`/`DangKy`/`HocPhi`; các ràng buộc/verify cục bộ không đủ thay bài thử này.
- TC-DQ-01 cần đọc các DB rồi tổng hợp tại API; không thay bằng JOIN xuyên DB. Chạy xong script khởi tạo chưa có nghĩa đã đạt toàn bộ yêu cầu môn học.

## Các file

| File | Mục đích |
|---|---|
| `00_create_databases.sql` | Tạo `QLTTNN_Q1`, `QLTTNN_Q7`, `QLTTNN_TD` trên SQL Server hiện tại nếu chưa có. |
| `01_create_schema.sql` | Tạo bảng, khóa, ràng buộc, chỉ mục và sequence trong **một** database đích. Chạy riêng một lần cho mỗi database. |
| `02_seed_shared_catalog.sql` | Nạp cùng danh sách cơ sở, môn học và khóa học vào database đích. Chạy cho cả ba database. Không tạo tài khoản hoặc mật khẩu mẫu. |
| `03_seed_demo_site.sql` | Tùy chọn: thêm một học viên, giáo viên, nhân viên, phòng, lớp, đăng ký, học phí, phiếu thu và điểm tại site đích để thử các luồng. Chạy tối đa một lần cho mỗi site. |
| `04_verify_database.sql` | Kiểm tra database đang chọn, các bảng cốt lõi, dữ liệu danh mục và ràng buộc cục bộ. Chạy riêng tại từng site. |
| `05_database_roles.sql` | Tạo role database cho API và truy vấn chỉ đọc; không tạo SQL login hay mật khẩu. Chạy riêng tại từng site. |
| `06_add_oauth_identity_table.sql` | Migration an toàn để thêm bảng liên kết danh tính Google/Facebook vào CSDL site đã được tạo trước đó. Chạy riêng tại từng site; database mới đã có bảng này từ `01_create_schema.sql`. |

## Chạy bằng SSMS

1. Kết nối tới **SQL Server Database Engine** bằng SSMS. Mở `00_create_databases.sql`, xem lại tên instance rồi chạy. Script chỉ tạo database còn thiếu; script không xóa hoặc ghi đè database hiện có.
2. Mở `01_create_schema.sql`. Trong SSMS bật **Query → SQLCMD Mode**. Dòng `:setvar DatabaseName "QLTTNN_Q1"` là database đích; chọn một trong ba tên `QLTTNN_Q1`, `QLTTNN_Q7`, `QLTTNN_TD`, chạy script, rồi đổi tên và chạy lại cho hai database còn lại.
3. Lặp bước tương tự với `02_seed_shared_catalog.sql`. Danh mục dùng chung phải giống nhau ở cả ba site.
4. Nếu cần dữ liệu để demo, bật SQLCMD Mode trong `03_seed_demo_site.sql`, đặt cả `DatabaseName` và `SiteCode` theo site đang seed, rồi chạy một lần tại mỗi site. Script chỉ tạo dữ liệu kiểm thử và không tạo tài khoản/mật khẩu.
5. Với database đã tạo trước khi có OAuth, chạy `06_add_oauth_identity_table.sql` riêng trên từng site. Thay `DatabaseName` mỗi lần; chạy cho tất cả site đang hoạt động để bảng dùng chung tồn tại cùng cấu trúc. Script không thêm tài khoản/liên kết mẫu và không sửa dữ liệu khác.
6. Lặp bước tương tự với `04_verify_database.sql` để kiểm tra từng database. Kết quả của ba lần chạy phải cho thấy cùng schema và danh mục; bảng nghiệp vụ có thể có dữ liệu khác nhau theo site.
7. Chạy `05_database_roles.sql` trong từng database. DBA tạo SQL login/user theo cấu hình môi trường rồi thêm database user vào `qlttnn_api` hoặc `qlttnn_readonly`. Không đưa mật khẩu vào script hoặc repository.

`01_create_schema.sql` chỉ dành cho database mới/chưa có bảng. Nếu đã có bảng, script sẽ dừng thay vì âm thầm sửa dữ liệu. Không dùng lệnh `DROP DATABASE` để xử lý lỗi; kiểm tra database đích và sao lưu trước khi quyết định cách khôi phục.

## Quy tắc dữ liệu

- Mỗi cơ sở có một database riêng. Khóa ngoại chỉ trỏ tới bảng trong database đó; không có khóa ngoại hoặc JOIN giữa database của các cơ sở.
- Khi demo trên một máy, có thể đặt cả ba database trên một SQL Server instance nhưng vẫn dùng tên database/kết nối riêng. `00_create_databases.sql` dành cho cách cài này. Nếu triển khai mỗi site trên một SQL Server khác nhau, chỉ tạo database của site tương ứng trên máy đó rồi chạy schema/seed/role riêng qua kết nối của site đó; không tạo cả ba database lặp lại trên từng máy.
- `CoSo`, `MonHoc`, `KhoaHoc`, `TaiKhoan`, `TaiKhoanLienKetOAuth` là dữ liệu nhân bản theo schema. Script seed chỉ thêm dữ liệu danh mục ban đầu; tài khoản phải được tạo qua ứng dụng với mật khẩu đã băm. Liên kết OAuth chỉ được thêm sau khi người dùng đã xác thực vào tài khoản nội bộ; không tạo liên kết mẫu.
- Script seed danh mục là thao tác nạp ban đầu, chưa phải đồng bộ runtime. Khi API được triển khai, mọi thay đổi danh mục dùng chung phải qua một luồng `REPLICATED-WRITE` tới các site đang hoạt động và phải đối soát lỗi.
- Các bảng nghiệp vụ và bảng con được lưu tại site tương ứng. Cột `ma_co_so` trên bảng con là khóa phân mảnh để database kiểm tra các quan hệ cùng site bằng khóa ngoại ghép.
- `GiaoDichChuyenCoSo` chỉ có bản ghi trong database của site nguồn; Admin Small tạo đề nghị `cho_duyet` tại đó, Admin Big quyết định qua Coordinator, và chỉ trạng thái đã duyệt mới được worker chuyển cơ sở xử lý. Bảng lưu người đề nghị, người quyết định và lý do; unique index giới hạn mỗi học viên còn tối đa một đề nghị/giao dịch mở. `LichSuChuyenCoSo` là nhật ký append-only tại nơi hành động xảy ra (nguồn hoặc đích); `ma_chuyen` chỉ dùng để đối chiếu giữa hai database, không tạo khóa ngoại xuyên site.
- Ràng buộc duy nhất xuyên database (ví dụ tên đăng nhập/email) và quy tắc một tài khoản chỉ gắn với một hồ sơ nhân sự được Coordinator/API kiểm tra; một database site không thể tự bảo đảm các quy tắc đó cho những database còn lại.
- Các sequence `Seq_*` chỉ cấp số thứ tự từ 1 đến 999999. Django/API phải ghép mã site và mã loại, ví dụ `Q1-HV-000001`; số có thể bị khuyết nếu một giao dịch lấy sequence rồi rollback, điều này bình thường.
- `ma_mon` và `ma_khoa_hoc` là mã danh mục dùng chung ổn định, không tạo sequence riêng theo site. `CoSo.ma_co_so` chính là mã cơ sở `Q1`, `Q7`, `TD`.
- Hộp thư Admin Big dùng Global Query: Coordinator hỏi từng database site, gộp danh sách trong ứng dụng, không tạo bảng/DB trung tâm. Quyết định được ghi tại database nguồn; giao dịch chuyển cơ sở chỉ bắt đầu sau khi duyệt. Bộ script này không tạo Linked Server, Publication, VPN hay một kho dữ liệu tập trung.
- Giao dịch chuyển cơ sở gồm nhiều transaction cục bộ được điều phối qua hai database; schema hỗ trợ phục hồi tiến về phía trước và không tự tạo cam kết ACID nguyên tử xuyên database. Khi đích đã commit, không xóa hồ sơ đích để giả vờ hoàn tác; Coordinator phải hoàn tất bước nguồn khi kết nối hồi phục.

Khi thay đổi cấu trúc, cập nhật `docs/DATABASE_SCHEMA.md` và README trong cùng thay đổi. Chi tiết chính sách dữ liệu nằm ở [schema](../docs/DATABASE_SCHEMA.md), luồng nghiệp vụ ở [README](../README.md).
