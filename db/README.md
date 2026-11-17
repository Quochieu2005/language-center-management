# Khởi tạo CSDL phân tán

Thư mục này chứa script SQL Server để dựng **ba CSDL riêng**, cùng schema nhưng lưu dữ liệu theo từng cơ sở. Cần SQL Server 2012 trở lên và SSMS có SQLCMD Mode. Đây là phần cài đặt vật lý ban đầu của Đề tài 10; nó không tạo một CSDL trung tâm có cột phân loại chi nhánh.

## Yêu cầu chung và giới hạn của bộ script

Môn học yêu cầu **2–4 site**; nhóm dùng 3 DB Q1/Q7/TD. Phải có phân mảnh, replication, transaction và đồng bộ; chứng minh ít nhất một phương pháp phân mảnh, một phương pháp replication, một distributed transaction, một tình huống concurrency và một distributed query. Các nhóm được chọn kiểu phân mảnh phù hợp. Xem [yêu cầu chung](../README.md#yêu-cầu-chung-áp-dụng-cho-mọi-đề-tài) và [kịch bản demo](../README.md#6-kịch-bản-demo) trong README chính.

- Schema/seed/verify hỗ trợ TC-SITE-01 và TC-FRAG-01; đọc riêng từng DB để đối chiếu mảnh và dữ liệu cha/con.
- `02_seed_shared_catalog.sql` chỉ nạp ban đầu. Runtime replication tối thiểu cho `MonHoc` dùng `PATCH /api/v1/admin/shared/subjects/{slug}/`, Admin Big và ACK trong `Logs`; outage/recovery qua mạng thật vẫn phải chạy TC-SYNC-01.
- Bảng trạng thái/sự kiện hỗ trợ Coordinator, không tự chạy distributed transaction hoặc bảo đảm ACID xuyên site. TC-DTX-01 cần nghiệp vụ nguồn/đích và cơ chế đã chốt chạy thật.
- TC-CON-01 cần hai phiên cạnh tranh chỗ cuối, cơ chế bảo vệ sức chứa và đọc lại `LopHoc`/`DangKy`/`HocPhi`; các ràng buộc/verify cục bộ không đủ thay bài thử này.
- TC-DQ-01 cần đọc các DB rồi tổng hợp tại API; không thay bằng JOIN xuyên DB. Chạy xong script khởi tạo chưa có nghĩa đã đạt toàn bộ yêu cầu môn học.

## Các file

| File | Mục đích |
|---|---|
| `00_create_databases.sql` | Tạo `QLTTNN_Q1`, `QLTTNN_Q7`, `QLTTNN_TD` trên SQL Server hiện tại nếu chưa có. |
| `01_create_schema.sql` | Tạo bảng, khóa, ràng buộc, chỉ mục và sequence trong **một** database đích. Chạy riêng một lần cho mỗi database. |
| `02_seed_shared_catalog.sql` | Nạp cùng danh sách cơ sở và môn học vào database đích. Chạy cho cả ba database. Không thêm khóa học, tài khoản hoặc mật khẩu mẫu. |
| `03_seed_demo_site.sql` | Tùy chọn: thêm một học viên, giáo viên, nhân viên, phòng, lớp, đăng ký, học phí, phiếu thu và điểm tại site đích để thử các luồng. Chạy tối đa một lần cho mỗi site. |
| `04_verify_database.sql` | Kiểm tra database đang chọn, các bảng cốt lõi, dữ liệu danh mục và ràng buộc cục bộ. Chạy riêng tại từng site. |
| `05_database_roles.sql` | Tạo role database cho API và truy vấn chỉ đọc; không tạo SQL login hay mật khẩu. Chạy riêng tại từng site. |
| `06_add_oauth_identity_table.sql` | Legacy/không còn dùng; không chạy cho schema hiện tại. Subject OAuth hiện nằm trong `TaiKhoan`, được bảo đảm bởi migration 27. |
| `07_add_auth_session_tables.sql` | Thêm phiên đăng nhập có thể thu hồi và sự kiện đăng nhập cho DB site; migration 26 chuyển log sự kiện cũ sang `Logs`. |
| `08_promote_admin_role_to_admin_big.sql` | Chuyển role quản trị cũ sang giá trị `admin_big` trên từng site. |
| `09_add_account_slug_and_rename_password_column.sql` | Bổ sung slug tài khoản và chuẩn hóa tên cột mật khẩu. |
| `10_add_public_slugs.sql` | Bổ sung/kiểm tra slug duy nhất cho cơ sở, môn học và khóa học. |
| `12_admin_password_reset_otp.sql` | Bổ sung cấu trúc OTP đặt lại mật khẩu và sự kiện reset cho tài khoản quản trị. |
| `13_admin_small_provisioning.sql` | Legacy/không còn dùng; hồ sơ Admin Small hiện ở `dbo.Admin`, không tạo bảng điều phối riêng. |
| `14_admin_small_deactivation.sql` | Legacy/không còn dùng; trạng thái được lưu trực tiếp trên `Admin` và `TaiKhoan`. |
| `15_admin_big_profile_update.sql` | Bổ sung cấu trúc cần cho Admin Big tự cập nhật hồ sơ tài khoản. |
| `16_teacher_lifecycle.sql` | Legacy/không còn dùng; trạng thái hồ sơ giáo viên nằm ở `GiaoVien`, trạng thái tài khoản ở `TaiKhoan`. |
| `17_account_status_lifecycle.sql` | Legacy/không còn dùng; trạng thái hoạt động nằm trực tiếp trong `TaiKhoan.trang_thai`. |
| `18_add_notifications.sql` | Thêm bảng thông báo quản trị theo từng database site. |
| `19_enable_student_accounts.sql` | Bật liên kết tài khoản học viên trong schema; chỉ áp dụng sau khi nhóm duyệt phạm vi portal. |
| `20_student_account_coordinator.sql` | Legacy/không còn dùng; liên kết tài khoản học viên dùng `HocVien.ma_tai_khoan`. |
| `21_enable_student_account_deactivation.sql` | Legacy/không còn dùng; trạng thái tài khoản nằm trong `TaiKhoan.trang_thai`. |
| `22_student_deletion_coordinator.sql` | Bổ sung ledger điều phối xóa học viên nhiều site; thuộc luồng portal ngoài phạm vi cho tới khi nhóm duyệt. |
| `23_allow_scoped_student_purge.sql` | Cho phép luồng xóa học viên có phạm vi dọn đúng dữ liệu/log liên quan; chỉ dùng cùng migration 22 và sau khi duyệt nghiệp vụ. |
| `24_account_status_bit.sql` | Chuẩn hóa `TaiKhoan.trang_thai` thành trạng thái bit và các ràng buộc phụ thuộc. |
| `25_simplify_account_lifecycle_tables.sql` | Gỡ các bảng tiến trình vòng đời tài khoản đã thay bằng trạng thái trực tiếp ở hồ sơ/tài khoản. |
| `26_consolidate_logs_and_remove_notification_reads.sql` | Gộp các nhật ký cũ vào `dbo.Logs`, rồi bỏ bảng nguồn và trạng thái đọc thông báo; chạy sau khi dữ liệu nguồn/OTP đã có. `Logs` tồn tại riêng trong mỗi DB site. |
| `27_move_oauth_identity_to_account.sql` | Thêm `google_subject`/`facebook_subject` vào `TaiKhoan`, chuyển dữ liệu từ bảng legacy nếu có, ghi dấu thu hồi vào `Logs` rồi bỏ bảng OAuth cũ. Cần migration 26 trước. |
| `28_add_tuition_installments.sql` | Thêm các đợt/kỳ học phí (`DotHocPhi`) và kiểm tra/backfill khoản phí hiện có. |
| `29_extend_employee_roles.sql` | Chuẩn hóa các chức vụ nhân viên nghiệp vụ theo danh sách được hỗ trợ. |
| `30_enforce_site_fragment_boundaries.sql` | Kiểm tra dữ liệu site rồi thêm 16 `CHECK` constraints để chặn ghi nhầm mảnh; rollback nếu có dòng sai site. |
| `31_add_account_avatar_metadata.sql` | Thêm metadata avatar Cloudinary vào `TaiKhoan`; yêu cầu `Logs` có sẵn. |
| `31_add_sepay_tuition_payments.sql` | Thêm yêu cầu/sự kiện thanh toán SePay tại site chứa `HocPhi`; scope thanh toán online vẫn cần nhóm duyệt. |
| `32_allow_admin_small_hard_delete.sql` | Cho phép xóa vật lý hồ sơ Admin Small trong khi giữ lịch sử; cần backup và chỉ chạy nếu bật luồng này. |
| `33_add_course_duration_fields.sql` | Thêm thời lượng tháng/ngày cho `KhoaHoc`; chạy trước 34 và 35 khi cần nâng schema cũ. |
| `34_allow_fractional_course_months.sql` | Đổi thời lượng sang `DECIMAL(7,2)` để hỗ trợ tháng lẻ; chạy sau 33. |
| `35_allow_optional_course_session_count.sql` | Cho phép `KhoaHoc.so_buoi` để trống đến khi lịch được xếp; chạy sau 33–34. |
| `36_add_blog_tables.sql` | Tạo `DanhMucBlog`/`BaiVietBlog` và nạp ba bài mẫu ban đầu; chạy riêng trên từng database site trước khi dùng API Blog công khai hoặc CMS Admin Big. |
| `37_merge_consultant_and_placement_roles.sql` | Gộp hồ sơ `xep_lop` cũ vào chức vụ `tu_van` và bỏ giá trị `xep_lop` khỏi CHECK; chạy riêng trên từng site trước khi triển khai phiên bản API mới. |
| `38_add_student_avatar_metadata.sql` | Thêm metadata ảnh Cloudinary vào `HocVien`; chạy riêng trên mọi site trước khi triển khai API mới (luồng upload ảnh và chuyển cơ sở đều đọc các cột này). |
| `39_add_contact_inbox.sql` | Thêm `YeuCauLienHe` để nhận form liên hệ tại từng site; cần `CoSo` và `Logs` có sẵn, chạy riêng trên mọi site trước khi bật form/API. Không tạo database trung tâm. |
| `40_enable_tuition_refunds.sql` | Thêm tham chiếu phiếu thu gốc và UUID idempotency vào `PhieuThu`; chạy riêng trên mọi site trước khi triển khai API hoàn học phí. Phiếu hoàn cũ không bị sửa; khoản có phiếu hoàn chưa đối chiếu sẽ bị API chặn hoàn tiếp. |
| `41_merge_receptionist_into_accounting.sql` | Chuyển `NhanVien.chuc_vu='le_tan'` thành `'ke_toan'` và bỏ `le_tan` khỏi CHECK; chạy sau migration 37, trước code chức vụ gộp, trên mọi database site. |
| `42_add_site_staff_notification_audience.sql` | Mở `ThongBao.doi_tuong` cho thông báo nội bộ tại site nhận; chạy trên mọi site đang hoạt động trước khi bật notification mới sau chuyển cơ sở. |

## Chạy bằng SSMS

1. Kết nối tới **SQL Server Database Engine** bằng SSMS. Mở `00_create_databases.sql`, xem lại tên instance rồi chạy. Script chỉ tạo database còn thiếu; script không xóa hoặc ghi đè database hiện có.
2. Mở `01_create_schema.sql`. Trong SSMS bật **Query → SQLCMD Mode**. Dòng `:setvar DatabaseName "QLTTNN_Q1"` là database đích; chọn một trong ba tên `QLTTNN_Q1`, `QLTTNN_Q7`, `QLTTNN_TD`, chạy script, rồi đổi tên và chạy lại cho hai database còn lại.
3. Lặp bước tương tự với `02_seed_shared_catalog.sql`. Script nạp CoSo và MonHoc; KhoaHoc được tạo qua API hoặc bổ sung dữ liệu kiểm thử có kiểm soát trước khi dùng seed demo.
4. Nếu cần dữ liệu để demo, bật SQLCMD Mode trong `03_seed_demo_site.sql`, đặt cả `DatabaseName` và `SiteCode` theo site đang seed, rồi chạy một lần tại mỗi site. Script chỉ tạo dữ liệu kiểm thử và không tạo tài khoản/mật khẩu.
5. Với database đã tồn tại, xác định schema/migration đang có rồi chỉ chạy migration còn thiếu và phù hợp, riêng từng site; không chạy mù toàn bộ lịch sử. Sao lưu trước khi đổi cấu trúc và theo điều kiện trong từng script. Migration `26_consolidate_logs_and_remove_notification_reads.sql` phải đi sau các log nguồn cần giữ và trước các migration cần `dbo.Logs`; `27`, `31_add_account_avatar_metadata.sql` phụ thuộc `Logs`. Chạy `30_enforce_site_fragment_boundaries.sql` sau khi xác nhận dữ liệu không có dòng sai site; script rollback nếu phát hiện vi phạm. Các migration 33–35 phải theo thứ tự khi nâng schema khóa học cũ. Hai file có tiền tố `31_` là hai migration riêng, không dựa vào sắp xếp số để xác định thứ tự. Các migration portal (19, 22, 23) không tự phê duyệt phạm vi nghiệp vụ.
6. Nếu bật chức năng xóa vĩnh viễn Admin Small, sau các migration khác chạy `32_allow_admin_small_hard_delete.sql` riêng trên Q1, Q7, TD. Script chỉ gỡ FK của các cột người thao tác trong bảng lịch sử; giữ FK tài khoản của `YeuCauThanhToan` và không xóa dữ liệu.
7. Lặp bước tương tự với `04_verify_database.sql` để kiểm tra từng database. Kết quả của ba lần chạy phải cho thấy cùng schema và danh mục; bảng nghiệp vụ có thể có dữ liệu khác nhau theo site.
8. Chạy `05_database_roles.sql` trong từng database. DBA tạo SQL login/user theo cấu hình môi trường rồi thêm database user vào `qlttnn_api` hoặc `qlttnn_readonly`. Không đưa mật khẩu vào script hoặc repository.
9. Để bật API Blog, chạy `36_add_blog_tables.sql` riêng trên Q1, Q7, TD và mọi site mới sau khi sao lưu; script tạo bảng cùng seed giống nhau và dừng nếu chỉ có một trong hai bảng đã tồn tại. Nếu cả hai bảng đã có, script không thay đổi dữ liệu.
10. Trước khi triển khai phiên bản gộp chức vụ, tạm dừng API/ghi nhân viên, sao lưu rồi chạy `37_merge_consultant_and_placement_roles.sql` trên **mọi** database site; script đổi `NhanVien.chuc_vu='xep_lop'` thành `'tu_van'` và cập nhật CHECK trong transaction cục bộ. Chỉ bật lại ứng dụng sau khi tất cả site hoàn tất migration.
11. Trước khi triển khai API có upload ảnh học viên/chuyển cơ sở cập nhật, chạy `38_add_student_avatar_metadata.sql` riêng trên Q1, Q7, TD và mọi site mới; script có thể chạy lại an toàn và chỉ thêm cột còn thiếu.
12. Trước khi bật form liên hệ/hộp thư quản trị, sao lưu rồi chạy `39_add_contact_inbox.sql` riêng trên Q1, Q7, TD và mọi site đang hoạt động; script cần `dbo.CoSo`/`dbo.Logs`, tạo bảng tại database đang chọn và không chuyển dữ liệu qua site khác. Cấu hình SMTP trong môi trường API để Admin gửi phản hồi; không đưa thông tin SMTP vào Git.
13. Trước khi triển khai API hoàn học phí, sao lưu rồi chạy `40_enable_tuition_refunds.sql` riêng trên từng database site đang hoạt động. Migration chỉ thêm cột/ràng buộc/index tại DB đang chọn, không thay đổi phiếu đã ghi; xác nhận thành công trên đủ site trước khi bật thao tác hoàn. Đối chiếu thủ công các phiếu `loai='hoan'` cũ chưa có `ma_phieu_goc`; API sẽ từ chối hoàn tiếp cho khoản có các phiếu này đến khi được gắn đúng phiếu gốc.
14. Trước khi triển khai chức vụ `Kế toán & Lễ tân`, dừng ghi nhân viên, sao lưu từng site rồi chạy `41_merge_receptionist_into_accounting.sql` lần lượt trên Q1, Q7, TD (và mọi site đang hoạt động). Script chỉ đổi chức vụ `le_tan` sang `ke_toan` trong đúng database đang chọn, thay CHECK trong transaction cục bộ, rồi in số nhân viên theo chức vụ. Xác nhận cả site hoàn tất trước khi bật API/UI mới; không chạy ở database trung tâm.
15. Trước khi triển khai thông báo chuyển cơ sở cho nhân sự site, sao lưu và chạy `42_add_site_staff_notification_audience.sql` trên mọi site đang hoạt động. Migration chỉ mở rộng CHECK `ThongBao.doi_tuong`; kiểm tra kết quả trên đủ site trước khi bật code phát thông báo.

`01_create_schema.sql` chỉ dành cho database mới/chưa có bảng. Nếu đã có bảng, script sẽ dừng thay vì âm thầm sửa dữ liệu. Không dùng lệnh `DROP DATABASE` để xử lý lỗi; kiểm tra database đích và sao lưu trước khi quyết định cách khôi phục.

## Quy tắc dữ liệu

- Mỗi cơ sở có một database riêng. Khóa ngoại chỉ trỏ tới bảng trong database đó; không có khóa ngoại hoặc JOIN giữa database của các cơ sở.
- Khi demo trên một máy, có thể đặt cả ba database trên một SQL Server instance nhưng vẫn dùng tên database/kết nối riêng. `00_create_databases.sql` dành cho cách cài này. Nếu triển khai mỗi site trên một SQL Server khác nhau, chỉ tạo database của site tương ứng trên máy đó rồi chạy schema/seed/role riêng qua kết nối của site đó; không tạo cả ba database lặp lại trên từng máy.
- `CoSo`, `MonHoc`, `KhoaHoc`, `TaiKhoan` là dữ liệu nhân bản theo schema. Google/Facebook subject nằm trong dòng `TaiKhoan`; chỉ liên kết sau khi người dùng đã xác thực vào tài khoản nội bộ. Script seed không tạo tài khoản hoặc liên kết đăng nhập mẫu.
- `DanhMucBlog`/`BaiVietBlog` có mặt tại từng site; migration 36 khởi tạo cùng ba bài mẫu. API public đọc `GLOBAL`; CMS Admin Big và Tư vấn & xếp lớp ghi bài theo `REPLICATED-WRITE` tại từng site, còn quản lý danh mục/xóa bài chỉ dành cho Admin Big. API lưu ACK trong `Logs`. Migration seed không phải cơ chế replication runtime. Nếu một site bị thiếu hoặc lệch Blog, API phải báo incomplete/conflict thay vì coi như bản sao đúng.
- Script seed danh mục là thao tác nạp ban đầu, chưa phải đồng bộ runtime. Source có service `REPLICATED-WRITE` cho `MonHoc` và `KhoaHoc`; `CoSo` chưa có fan-out runtime đầy đủ. Không lấy seed, code hoặc unit test làm bằng chứng TC-REP-01/TC-SYNC-01; xem [ma trận trạng thái](../docs/Trang-Thai-Trien-Khai.md).
- Các bảng nghiệp vụ và bảng con được lưu tại site tương ứng. Cột `ma_co_so` trên bảng con là khóa phân mảnh để database kiểm tra các quan hệ cùng site bằng khóa ngoại ghép.
- `GiaoDichChuyenCoSo` chỉ có bản ghi trong database của site nguồn; chỉ Tư vấn & xếp lớp tạo đề nghị `cho_duyet` tại đó. Admin Big hoặc Admin Small tại site đích quyết định; Coordinator chỉ thực hiện sau khi đã duyệt. Khi hoàn tất, `ThongBao` được ghi trong transaction cục bộ tại site đích với audience `site_staff`; Admin Small, Kế toán & Lễ tân và Tư vấn & xếp lớp ở site nhận xem được để bắt đầu xếp lớp/phòng. Source có route để Admin Big retry; worker/lịch retry chạy nền chưa được xác nhận. Hồ sơ đích giữ nguyên `ma_tai_khoan`; không tạo lại tài khoản, đổi thông tin đăng nhập hay mật khẩu. Bảng lưu người đề nghị, người quyết định và lý do; unique index giới hạn mỗi học viên còn tối đa một đề nghị/giao dịch mở. `LichSuChuyenCoSo` là nhật ký append-only tại nơi hành động xảy ra (nguồn hoặc đích); `ma_chuyen` chỉ dùng để đối chiếu giữa hai database, không tạo khóa ngoại xuyên site.
- Ràng buộc duy nhất xuyên database (ví dụ tên đăng nhập/email) và quy tắc một tài khoản chỉ gắn với một hồ sơ nhân sự được Coordinator/API kiểm tra; một database site không thể tự bảo đảm các quy tắc đó cho những database còn lại.
- Các sequence `Seq_*` chỉ cấp số thứ tự từ 1 đến 999999. Django/API phải ghép mã site và mã loại, ví dụ `Q1-HV-000001`; số có thể bị khuyết nếu một giao dịch lấy sequence rồi rollback, điều này bình thường.
- `ma_mon` và `ma_khoa_hoc` là mã danh mục dùng chung ổn định, không tạo sequence riêng theo site. `CoSo.ma_co_so` chính là mã cơ sở `Q1`, `Q7`, `TD`.
- Hộp thư Admin Big dùng Global Query: Coordinator hỏi từng database site, gộp danh sách trong ứng dụng, không tạo bảng/DB trung tâm. Quyết định được ghi tại database nguồn; giao dịch chuyển cơ sở chỉ bắt đầu sau khi duyệt. Bộ script này không tạo Linked Server, Publication, VPN hay một kho dữ liệu tập trung.
- Giao dịch chuyển cơ sở gồm nhiều transaction cục bộ được điều phối qua hai database; schema hỗ trợ phục hồi tiến về phía trước và không tự tạo cam kết ACID nguyên tử xuyên database. Khi đích đã commit, không xóa hồ sơ đích để giả vờ hoàn tác; Coordinator phải hoàn tất bước nguồn khi kết nối hồi phục.

Khi thay đổi cấu trúc, cập nhật `docs/DATABASE_SCHEMA.md` và README trong cùng thay đổi. Chi tiết chính sách dữ liệu nằm ở [schema](../docs/DATABASE_SCHEMA.md), luồng nghiệp vụ ở [README](../README.md).
