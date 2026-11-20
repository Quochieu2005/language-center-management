# TC-REP-01 — MonHoc Publisher Q1 tới Q7 và TD

- Hoàn tất phép thử: `2026-11-20T10:31:06+07:00` (múi giờ Việt Nam).
- Người thực hiện: tác nhân Codex theo yêu cầu Quốc Hiếu; chờ Quốc Hiếu review.
- Source khi chạy: `cdc052a7`, nhánh `qhiu`.
- Loại nghiệp vụ: `REPLICATED-WRITE`, bất đồng bộ; không phải distributed ACID.
- Q1/TD: Windows `DESKTOP-CK4K90F`, hai database riêng `QLTTNN_Q1`/`QLTTNN_TD`.
- Q7: SQL Server 2022 container `sql-q7` trên Intel Mac Minh Khôi,
  database `QLTTNN_Q7`, kết nối ZeroTier. TD chưa chuyển máy.
- Publication: `PUB_QLTTNN_MonHoc`, chỉ article `dbo.MonHoc`; push Subscribers
  `SQL-Q7` và instance Windows/database TD. Không đổi schema hay `.env`.

## Điều kiện đầu và thao tác

Trước sửa: Q1/Q7 có `MH-ENG`, `MH-JPN`, `MH-TEST-Q7`; TD chỉ có hai môn đầu.
Đối chiếu toàn bộ sáu cột môn học, giữ bản trước ngoài repository; hai dòng TD
cũ khớp hoàn toàn. Khởi tạo đúng một dòng TD thiếu rồi thêm Subscription với
`replication support only`. Không drop/truncate hoặc ghi đè dữ liệu cũ.

Gọi `SharedSubjectCollectionView`/`SharedSubjectDetailView` bằng DRF
`APIRequestFactory`, gán danh tính Admin Big trong test bằng `force_authenticate`;
service và Site Router dùng kết nối SQL Server thật, mỗi lần commit thực sự.
Không thử cookie/CSRF, HTTP transport hoặc trình duyệt trong bộ chạy này.

1. POST mã `MH-RT-8A293A34`, tên `Kiem chung SQL MH-RT-8A293A34`, mô tả
   `Runtime create test`. Retry nguyên key/body cho tới complete.
2. Lặp POST cùng key nhưng mô tả `Different body`: phải bị 409.
3. PATCH tên thêm ` updated`, mô tả `Runtime update test`; retry nguyên
   key/body qua route slug ban đầu. Đổi slug và tăng phiên bản đúng một lần.
4. Lặp PATCH đã hoàn tất: phải giữ phiên bản 2, `idempotent_replay=true`.
5. DELETE qua slug mới, key mới; retry nguyên key tới complete.
6. Đọc từng kết nối: `SELECT COUNT_BIG(*) FROM dbo.MonHoc WHERE ma_mon = ...`
   phải bằng 0. Gọi `list_shared_subjects()` phải đủ site và không lệch.

## Kết quả

[Response đã lọc thông tin bí mật](api-results.json): POST 202 → 201, PATCH
202 → 200, DELETE 202 → 200. Cả ba trả complete với Q1/Q7/TD sau khi Agent
truyền thay đổi. Retry PATCH vẫn phiên bản 2; key khác body bị 409.

Môn tạm đã xóa bằng API trên cả ba site; biên nhận `Logs` tại Publisher giữ lại
đúng chính sách append-only. Môn thử `MH-TEST-Q7` do người dùng tạo vẫn giữ.
Danh mục cuối có ba môn, `complete=true`, không thiếu site và không lệch dữ liệu.

Đạt phạm vi thêm/sửa/xóa/retry qua API views và SQL replication trên topology
này. Không thay thế TC-CON-01, TC-DTX-01, browser end-to-end hoặc outage TD.
Ảnh UPDATE/phục hồi Q7 do Quốc Hiếu cung cấp nằm trong hội thoại, chưa được
đóng gói vào thư mục bằng chứng này.
