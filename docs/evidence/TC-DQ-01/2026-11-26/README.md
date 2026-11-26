# TC-DQ-01 — Truy vấn phân tán và site thiếu (26/11/2026)

**Kết quả:** đạt trên hai database tạm, sau khi sửa một lỗi phát hiện ngay trong lần chạy này (database offline làm API văng lỗi). Chưa chạy trên Q1/Q7/TD.

## Môi trường

Như [TC-FRAG-01](../../TC-FRAG-01/2026-11-26/README.md). Gọi `student_counts_by_site()` (`core/academics/reports.py`) với `AUTH_SESSION_SITE_CODE=EVA`, `SITE_UNREACHABLE_COOLDOWN_SECONDS=2` cho lần chạy này. Dữ liệu: EVA 5 học viên đang học, EVB 4 (đối chiếu bằng SQL trực tiếp từng database trước khi gọi API).

## Cách chạy

[scripts/ev_dq.py](../../scripts/ev_dq.py), kết quả [results.json](results.json).

## Kết quả

| Bước | Kết quả |
|---|---|
| 1. Cả hai site hoạt động | `complete=true`, tổng 9 = 5 + 4, khớp SQL trực tiếp từng database |
| 2a. Database EVB `OFFLINE` trên instance còn chạy (`ALTER DATABASE … SET OFFLINE`), thử 4 lần liên tiếp | Cả 4 lần: `complete=false`, `missing_sites=["EVB"]` |
| 2b. EVB không truy cập được qua mạng (trỏ cổng kết nối sang cổng đóng, như máy tắt hoặc VPN rớt) | `complete=false`, `missing_sites=["EVB"]`, tổng 5 (chỉ EVA). EVB không bị báo là 0. Truy vấn cục bộ `requested_site=EVA` vẫn chạy. Mất khoảng 6,3 giây (hết thời gian kết nối) |
| 3. EVB hoạt động lại | `complete=true`, tổng 9, khớp lại |

## Lỗi phát hiện và đã sửa: database offline làm API văng lỗi

Trước khi sửa, bước 2a cho kết quả khác hẳn: cả 4 lần thử liên tiếp, `student_counts_by_site()` **văng `django.db.utils.InterfaceError`** thay vì trả `complete=false`.

Nguyên nhân: khi instance còn chạy nhưng database của site offline, đang restore hoặc login bị từ chối, ODBC trả SQLSTATE 28000 (lỗi 4060/18456). pyodbc báo thành `InterfaceError`, không phải lớp con của `DatabaseError`. Các bộ lọc "site thiếu" trong source (như `active_site_state()` ở [core/academics/common.py](../../../../src/api/core/academics/common.py)) chỉ bắt `DatabaseError`, `ImproperlyConfigured`, `KeyError`, `UnknownSiteError` rồi raise lại phần còn lại, nên báo cáo toàn cục sẽ lỗi 500 thay vì cảnh báo thiếu site. Có khoảng 96 chỗ `except DatabaseError` như vậy. Mất mạng hẳn (timeout) không bị ảnh hưởng vì ra `OperationalError`, như bước 2b.

Sửa tại đúng một chỗ mở kết nối: backend mới [core/sites/mssql_backend/base.py](../../../../src/api/core/sites/mssql_backend/base.py) kế thừa backend `mssql` và đổi `InterfaceError` có SQLSTATE `28000`, `08001`, `08004`, `08S01`, `HYT00`, `HYT01` thành `OperationalError` ngay khi mở kết nối; `config/settings.py` dùng backend này cho các database site. Nhờ vậy mọi bộ lọc `except DatabaseError` hiện có tự hoạt động đúng, không phải sửa từng nơi. Lỗi truy vấn (không phải kết nối) và các `InterfaceError` khác (ví dụ thiếu driver, `IM002`) giữ nguyên. Test: [core/sites/test_mssql_backend.py](../../../../src/api/core/sites/test_mssql_backend.py) (3 ca).

Lần chạy trong `results.json` là sau khi sửa. Kịch bản kiểm tra điều kiện này trong tiêu chí đạt (`every_attempt_reports_EVB_missing`).

## Giới hạn

- Hai database tạm trên một instance. Mất mạng được mô phỏng bằng cổng đóng; chưa thử bằng ngắt VPN/tắt máy thật. Database offline được mô phỏng bằng `ALTER DATABASE`, chưa thử trạng thái restore hay login bị từ chối do quyền.
- Chỉ kiểm tra thống kê học viên; chưa chạy từng báo cáo toàn cục khác (chúng dùng chung bộ lọc nên được hưởng cùng bản sửa, nhưng chưa có ca riêng).
- Chưa có học viên đang chuyển cơ sở trong dữ liệu mẫu.
