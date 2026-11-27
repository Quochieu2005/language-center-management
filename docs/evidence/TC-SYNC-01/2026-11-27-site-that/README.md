# TC-SYNC-01 — Sửa Blog trên Q1 thật khi Q7 và TD mất kết nối (27/11/2026)

**Kết quả:** phần **mất kết nối** đạt trên Q1 thật. **Phần phục hồi chưa chạy**, vì Q7 và TD vẫn offline.

## Cách chạy

[real_sync.py](../../scripts/real_sync.py) gọi `write_blog` của source (không đổi source). Kết quả đầy đủ: [results.json](results.json). Không ghi host hay thông tin đăng nhập.

## Kết quả

| Bước | Kết quả |
|---|---|
| 1. Tạo danh mục `lab-ev` | Ghi vào Q1; `complete=false`, `missing_sites=["Q7","TD"]`; hàng đợi 1 mục |
| 2. Tạo bài nháp `lab-bai-ev` | Ghi vào Q1; hàng đợi 2 mục |
| 3 và 4. Sửa tiêu đề hai lần liên tiếp | Mỗi lần ghi vào Q1 và báo thiếu Q7, TD; hàng đợi 3 rồi 4 mục |
| 5. Đọc lại ở Q1 | Tiêu đề là bản sửa lần 2: Q1 vẫn làm việc bình thường khi hai site kia mất |
| 6 và 7. Chạy worker khi hai site vẫn mất | Không hoàn tất mục nào (`completed=0`); cả 4 mục **được giữ lại** trong hàng đợi, không mất, không vào diện cần đối soát (`review_count=0`) |

Ý nghĩa cho báo cáo: khi site khác mất kết nối, thao tác ghi không bị chặn và không bị mất; yêu cầu được xếp hàng ở site điều phối và thử lại, đúng mô hình đồng bộ lười (GV-03).

## Trạng thái dữ liệu để lại

Bài và danh mục mang nhãn LAB, bài ở trạng thái **nháp** nên không hiển thị công khai. **Không dọn** có chủ ý: 4 mục trong hàng đợi chính là đầu vào của phần phục hồi.

Khi Q7 và TD lên, chạy `sync_blog` (hoặc `reconcile_pending_blog_writes`), kỳ vọng hàng đợi về 0 và hai site có bài `lab-bai-ev` với tiêu đề "lần 2"; sau đó xóa bài và danh mục bằng `write_blog` (hành động `xoa`) để dọn ở cả ba site.

## Giới hạn

- Chưa có bằng chứng phục hồi trên site thật (phần đó có trên database tạm: [bản 26/11](../2026-11-26/README.md)).
- Chưa kiểm tra `TaiKhoan` và `KhoaHoc`.
- Blog ở TD và Q7 có thể đã lệch Q1 từ trước (xem UI-CHECK). Bài LAB mới không phụ thuộc điều đó, nhưng bước sửa sau khi phục hồi có thể bị từ chối nếu hai site đó có cùng slug khác nội dung.
