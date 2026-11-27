# TC-CON-01 — Tranh chỗ cuối trên Q1 thật (27/11/2026)

**Kết quả:** đạt trên **Q1 thật** (`QLTTNN_Q1`, máy `DESKTOP-CK4K90F`), gọi trực tiếp `register_student_to_class` của source. Chỉ ghi dữ liệu mang nhãn `LAB`, đã dọn sau khi chạy. Chưa chạy trên Q7 và TD.

## Môi trường và cách chạy

- Site Q1 theo cấu hình `src/api/.env`; dữ liệu LAB nạp bằng `manage.py seed_lab_data --sites Q1 --apply` ([hướng dẫn](../../../../db/README.md#dữ-liệu-mẫu-cho-các-lần-chạy-bằng-chứng-seed_lab_data)). Trước khi nạp Q1 có 2 học viên, 1 giáo viên, chưa có phòng, lớp hay đăng ký.
- Kịch bản [real_con.py](../../scripts/real_con.py); kết quả đầy đủ [results.json](results.json). Cơ chế bảo vệ trong source: khóa ứng dụng theo học viên và theo lớp, đọc lớp bằng `UPDLOCK, HOLDLOCK`, rồi `UPDATE … WHERE si_so_hien_tai < si_so_toi_da`.
- Mỗi phiên là một luồng với kết nối SQL Server riêng.

## Kết quả

| Ca | Kết quả |
|---|---|
| A. Chứng minh chồng lấn: lớp `Q1-LH-LAB03` còn 1 chỗ. Phiên 1 giữ khóa 2 giây sau khi lấy chỗ (bộ kiểm thử chèn `sleep`), phiên 2 bắt đầu sau 0,5 giây | Phiên 1 thành công (2,05 giây). Phiên 2 **phải chờ** (1,55 giây) rồi bị từ chối `ClassConflict: Lớp đã đủ sĩ số tối đa.` Cuối: sĩ số 1, 1 đăng ký, 1 dòng học phí |
| B. 10 vòng, mỗi vòng một lớp 1 chỗ mới và một cặp học viên mới, hai phiên xuất phát cùng lúc | Cả 10 vòng có đúng một thành công và một từ chối; không vượt sức chứa; sĩ số, đăng ký và học phí khớp nhau |
| C. Lớp 5 chỗ, 12 phiên cùng lúc | 5 thành công, 7 từ chối; cuối: sĩ số 5, 5 đăng ký, 5 dòng học phí |

## Lần chạy đầu bị lỗi thiết kế kịch bản (không phải lỗi hệ thống)

[lan-chay-dau-loi-thiet-ke.json](lan-chay-dau-loi-thiet-ke.json) là lần chạy đầu: vòng 1 và 2 đúng, từ vòng 3 đến 10 **cả hai phiên đều bị từ chối** và không ai có chỗ. Nguyên nhân là hệ thống có quy tắc nghiệp vụ thật: *mỗi học viên chỉ có một đăng ký hiệu lực cho mỗi khóa học* (`Học viên đã có đăng ký hiệu lực cho khóa học này`). Kịch bản đầu dùng lại cùng hai học viên cho mọi vòng, nên từ vòng 3 họ bị quy tắc này chặn, không liên quan tới sức chứa. Ngay cả khi đó không có lớp nào vượt sức chứa và số liệu vẫn khớp. Quy tắc này không xuất hiện trên database tạm vì kịch bản trước đó dùng học viên khác nhau cho mỗi vòng. Kịch bản đã sửa để mỗi vòng dùng cặp học viên riêng; kết quả bảng trên là của lần chạy sau khi sửa.

## Giới hạn

- Chỉ Q1, một site. Các phiên là luồng trong một tiến trình, không phải nhiều máy hay nhiều tiến trình API.
- Ca A chèn `sleep` ở phía bộ kiểm thử (không đổi source) để buộc hai phiên chồng lấn; ca B và C dùng `Barrier` nhưng không tự chứng minh chồng lấn thật trong từng vòng.
- Chưa kiểm tra qua HTTP hay trình duyệt.
- **Đã dọn dữ liệu LAB khỏi Q1** (`seed_lab_data --remove --apply`): Q1 về lại đúng số lượng ban đầu. Các dòng nhật ký audit của lần đăng ký (`Logs`, bảng chỉ thêm) vẫn còn.
