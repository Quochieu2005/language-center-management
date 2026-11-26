# TC-SYNC-01 — Đồng bộ sau khi site mất kết nối (26/11/2026)

**Kết quả:** đạt cho hàng đợi tài khoản và hàng đợi Blog, **sau khi sửa một lỗi** của hàng đợi Blog được phát hiện ngay trong lần chạy này. Chạy trên hai database tạm, chưa chạy trên Q1/Q7/TD.

## Môi trường

Như [TC-FRAG-01](../../TC-FRAG-01/2026-11-26/README.md): `QLTTNN_EVA` (authority, có migration 45 và 49) và `QLTTNN_EVB`. EVB mất kết nối được mô phỏng bằng cách trỏ cổng kết nối sang cổng đóng (như máy tắt hoặc VPN rớt), sau đó trả về cổng thật. Gọi trực tiếp `sync_accounts()`, `write_blog()` và `reconcile_pending_blog_writes()` của source.

## Cách chạy

[scripts/ev_sync.py](../../scripts/ev_sync.py), kết quả [results.json](results.json).

## Phần 1 — Tài khoản (trigger → `DongBoTaiKhoan` → `sync_accounts`)

| Bước | Kết quả |
|---|---|
| Thêm tài khoản Admin Big vào authority EVA | Trigger tạo hàng đợi cho EVA và EVB; EVB chưa có tài khoản |
| Worker chạy khi EVB mất kết nối | Giao được 1 (EVA), hoãn 1 (EVB). Hàng của EVB được giữ, `so_lan_thu=1`, `loi=OperationalError` |
| EVB trở lại, worker chạy lại | Giao 1, hoãn 0. Bản sao tại EVB bằng đúng bản ở authority ở mọi cột đồng bộ; hàng đợi rỗng |
| Chạy worker lần nữa | Không làm gì (`delivered=0`, `deferred=0`) |

## Phần 2 — Blog (`write_blog` → hàng đợi trong `Logs` → `sync_blog`)

| Bước | Kết quả |
|---|---|
| Tạo danh mục và bài khi cả hai site hoạt động | `complete=true` |
| Sửa bài lần 1 khi EVB mất kết nối | Ghi được ở EVA; `complete=false`, `missing_sites=["EVB"]`; hàng đợi chờ 1 |
| Sửa bài lần 2 (cùng bài) khi EVB vẫn mất | Tương tự; hàng đợi chờ 2. EVA có tiêu đề mới nhất, EVB còn tiêu đề gốc |
| Worker chạy khi EVB vẫn mất | Không hoàn tất, không đẩy sang đối soát (chờ 2, cần xem xét 0) |
| EVB trở lại, worker chạy | Hoàn tất 2 việc theo thứ tự cũ → mới; hàng đợi và đối soát đều 0. Hai site giống nhau và mang tiêu đề của lần sửa cuối |
| Gửi lại khóa của lần sửa cuối | `idempotent_replay=true`, không ghi lại dòng nào (`cap_nhat_luc_utc` không đổi ở cả hai site) |
| Gửi lại khóa của lần sửa cũ sau khi có lần sửa mới hơn | Không áp dụng lại thay đổi cũ; tiêu đề hai site vẫn là bản mới nhất |

## Lỗi phát hiện và đã sửa

Trước khi sửa, hai lần sửa liên tiếp cùng một bài khi một site mất kết nối **không hội tụ**: worker đánh dấu cả hai việc `BLREV-` (cần đối soát thủ công), EVB giữ mãi tiêu đề gốc. Kết quả lần chạy đó được giữ ở [before-fix-blog-two-edits.json](before-fix-blog-two-edits.json) (`review_count=2`, `completed=0`, hai site khác nhau).

Nguyên nhân: khi phát lại, `write_blog` yêu cầu **mọi** site phải đang ở đúng trạng thái "sau" của thao tác nếu đã ACK, hoặc trạng thái "trước" nếu chưa. Site đã ACK lần sửa 1 lại đã đi tiếp sang lần sửa 2, nên bị coi là lệch ACK. Một lần sửa duy nhất thì không bị lỗi này.

Sửa: [write_services.py](../../../../src/api/core/blog/write_services.py) thêm `sites_off_ack`, chỉ so sánh những site **còn nợ** thao tác với trạng thái "trước"; site đã ACK không bị so sánh lại. Có test mới [test_write_replay.py](../../../../src/api/core/blog/test_write_replay.py) (4 ca). Lần chạy trong `results.json` là sau khi sửa.

Hệ quả cần biết: gửi lại một khóa cũ khi tất cả site đã ACK giờ trả kết quả lặp lại (không ghi lại) thay vì 409. Việc ghi lại thay đổi cũ vẫn bị chặn.

## Giới hạn

- Hai database tạm trên một instance; mất mạng được mô phỏng bằng cổng đóng. Chưa thử tắt máy hay ngắt VPN thật, chưa thử trên Q1/Q7/TD.
- Database offline trên instance còn sống (không phải mất mạng) chưa được kiểm tra ở đây và có thể gặp lỗi `InterfaceError` như ghi ở [TC-DQ-01](../../TC-DQ-01/2026-11-26/README.md).
- Chưa kiểm tra xung đột thật giữa hai người sửa cùng bài, chưa kiểm tra xóa hoặc đổi slug trong hàng đợi, chưa kiểm tra `KhoaHoc` (`sync_courses`) và MonHoc (Publication).
- Worker được gọi bằng tay trong kịch bản; vòng lặp nền 5 giây và 10 giây/60 giây của `manage.py sync_blog` và `sync_accounts` chưa được chạy dài.
