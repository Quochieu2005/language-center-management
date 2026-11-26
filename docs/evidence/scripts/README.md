# Bộ chạy kiểm chứng trên database tạm

Dựng hai database tạm `QLTTNN_EVA` và `QLTTNN_EVB` (site `EVA` là authority, `EVB` là site còn lại) trên **instance của Q1**, áp schema và migration của dự án, chạy bốn kịch bản bằng code thật của source, rồi xóa. Không đụng `QLTTNN_Q1/Q7/TD`. Đây là mô phỏng hai site trên một máy, không thay cho kiểm chứng ba server vật lý.

## Yêu cầu

- Chạy từ gốc repo với Python của `src/api/.venv` (cần `pyodbc` và `python-dotenv`, đã có).
- `src/api/.env` có `SITE_DATABASES_JSON` với site `Q1` dùng `trusted_connection` (Windows Authentication) và tài khoản có quyền `CREATE DATABASE`/`DROP DATABASE`. Script chỉ đọc host/cổng từ đó và không in thông tin đăng nhập.
- Tên database phải có dạng `QLTTNN_<SITE>`; migration 30 suy ra mã site từ tên.

## Thứ tự chạy

```powershell
$py = "src/api/.venv/Scripts/python.exe"; $env:PYTHONUTF8 = "1"
& $py docs/evidence/scripts/ev_harness.py create                      # tạo hai database rỗng
& $py docs/evidence/scripts/ev_harness.py script 01_create_schema.sql # schema nền cho cả hai
& $py docs/evidence/scripts/ev_build.py EVA EVB                       # migration (45, 49 chỉ ở EVA)
& $py docs/evidence/scripts/ev_fixture.py                             # dữ liệu mẫu cho TC-FRAG/CON/DQ
& $py docs/evidence/scripts/ev_frag.py                                # TC-FRAG-01
& $py docs/evidence/scripts/ev_con.py                                 # TC-CON-01
& $py docs/evidence/scripts/ev_dq.py                                  # TC-DQ-01
& $py docs/evidence/scripts/ev_harness.py drop                        # xóa hai database tạm
```

`ev_sync.py` (TC-SYNC-01) cần database sạch: chạy `create`, `script 01_create_schema.sql`, `ev_build.py EVA EVB` rồi `ev_sync.py`, không chạy `ev_fixture.py`/`ev_con.py` trước. Mỗi kịch bản ghi `results.json` vào `docs/evidence/<TC>/2026-11-26/`; đổi hằng ngày trong `OUT` nếu chạy lại ở ngày khác.

## Lưu ý

- `ev_dq.py` và `ev_sync.py` mô phỏng mất kết nối bằng cách đổi cổng của alias sang cổng đóng (và `ALTER DATABASE … SET OFFLINE` cho phần phát hiện `InterfaceError`); chúng luôn khôi phục khi kết thúc, kể cả khi lỗi.
- Chạy lại `ev_build.py` trên database đã dựng sẽ lỗi trùng khóa ở bước nạp `CoSo`; hãy `drop` rồi `create` lại.
- Không dùng các script này cho `QLTTNN_Q1/Q7/TD`: chúng tạo, sửa và xóa dữ liệu.
