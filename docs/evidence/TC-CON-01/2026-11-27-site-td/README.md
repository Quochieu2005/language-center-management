# TC-CON-01 — Tranh chỗ cuối trên TD thật (27/11/2026)

**Kết quả:** đạt trên **TD thật** (`QLTTNN_TD_MOI`, máy `DESKTOP-N47BBPH`, SQL Server 16.0.1000.6), gọi trực tiếp `register_student_to_class` của source từ máy API. Chỉ ghi dữ liệu mang nhãn `LAB`, **đã dọn** sau khi chạy (TD về lại số lượng thật; các dòng nhật ký audit của lần đăng ký vẫn còn vì `Logs` chỉ thêm). Chưa chạy trên Q7.

Cách chạy và cơ chế bảo vệ giống [bản Q1](../2026-11-27-site-that/README.md): `python docs/evidence/scripts/real_con.py TD 2026-11-27-site-td` sau `manage.py seed_lab_data --sites TD --apply`. Kết quả đầy đủ: [results.json](results.json).

| Ca | Kết quả |
|---|---|
| A. Chồng lấn: lớp `TD-LH-LAB03` còn 1 chỗ, phiên 1 giữ khóa 2 giây (bộ kiểm thử chèn `sleep`), phiên 2 bắt đầu sau 0,5 giây | Phiên 1 thành công (2,39 giây); phiên 2 **phải chờ** (1,96 giây) rồi bị từ chối `ClassConflict: Lớp đã đủ sĩ số tối đa.` Cuối: sĩ số 1, 1 đăng ký, 1 dòng học phí |
| B. 10 vòng, mỗi vòng một lớp 1 chỗ mới và một cặp học viên mới | Cả 10 vòng có đúng một thành công và một từ chối; không vượt sức chứa; sĩ số, đăng ký và học phí khớp nhau |
| C. Lớp 5 chỗ, 12 phiên cùng lúc | 5 thành công, 7 từ chối; cuối: sĩ số 5, 5 đăng ký, 5 dòng học phí |

## Giới hạn

- Một site; các phiên là luồng trong một tiến trình, kết nối qua mạng tới TD (khác bản Q1 chạy trên máy cục bộ).
- Ca A chèn `sleep` ở phía bộ kiểm thử để buộc chồng lấn; ca B và C dùng `Barrier` nhưng không tự chứng minh chồng lấn thật trong từng vòng.
- Chưa kiểm tra qua HTTP hay trình duyệt.
