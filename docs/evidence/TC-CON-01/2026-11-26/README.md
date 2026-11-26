# TC-CON-01 — Tranh chỗ cuối (26/11/2026)

**Kết quả:** đạt trên hai database tạm, gọi trực tiếp `register_student_to_class` của source. Chưa chạy trên Q1/Q7/TD.

## Môi trường

Như [TC-FRAG-01](../../TC-FRAG-01/2026-11-26/README.md): `QLTTNN_EVA`/`QLTTNN_EVB` tạm trên instance `DESKTOP-CK4K90F`, đã xóa sau khi chạy. Các phiên chạy trên site EVA, mỗi phiên là một luồng Python với kết nối SQL Server riêng.

## Cách chạy

[scripts/ev_con.py](../../scripts/ev_con.py), kết quả đầy đủ [results.json](results.json). Cơ chế bảo vệ trong source: khóa ứng dụng theo học viên và theo lớp (`sp_getapplock`), đọc lớp bằng `UPDLOCK, HOLDLOCK`, rồi `UPDATE … WHERE si_so_hien_tai < si_so_toi_da`.

## Kết quả

| Ca | Kết quả |
|---|---|
| A. Chứng minh chồng lấn: lớp 1 chỗ, hai học viên. Phiên 1 giữ khóa 2 giây sau khi tăng sĩ số (bộ kiểm thử chèn `sleep`), phiên 2 bắt đầu sau 0,5 giây | Phiên 1 thành công (2,22 giây). Phiên 2 **phải chờ** (1,74 giây) rồi bị từ chối `ClassConflict: Lớp đã đủ sĩ số tối đa.` Cuối: sĩ số 1, 1 đăng ký, 1 dòng học phí |
| B. 20 vòng, mỗi vòng một lớp 1 chỗ mới, hai phiên xuất phát cùng lúc bằng `Barrier` | Cả 20 vòng có đúng một thành công và một từ chối; không vượt sức chứa; sĩ số khớp số đăng ký |
| C. Lớp 5 chỗ, 12 phiên cùng lúc | 5 thành công, 7 từ chối; cuối: sĩ số 5, 5 đăng ký, 5 dòng học phí |

## Giới hạn

- Ca A chèn `sleep` trong luồng thử (chỉ ở phía bộ kiểm thử, không đổi source) để buộc hai phiên chồng lấn và đo thời gian chờ. Ca B và C dùng `Barrier` nhưng không tự chứng minh có chồng lấn thật trong từng vòng; ca A mới là chứng minh.
- Các phiên là luồng trong một tiến trình, không phải nhiều máy hay nhiều tiến trình API.
- Chưa kiểm tra qua HTTP/trình duyệt, chưa kiểm tra trên site thật, chưa thử khi có lịch trùng hoặc đăng ký chuyển cơ sở cùng lúc.
- Tranh chấp chỉ xảy ra trong một site (đúng thiết kế: đăng ký lớp là thao tác cục bộ).
