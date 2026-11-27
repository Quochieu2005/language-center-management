# Kịch bản chạy bằng chứng trên site thật

Dùng khi Q7 và TD mở lại, để làm hết trong một buổi (khoảng 2 giờ) thay vì vừa chạy vừa nghĩ. Mỗi bước có lệnh, kết quả mong đợi, và điều kiện dừng. Bối cảnh: [yêu cầu và kịch bản TC](QLTTNN-Yeu-Cau-Chung-Va-Kiem-Chung.md), [bản nháp báo cáo](QLTTNN-Bao-Cao-Ban-Nhap.md) (phụ lục A là danh sách ảnh), [hướng dẫn DB](../db/README.md).

Lệnh viết cho PowerShell, chạy từ gốc repo trên máy chạy API (máy của Quốc Hiếu), trừ khi ghi khác. `$py = "src/api/.venv/Scripts/python.exe"; $env:PYTHONUTF8 = "1"`.

## 0. Chuẩn bị trước buổi

| Việc | Ai | Ghi chú |
|---|---|---|
| Hai máy chạy SQL Server (Q7, TD), dịch vụ SQL Server Agent bật, vào mạng ZeroTier | Chủ máy Q7 và TD | Cổng 1433 mở |
| Chủ mỗi máy ngồi cùng buổi | Cả nhóm | Cần dừng và bật lại dịch vụ SQL Server để thử mất site, và chụp ảnh SSMS trên máy mình |
| `src/api/.env` có `SITE_DATABASES_JSON` đủ Q1, Q7, TD (đúng máy và tên database) | Quốc Hiếu | TD hiện là `DESKTOP-N47BBPH` / `QLTTNN_TD_MOI`; xác nhận Q7 |
| API và worker chạy: `src\api\run-local.ps1` | Quốc Hiếu | Gồm `sync_accounts`, `sync_courses`, `sync_blog` |
| Máy có `playwright` nếu muốn chụp giao diện tự động | Tùy chọn | Ảnh SSMS vẫn phải chụp tay |

**Dừng và hỏi nếu:** một lệnh báo lỗi không rõ, số liệu không khớp mong đợi, hoặc ai đó muốn tắt ràng buộc (`CHECK`, khóa ngoại) cho "chạy được". Không tắt ràng buộc để lấy ảnh.

## 1. Kiểm tra kết nối (5 phút)

```powershell
& $py src/api/manage.py seed_lab_data          # chỉ in kế hoạch; dòng đầu liệt kê site không truy cập được
```

Mong đợi: không có dòng `Skipping unreachable site(s)`. Nếu còn, kiểm tra từng máy: `Test-NetConnection <host> -Port 1433` (host lấy từ `.env`; không dán host hay mật khẩu vào báo cáo). `[CẦN ẢNH E-3.1-01]` mỗi máy trong ZeroTier; `[CẦN ẢNH E-3.1-02]` kết quả `Test-NetConnection` tới Q7 và TD.

## 2. Migration cho Q7, kiểm tra TD (15 phút)

Công cụ [db/tools/apply_migrations.py](../db/tools/apply_migrations.py) chỉ in trạng thái nếu không có `--apply`, và chỉ nhận database tên `QLTTNN_*`.

```powershell
& $py db/tools/apply_migrations.py --site Q7 47 48                      # xem trạng thái trước
& $py db/tools/apply_migrations.py --site Q7 47 48 --apply --backup     # sao lưu COPY_ONLY rồi chạy
& $py db/tools/apply_migrations.py --site TD 47 48                      # TD đã có 47 và 48: chỉ kiểm tra
& $py db/tools/apply_migrations.py --site Q1 47 48                      # Q1 cũng kiểm tra
```

Mong đợi sau khi chạy: ở cả ba site `47_cover_columns` có `anh_bia_public_id`, `anh_bia_url`; bốn cờ còn lại là `true`. Chạy lặp lại không lỗi. Migration 49 chỉ ở Q1, không chạy cho Q7 và TD. Nếu lỗi ở Q7, dừng, gửi nguyên văn kết quả; bản sao lưu COPY_ONLY nằm trên máy Q7 (không được kiểm chứng bằng `RESTORE VERIFYONLY` vì thiếu quyền). `[CẦN ẢNH E-3.3-01]` phiên bản instance và danh sách bảng của từng site (chụp trong SSMS trên từng máy).

## 3. Kiểm tra đồng bộ tồn đọng (10 phút)

```powershell
Invoke-RestMethod http://localhost:8001/api/v1/blog/articles/ | Select-Object complete, missing_sites, inconsistent_sites
& $py src/api/manage.py shell -c "from django.db import connections; c=connections['site_q1'].cursor(); c.execute('SELECT site_dich, COUNT(*), MAX(so_lan_thu) FROM dbo.DongBoTaiKhoan GROUP BY site_dich'); print([tuple(r) for r in c.fetchall()])"
```

- **Tài khoản:** hàng đợi `DongBoTaiKhoan` phải giảm về 0 trong vài phút sau khi site lên (worker `sync_accounts` thử lại 10 giây, đối soát 60 giây). Nếu `so_lan_thu` vẫn tăng, đọc cột `loi`.
- **Blog:** API Blog hiện báo `inconsistent_sites=["TD"]` (bản `bat-dau-hoc-ngoai-ngu` ở Q1 khác TD, có thể cả Q7). Hàng đợi Blog trống nên worker không tự sửa. Admin cũng không sửa được qua trang Blog khi các bản sao khác nhau (API từ chối "các bản sao không thống nhất"). Cách xử lý: so dữ liệu chỉ đọc giữa Q1, Q7, TD (bảng `BaiVietBlog`: `tieu_de`, `tom_tat`, `noi_dung`, `trang_thai`, `anh_bia_*`), rồi **cùng quyết định** có đưa Q7 và TD về bản của Q1 bằng `UPDATE` trong transaction không. Mình làm cùng, không tự ghi.

Mong đợi sau bước này: `complete=true`, `missing_sites=[]`, `inconsistent_sites=[]`.

## 4. Nạp dữ liệu LAB (5 phút)

```powershell
& $py src/api/manage.py seed_lab_data                 # kế hoạch: khóa học chung, mã sẽ tạo
& $py src/api/manage.py seed_lab_data --apply         # tạo ở cả ba site
```

Mong đợi: mỗi site 8 học viên, 3 lớp, 5 đăng ký, có `LAB` trong mọi mã. Cần một khóa học có ở cả ba site; nếu lệnh báo không có, tạo khóa học qua trang admin trước (để nó nhân bản), rồi chạy lại. `[CẦN ẢNH E-3.7-01]` dữ liệu LAB ở từng site. Dọn lại sau buổi: `seed_lab_data --remove --apply` (không xóa nếu đã có lịch sử chuyển cơ sở).

## 5. Các kịch bản bằng chứng (khoảng 60 phút)

Hai kịch bản đã có bản chạy trên site thật, đã dùng trên Q1 ngày 27/11/2026 ([CON](evidence/TC-CON-01/2026-11-27-site-that/README.md), [DQ](evidence/TC-DQ-01/2026-11-27-site-that/README.md)): `python docs/evidence/scripts/real_con.py <SITE> <thư-mục-kết-quả>` (cần dữ liệu LAB của site đó; mỗi học viên chỉ đăng ký được một lớp mỗi khóa học nên kịch bản tạo thêm học viên LAB cho mỗi vòng) và `python docs/evidence/scripts/real_dq.py <thư-mục-kết-quả>` (chỉ đọc, chạy một lần cho cả ba site). Trong buổi này chạy lại cho Q7 và TD. Các kịch bản còn lại (`ev_frag.py`, `ev_sync.py`) hiện chỉ chạy trên database tạm; khi hai máy mở, mình chuyển chúng sang cấu hình site thật (đổi nơi kết nối, không đổi logic kiểm tra) và lưu kết quả vào `docs/evidence/<TC>/<ngày>/`. Dưới đây là điều cần xảy ra ở từng kịch bản và ảnh cần chụp, để cả nhóm biết trước.

| TC | Việc làm | Kết quả mong đợi | Ảnh |
|---|---|---|---|
| TC-FRAG-01 | Chạy [01_site_fragment_readonly.sql](../db/verification/01_site_fragment_readonly.sql) trên từng site; hợp danh sách lớp LAB của ba site | Không thiếu, không thừa, không giao nhau; đăng ký cùng site với lớp cha; ghi sai site bị `CHECK` chặn | E-3.7-02 |
| TC-CON-01 | Hai phiên đăng ký hai học viên LAB vào lớp `LAB03` (1 chỗ) cùng lúc | Đúng một thành công, một "Lớp đã đủ sĩ số tối đa"; sĩ số 1, một dòng học phí | E-3.7-03 |
| TC-DQ-01 | Lấy số học viên đang học từ từng database rồi so với `GET /admin/reports/students-by-site/`. Sau đó **chủ một máy dừng dịch vụ SQL Server** (hoặc ngắt ZeroTier) và chạy lại | Đủ site thì tổng khớp; thiếu site thì `complete=false`, `missing_sites` nêu đúng site, không đổi thành 0; bật lại thì khớp lại | E-3.7-04 |
| TC-SYNC-01 | Khi một site dừng, sửa một bài Blog ở trang admin; xem `GET/POST /admin/blog/sync/`; bật site lại | Bài ghi ở site còn sống, hàng đợi chờ 1; sau khi site lên và worker chạy thì hai site giống nhau, hàng đợi 0 | E-3.6-02 |
| TC-DTX-01 | Tư vấn tạo đề nghị chuyển học viên `LAB06` Q1 → Q7; Admin Big hoặc Admin Small Q7 duyệt; chạy chuyển (đường **2PC** nếu đã cấu hình theo [mục 2PC](#2pc), nếu không thì đường phục hồi tiến). Thử riêng: dừng Q7 giữa chừng, rồi bật lại và chạy lại | Nguồn `da_chuyen_di`, đích `dang_hoc`, giữ tài khoản và lịch sử; khi đích dừng thì nguồn giữ nguyên, **không** có hồ sơ đích dở dang; chạy lại không tạo hồ sơ thứ hai | E-3.7-05 |
| TC-REP-01 | Sửa một môn học qua trang admin, đọc `MonHoc` ở ba site; chụp Replication Monitor trên máy Q1 | Ba site khớp nội dung và phiên bản; Agent báo thành công | E-3.6-01, E-3.6-02 |
| Quyền và trigger | Mỗi vai trò thử một chức năng được phép và một bị cấm; thử sửa hoặc xóa `Logs` | Được/bị từ chối đúng; `TR_Logs_AppendOnly` chặn | E-3.7-06 |
| Linked Server | Trên máy có `LS_Q7`: chụp cấu hình (che tài khoản) và truy vấn đọc thử qua `LS_Q7` | Kết quả đến từ Q7 | E-3.5-01, E-3.5-02 |
| Agent | Trên máy Publisher: trạng thái SQL Server Agent và lịch sử job | Agent chạy, job thành công | E-3.4-01 |

Trong lúc một site dừng, đây cũng là cơ hội chụp cảnh báo thiếu site ở trang admin (Dashboard, Đăng ký khóa học, Blog).

## <a id="2pc"></a>Cấu hình 2PC giữa các máy thật (làm trước TC-DTX-01, khoảng 30 phút)

Đã chạy đạt trên hai instance cùng máy ([kết quả](evidence/TC-DTX-01/2026-11-27/README.md)); giữa các máy thật cần thêm hạ tầng. **Làm trước, vì đây là rủi ro lớn nhất.**

1. **Migration 50** trên mọi site: `python db/tools/apply_migrations.py --site <Q1|Q7|TD> 50 --apply` (tạo `sp_chuyen_co_so_2pc` và `sp_chuyen_co_so_nhan_2pc`).
2. **MS DTC trên máy Windows (Q1, TD):** Component Services → My Computer → Properties → MSDTC → Security: bật Network DTC Access, Allow Inbound, Allow Outbound; xác thực `No Authentication Required` (workgroup, không có Kerberos); dịch vụ `Distributed Transaction Coordinator` chạy; mở firewall **TCP 135 và dải RPC động 49152–65535** giữa các máy qua ZeroTier.
3. **Linked Server** từ site nguồn tới từng site đích, bật `rpc out` (chạy trên site nguồn; Q1 đã có `LS_Q7`, cần thêm tới TD):
   ```sql
   EXEC sp_addlinkedserver @server = 'LS_TD', @srvproduct = '', @provider = 'MSOLEDBSQL', @datasrc = '<máy,cổng>', @provstr = 'TrustServerCertificate=Yes';
   EXEC sp_serveroption 'LS_TD', 'rpc out', 'true';
   EXEC sp_addlinkedsrvlogin @rmtsrvname = 'LS_TD', @useself = 'false', @rmtuser = '<user>', @rmtpassword = '<mật khẩu>';
   ```
4. **Kiểm tra DTC trước khi chạy ứng dụng** (từ site nguồn; phải chạy được mới đi tiếp):
   ```sql
   BEGIN DISTRIBUTED TRANSACTION; SELECT TOP 1 1 FROM LS_TD.QLTTNN_TD_MOI.dbo.HocVien; COMMIT TRANSACTION;
   ```
5. **Bật cho ứng dụng:** trong `src/api/.env` đặt `TRANSFER_2PC_LINKED_SERVERS_JSON={"Q1":{"Q7":"LS_Q7","TD":"LS_TD"}}` (nguồn → đích → tên Linked Server) rồi khởi động lại API. Cặp không liệt kê vẫn dùng đường phục hồi tiến.
6. **Q7 là SQL Server Linux trong Docker:** MS DTC trên Linux cần `mssql-conf set distributedtransaction.allowonlysecurerpccalls 0`, `distributedtransaction.fallbacktounsecurerpcifnecessary 1`, `network.rpcport 13500`, mở cổng 135 và 13500 từ container; nếu không chạy được thì chứng minh 2PC giữa Q1 và TD (cả hai Windows) hoặc ở mức hai instance cùng máy. Các tham số `mssql-conf` này lấy từ tài liệu Microsoft về giao dịch phân tán trên SQL Server Linux, **chưa kiểm chứng trên Q7 của nhóm**.

**Phương án dự phòng nếu DTC không chạy qua mạng:** chạy `python docs/evidence/scripts/ev_dtx.py` trên một máy có hai instance (cần dịch vụ MS DTC đang chạy), chụp kết quả K1 đến K5, và nói rõ giới hạn.

## 6. Sau buổi

1. Dọn: `seed_lab_data --remove --apply` (trừ khi còn cần cho báo cáo); xác nhận Q7 và TD đã bật lại và đồng bộ về 0 hàng đợi.
2. Lưu ảnh vào `docs/evidence/<TC>/<ngày>/`, che mật khẩu, token, IP riêng.
3. Cập nhật trạng thái trong [bản nháp báo cáo](QLTTNN-Bao-Cao-Ban-Nhap.md) (phụ lục A), [Trang-Thai-Trien-Khai.md](Trang-Thai-Trien-Khai.md) và [bộ yêu cầu](QLTTNN-Yeu-Cau-Chung-Va-Kiem-Chung.md): ghi site thật, ngày, và phần nào vẫn là "chưa kiểm chứng".
4. Cập nhật sơ đồ bố trí máy ([diagrams/bo-tri-vat-ly.mmd](diagrams/bo-tri-vat-ly.mmd)) theo máy thật rồi vẽ lại.
5. Khi cả ba site đã đọc được, chạy `python db/tools/cloudinary_audit.py` (chỉ đọc) để xem ảnh Cloudinary nào không site nào còn dùng; chỉ xóa tay những ảnh mà script báo mồ côi mà **không** có cảnh báo thiếu site.

## Tóm tắt thời gian

| Phần | Thời gian |
|---|---|
| 1. Kết nối | 5 phút |
| 2. Migration | 15 phút |
| 3. Đồng bộ tồn đọng | 10 phút |
| 4. Dữ liệu LAB | 5 phút |
| 5. Kịch bản và ảnh | 60 phút |
| 6. Sau buổi | 20 phút |
| **Tổng** | **khoảng 2 giờ** |
