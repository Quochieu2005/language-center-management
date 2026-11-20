# Kiểm tra và sửa cấu trúc DB ngày 20/11/2026

Đợt rà tài liệu giảng viên và script kiểm chứng; xem thời điểm chính xác trong [kết quả](readonly-schema-checks.json). Chạy từ môi trường Django hiện có với từng alias trong `SITE_DATABASE_ALIASES`, không sửa `.env`, không chạy migration, không thêm/sửa/xóa dữ liệu hoặc cấu hình replication.

## Phương pháp

- Mở kết nối riêng theo Site Router; chạy từng batch SQL của `db/04_verify_database.sql` và `db/verification/01_site_fragment_readonly.sql`. Khi chạy qua driver, bỏ dòng SQLCMD `:setvar`/`USE [$(DatabaseName)]` vì kết nối đã chọn database; không sửa các câu kiểm tra còn lại.
- Đọc hết các result set, ghi số dòng/metadata, không xuất tài khoản, mật khẩu, provider subject hoặc dữ liệu cá nhân. Lưu bản kết quả cuối, không lưu lần trình chạy tạm bị lỗi cấu hình timeout.
- Thử lại mỗi script trong `master` để xác nhận guard từ chối trước thao tác bảng nghiệp vụ; sau đó khôi phục database đã chọn trên cùng kết nối.
- Probe metadata cho lỗi 51026 và FK/trigger tại Q1/TD; [schema-flags.json](schema-flags.json) chỉ chứa tên cấu trúc và cờ trạng thái.

## Kết quả

| Site | Danh tính DB/instance | Script 04 | Script mảnh cục bộ | Guard master |
|---|---|---|---|---|
| Q1 | QLTTNN_Q1 / DESKTOP-CK4K90F | Dừng 51026: thiếu cấu trúc subject OAuth | Pass; có 16 CHECK site; lớp và đăng ký đều 0 dòng | Pass cho cả hai |
| TD | QLTTNN_TD / DESKTOP-CK4K90F | Dừng 51026: thiếu cấu trúc subject OAuth | Pass; có 16 CHECK site; lớp và đăng ký đều 0 dòng | Pass cho cả hai |
| Q7 | Chưa mở được kết nối cấu hình | Chưa chạy, SQLSTATE 08001 | Chưa chạy | Chưa chạy |

Probe xác nhận cả Q1/TD không có `google_subject`, `facebook_subject`, hai unique index/subject CHECK tương ứng migration 27; bảng liên kết OAuth legacy cũng không có. Hai trigger `TR_Logs_AppendOnly` và `TR_LichSuChuyenCoSo_AppendOnly` đang bật tại Q1/TD. TD còn có `FK_KhoaHoc_MonHoc` bật nhưng `is_not_trusted = 1`; không đồng nghĩa đã tìm được dữ liệu mồ côi. Lỗi kết nối Q7 không đủ xác định Docker, VPN hay cổng là nguyên nhân.

[Đối chiếu hồi quy](guard-regression-checks.json): chạy bản script 04 ở HEAD trước sửa trên cùng Q1/TD cũng dừng 51026, nên lỗi cấu trúc này đã có trước thay đổi verifier. Chạy riêng đúng khối kiểm tra integrity mới: Q1 qua; TD nhận 51405 đúng với FK chưa trusted. Đây là kiểm tra chỉ đọc khối guard, không có nghĩa script 04 toàn bộ đã pass hoặc đã thử tắt constraint/trigger trên dữ liệu thật.

Các lỗi này không được che bằng bỏ điều kiện verify. Script mảnh pass với dữ liệu rỗng **không chứng minh đầy đủ/tái thiết/phân mảnh nhiều site**, và không thay kết quả TC-CON/DTX/DQ.

## Hướng xử lý trước buổi demo

1. Khôi phục kết nối Q7 rồi chạy lại. Không thay bằng DB Q7 cũ trên Windows để làm đẹp kết quả; ghi đúng vị trí Q7.
2. Sao lưu và đối chiếu migration 27 trên các site thiếu cấu trúc trước khi bật luồng OAuth hiện hành. Đợt rà này không tự áp dụng migration.
3. Với TD, kiểm tra tham chiếu khóa học ngay tại `QLTTNN_TD`:

```sql
SELECT COUNT_BIG(*) AS orphan_courses
FROM dbo.KhoaHoc AS k
LEFT JOIN dbo.MonHoc AS m ON m.ma_mon = k.ma_mon
WHERE m.ma_mon IS NULL;
```

Nếu còn mồ côi thì đối soát bản sao trước, không xóa khóa học để ép pass. Sau khi dữ liệu hợp lệ và được lên lịch bảo trì, có thể revalidate FK bằng `ALTER TABLE dbo.KhoaHoc WITH CHECK CHECK CONSTRAINT FK_KhoaHoc_MonHoc` tại đúng TD; lệnh này **chưa chạy trong đợt rà**.

4. Chạy lại script 04 và bộ fragment với fixture lớp/đăng ký ở các site, đối chiếu tập kỳ vọng và lưu kết quả mới. Bản kết quả này được giữ làm bằng chứng lỗi/giới hạn, không sửa thành pass khi chưa có lần chạy mới.

## Kiểm tra source/tài liệu cùng đợt

- Django `manage.py check`: pass.
- `manage.py test core.catalog --noinput`: 26/26 pass; không phải bằng chứng replication nhiều máy.
- Kiểm tra UTF-8, liên kết file Markdown và cân bằng code fence trong docs/FS/spec/DB/README: pass tại thời điểm rà.
- Không chạy browser end-to-end, không chạy concurrency/fault injection, không cấu hình ba server lại, không tạo PR.


## Cập nhật sau khi sửa DB

Các kết quả chỉ đọc ở trên là trạng thái **trước sửa**. [Kết quả sau sửa](db-fix-results.json) ghi nhận Q1/TD đã có backup COPY_ONLY/CHECKSUM, RESTORE VERIFYONLY thành công, áp dụng migration 27/40/43/44 và qua script 04 cùng kiểm tra mảnh cục bộ. Chỉ bổ sung cấu trúc/ràng buộc; không thay số tiền, hồ sơ hoặc nội dung liên hệ. TD đã bỏ cờ NOT FOR REPLICATION trên đúng FK môn–khóa học theo schema để xác nhận FK trusted; không đổi Publication/Subscription.

DB tạm đã thử nâng cấp từ thiếu cột OAuth/phiếu hoàn, FK NOT FOR REPLICATION, chạy lại migration, kiểm tra bình thường và các ca thiếu bảng Blog, thiếu cột ảnh, tắt CHECK, FK chưa trusted, ghi liên hệ sai cơ sở. DB tạm đã được xóa sau kiểm thử. Script hồi quy liên hệ được lưu tại `db/verification/02_contact_boundary_regression.sql`; fixture chỉ chứa dữ liệu giả.

Q7 vẫn không mở được kết nối; migration mới chưa được áp dụng/kiểm chứng tại Q7. Không ghi toàn hệ thống đã hoàn tất. Chưa thử browser, concurrency, lỗi chuyển cơ sở hoặc truyền replication sau lần sửa này; Q1/TD vẫn chưa có lớp để chứng minh đầy đủ phân mảnh với dữ liệu thật.
