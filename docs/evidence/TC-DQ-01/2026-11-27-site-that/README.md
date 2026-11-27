# TC-DQ-01 — Truy vấn phân tán khi mất site thật (27/11/2026)

**Kết quả:** đạt trên **topology thật**, trong lúc Q7 và TD mất kết nối thật (máy đang bận, không do kịch bản gây ra). Chỉ đọc, không đổi dữ liệu. Đây là lần mất site thật, khác với bản mô phỏng trên database tạm.

## Cách chạy

[real_dq.py](../../scripts/real_dq.py) kiểm tra kết nối TCP từng site, đếm trực tiếp bằng SQL ở site truy cập được, gọi `student_counts_by_site()` của source, rồi gọi hai endpoint công khai qua HTTP của API đang chạy ở `localhost:8001`. Kết quả đầy đủ: [results.json](results.json). Không ghi host hay thông tin đăng nhập.

## Kết quả

| Bước | Kết quả |
|---|---|
| Kết nối TCP | Q1 truy cập được; Q7 và TD hết thời gian chờ |
| Đếm trực tiếp bằng SQL | Q1: 42 học viên đang học (2 học viên thật và 40 học viên LAB đang có lúc chạy) |
| Global Query, lần gọi đầu (mất 5,16 giây, hết thời gian kết nối) | `complete=false`, `missing_sites=["Q7","TD"]`, chỉ có kết quả của Q1, tổng 42 khớp đúng số đếm SQL; hai site thiếu **không** bị báo là 0 |
| Global Query, gọi lại ngay (0,02 giây) | Vẫn `complete=false` và đúng hai site thiếu; site vừa mất kết nối được bỏ qua tức thì thay vì chờ lại hết thời gian |
| Truy vấn cục bộ `Q1` | `complete=true`, 42: Q1 vẫn làm việc bình thường khi hai site kia mất |
| HTTP `GET /api/v1/courses/` | 200, `complete=false`, `missing_sites=["Q7","TD"]`, trả 3 khóa học từ Q1 |
| HTTP `GET /api/v1/blog/articles/` | 200, `complete=false`, `missing_sites=["Q7","TD"]`, trả 3 bài từ Q1 |

Ý nghĩa cho báo cáo: khi hai trong ba site mất, hệ thống không lỗi 500 và không che thiếu dữ liệu; phần còn sống vẫn phục vụ và phản hồi nói rõ site nào thiếu.

## Giới hạn

- Chỉ có trạng thái **đang mất** site; chưa có trước và sau khi phục hồi trên site thật (phần đó đã có trên database tạm, xem [bản 26/11](../2026-11-26/README.md)).
- Số 42 gồm 40 học viên LAB đã được dọn khỏi Q1 sau khi chạy, nên con số này không tái hiện lại; kết quả giữ nguyên trong `results.json`.
- `inconsistent_sites` ở các endpoint công khai là rỗng vì khi site thiếu thì không có gì để so sánh; không dùng kết quả này để kết luận Blog đã nhất quán (xem phát hiện về Blog ở TD trong [UI-CHECK](../../UI-CHECK/2026-11-26/README.md)).
- Chưa kiểm tra endpoint admin (cần đăng nhập). Chưa biết nguyên nhân Q7 và TD mất kết nối ngoài việc máy đang bận.
