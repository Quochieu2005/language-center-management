# TC-DQ-01 — Truy vấn phân tán khi chỉ Q7 mất kết nối (27/11/2026)

**Kết quả:** đạt. Lần này **Q1 và TD cùng truy cập được, chỉ Q7 mất kết nối thật** (khác [bản trước](../2026-11-27-site-that/README.md) khi cả Q7 và TD đều mất). Chỉ đọc, không đổi dữ liệu. Kịch bản [real_dq.py](../../scripts/real_dq.py); kết quả đầy đủ [results.json](results.json).

| Bước | Kết quả |
|---|---|
| Kết nối TCP | Q1 và TD truy cập được; Q7 hết thời gian chờ |
| Đếm trực tiếp bằng SQL | Q1: 2 học viên đang học; TD: 146 (gồm dữ liệu LAB của TC-CON-01 đang có lúc chạy, đã dọn sau đó) |
| Global Query lần đầu (5,27 giây) | `complete=false`, `missing_sites=["Q7"]`, tổng 148 khớp đúng tổng SQL trực tiếp của hai site còn lại; Q7 **không** bị báo là 0 |
| Truy vấn cục bộ `Q1` và `TD` | Cả hai `complete=true`, đúng số đếm từng site: hai site còn sống làm việc bình thường |
| HTTP `GET /api/v1/courses/` | 200, `complete=false`, `missing_sites=["Q7"]`, 3 khóa học |
| HTTP `GET /api/v1/blog/articles/` | 200, `complete=false`, `missing_sites=["Q7"]`, 3 bài, `inconsistent_sites=[]` (sau khi đối soát Blog TD với Q1) |

## Giới hạn

- Chỉ trạng thái **đang mất** một site; chưa có trước và sau khi Q7 phục hồi trên site thật.
- Số 146 ở TD gồm 40 học viên LAB đã được dọn; con số này không tái hiện lại, kết quả giữ nguyên trong `results.json`.
- Chưa kiểm tra endpoint admin (cần đăng nhập). TD từng chập chờn ngay sau lần chạy này (xem [TC-DTX-01](../../TC-DTX-01/2026-11-27/README.md)).
