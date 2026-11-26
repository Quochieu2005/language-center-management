# TC-DQ-01 — Truy vấn phân tán và site thiếu (26/11/2026)

**Kết quả:** đạt khi site mất kết nối mạng; **phát hiện một lỗi** khi database offline trên instance còn truy cập được. Chạy trên hai database tạm, chưa chạy trên Q1/Q7/TD.

## Môi trường

Như [TC-FRAG-01](../../TC-FRAG-01/2026-11-26/README.md). Gọi `student_counts_by_site()` (`core/academics/reports.py`) với `AUTH_SESSION_SITE_CODE=EVA`, `SITE_UNREACHABLE_COOLDOWN_SECONDS=2` cho lần chạy này. Dữ liệu: EVA 59 học viên đang học, EVB 4 (đối chiếu bằng SQL trực tiếp từng database trước khi gọi API).

## Cách chạy

[scripts/ev_dq.py](../../scripts/ev_dq.py), kết quả [results.json](results.json).

## Kết quả

| Bước | Kết quả |
|---|---|
| 1. Cả hai site hoạt động | `complete=true`, tổng 63 = 59 + 4, khớp SQL trực tiếp từng database |
| 2b. EVB không truy cập được qua mạng (trỏ cổng kết nối sang cổng đóng, như máy tắt hoặc VPN rớt) | `complete=false`, `missing_sites=["EVB"]`, tổng 59 (chỉ EVA). EVB không bị báo là 0. Truy vấn cục bộ `requested_site=EVA` vẫn chạy. Mất khoảng 6,3 giây (hết thời gian kết nối) |
| 3. EVB hoạt động lại | `complete=true`, tổng 63, khớp lại |

## Phát hiện: database offline trên instance còn sống làm API văng lỗi

Bước 2a đưa `QLTTNN_EVB` về `OFFLINE` bằng `ALTER DATABASE` (instance vẫn chạy). Cả 4 lần thử liên tiếp, `student_counts_by_site()` **văng `django.db.utils.InterfaceError`** thay vì trả `complete=false`.

Nguyên nhân: ODBC báo "Login failed / Cannot open database" (SQLSTATE 28000, lỗi 4060) thành `InterfaceError`, không phải lớp con của `DatabaseError`. Bộ lọc ở `active_site_state()` ([core/academics/common.py](../../../../src/api/core/academics/common.py)) chỉ coi `DatabaseError`, `ImproperlyConfigured`, `KeyError`, `UnknownSiteError` là "site thiếu", còn lại raise lại. Trong source có khoảng 96 chỗ `except DatabaseError`.

Ảnh hưởng thực tế: nếu máy site còn chạy SQL Server nhưng database đang offline, đang restore, hoặc login bị từ chối, báo cáo toàn cục có thể lỗi 500 thay vì cảnh báo thiếu site. Mất mạng hẳn (timeout) không bị ảnh hưởng, như bước 2b. Một lần chạy thử trước đó của bước 2a (chỉ gọi một lần) từng trả bình thường, nên hành vi này có thể phụ thuộc trạng thái kết nối đang được giữ; 4/4 lần ở lần chạy cuối đều văng lỗi.

**Chưa sửa** trong đợt này (ảnh hưởng nhiều nơi, cần quyết định phạm vi). Hướng sửa: coi `django.db.utils.InterfaceError` (hoặc lớp cha `django.db.utils.Error`) là lỗi hạ tầng ở các bộ lọc site thiếu, kèm test.

## Giới hạn

- Hai database tạm trên một instance. Mất mạng được mô phỏng bằng cổng đóng; chưa thử bằng ngắt VPN/tắt máy thật.
- Chỉ kiểm tra thống kê học viên; chưa kiểm tra các báo cáo toàn cục khác.
- Chưa có học viên đang chuyển cơ sở trong dữ liệu mẫu.
