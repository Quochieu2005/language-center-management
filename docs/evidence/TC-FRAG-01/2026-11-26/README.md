# TC-FRAG-01 — Phân mảnh và tái thiết (26/11/2026)

**Kết quả:** đạt trên hai database tạm. Đây là bằng chứng cho logic phân mảnh và ràng buộc site, **không** phải bằng chứng trên Q1/Q7/TD thật.

## Môi trường

- Hai database tạm `QLTTNN_EVA` và `QLTTNN_EVB`, cùng instance Windows `DESKTOP-CK4K90F` với Q1. Không phải ba server vật lý, không đụng `QLTTNN_Q1/Q7/TD`. Đã xóa sau khi chạy.
- Schema: `01_create_schema.sql` rồi các migration 07–44, 47, 48 (và 45, 49 tại authority EVA). Danh sách và thứ tự: [scripts/ev_build.py](../../scripts/ev_build.py).
- Dữ liệu mẫu: EVA có 3 lớp, 5 học viên, 5 đăng ký; EVB có 2 lớp, 4 học viên, 4 đăng ký. `MonHoc`/`KhoaHoc` giống nhau ở cả hai site (bảng nhân bản).

## Cách chạy

[scripts/ev_frag.py](../../scripts/ev_frag.py) mở kết nối riêng tới từng database, đọc lớp, đăng ký và học viên, rồi hợp các tập trong công cụ kiểm thử. Không có database tổng hợp và không có JOIN xuyên database. Kết quả đầy đủ: [results.json](results.json).

## Kết quả

| Tiêu chí | Kết quả |
|---|---|
| Đầy đủ và tái thiết | Hợp các lớp của hai mảnh bằng đúng tập kỳ vọng: 3 + 2 = 5 lớp, không thiếu, không thừa |
| Không giao nhau | Hai mảnh lớp không có mã chung |
| Đúng site | Mỗi database: 0 lớp, 0 học viên, 0 đăng ký mang `ma_co_so` của site khác |
| Dẫn xuất | Mọi đăng ký có lớp cha và học viên cùng site, cùng `ma_co_so` (0 vi phạm) |
| Sĩ số | `si_so_hien_tai` khớp số đăng ký ở mọi lớp (0 lệch) |
| Ràng buộc | 17 `CHECK` dạng `CK_*_site_local` mỗi database, đều bật và đã trust (16 do migration 30, 1 do migration 43 cho `YeuCauLienHe`) |

Bốn ca ghi sai site, mỗi ca chạy trong transaction rồi rollback, đều bị SQL Server từ chối (lỗi 547):

| Ca | Ràng buộc chặn |
|---|---|
| Lớp `ma_co_so='EVA'` vào database của EVB | `CK_LopHoc_site_local` |
| Học viên `ma_co_so='EVA'` vào database của EVB | `CK_HocVien_site_local` |
| Đăng ký tại EVB trỏ vào lớp thuộc EVA | `FK_DangKy_LopCungCoSo` |
| Đăng ký `ma_co_so='EVB'` vào database của EVA | `CK_DangKy_site_local` |

Một lần chạy đầu của ca thứ tư bị chặn bởi `UQ_DangKy_hoc_vien_lop` (cặp học viên–lớp đã tồn tại) thay vì ràng buộc site. Mình đổi sang học viên chưa ghi danh lớp đó để ca thử đúng mục đích; kết quả trong `results.json` là của lần chạy sau.

## Giới hạn

- Hai database tạm trên một instance, dữ liệu giả lập. Chưa có bằng chứng trên Q1/Q7/TD; Q1 và TD hiện vẫn chưa có lớp hay đăng ký thật.
- Các câu SELECT ở hai site không phải snapshot nguyên tử toàn cục.
- Dẫn xuất ở đây là FK ghép và `CHECK` site, không phải Publication có join filter như GV-02.

## Chạy lại

Xem [scripts/README.md](../../scripts/README.md).
