# TC-DTX-01 — Chuyển cơ sở bằng giao dịch phân tán 2PC (27/11/2026)

**Kết quả:** đạt trên **hai instance SQL Server thật** cùng một máy, nối bằng Linked Server và **MS DTC**. Chưa chạy trên Q7 và TD thật (hai máy đang offline).

## Môi trường

| | Nguồn (EVA) | Đích (EVB) |
|---|---|---|
| Instance | instance mặc định, SQL Server 2022 (`16.0.1000.6`) | instance có tên `MSSQLSERVER01`, SQL Server 2025 (`17.0.1000.7`) |
| Database | `QLTTNN_EVA` (tạm) | `QLTTNN_EVB` (tạm) |
| Nối | Linked Server `LS_EVB` (RPC OUT bật) | — |

Hai database có cùng schema của dự án (các migration đến 48 và **50**). Không đụng `QLTTNN_Q1/Q7/TD`. Database tạm và Linked Server `LS_EVB` đã xóa sau khi chạy.

**Vì sao hai instance:** thử Linked Server trỏ vòng về chính instance đó (loopback) cho lỗi 3910 "Transaction context in use by another session": SQL Server không cho giao dịch phân tán chạy vòng về chính nó. Cần instance thứ hai thật; đây cũng là phương án dự phòng "hai named instance cùng máy" khi MS DTC qua mạng chưa chạy.

## Cách làm

Migration [50_add_transfer_2pc.sql](../../../../db/50_add_transfer_2pc.sql) thêm hai thủ tục (chạy ở mọi site):

- `dbo.sp_chuyen_co_so_2pc` (site nguồn): `BEGIN DISTRIBUTED TRANSACTION`, khóa và kiểm tra giao dịch, đối soát sĩ số lớp, gọi thủ tục đích qua Linked Server, trả chỗ lớp, đóng đăng ký, đánh dấu `da_chuyen_di`, ghi sự kiện, nhật ký, rồi `COMMIT`.
- `dbo.sp_chuyen_co_so_nhan_2pc` (site đích): tạo hoặc kích hoạt hồ sơ học viên (giữ `ma_tai_khoan`), ghi sự kiện, nhật ký, thông báo cho nhân viên đích.

`SET XACT_ABORT ON` bắt buộc: lỗi ở site nào cũng hủy cả hai. Code ứng dụng ([transfers.py](../../../../src/api/core/academics/transfers.py)) chọn đường này khi `TRANSFER_2PC_LINKED_SERVERS_JSON` có cặp nguồn–đích và giao dịch chưa chạy bước nào; không thì giữ đường cũ (transaction cục bộ và phục hồi tiến về phía trước), nên việc chạy dở theo đường cũ vẫn tiếp tục được.

Kịch bản: [ev_dtx.py](../../scripts/ev_dtx.py) (gọi thẳng thủ tục, kết quả [results.json](results.json)) và [ev_dtx_api.py](../../scripts/ev_dtx_api.py) (qua `execute_approved_transfer` của Django, kết quả [ung-dung.json](ung-dung.json)).

## Kết quả

| Ca | Kết quả |
|---|---|
| K1. Chuyển thành công: học viên có tài khoản và 2 đăng ký | Nguồn `da_chuyen_di`, hai đăng ký `chuyen_di`, sĩ số hai lớp giảm đúng, giao dịch `hoan_tat`. Đích có hồ sơ `dang_hoc` giữ nguyên mã tài khoản, đúng một thông báo. Sự kiện đủ ở cả hai site |
| K2. Đích từ chối (đã có hồ sơ khác cùng mã) | Giao dịch bị hủy với lỗi nghiệp vụ; **nguồn không đổi một dòng nào** |
| K3. Site đích **offline** | Lỗi "database offline"; nguồn nguyên vẹn. Bật đích lại rồi chạy lại: **thành công**, không dư hồ sơ |
| K4. Lỗi ở **nguồn sau khi đích đã ghi** (sĩ số lệch) | Giao dịch hủy; hồ sơ đích vừa tạo **cũng bị hủy** (đích không còn hồ sơ, không sự kiện, không thông báo), nguồn nguyên vẹn |
| K5. Học viên **quay lại** cơ sở cũ (EVB → EVA) | Hồ sơ cũ `da_chuyen_di` ở EVA được dùng lại (đúng một hồ sơ, `dang_hoc`, giữ tài khoản), đăng ký cũ vẫn `chuyen_di` (không mở lại), nguồn EVB thành `da_chuyen_di` |
| Qua service Django | `execute_approved_transfer` trả `complete=true, mechanism=2PC`; gọi lại không tạo hồ sơ lần hai; đích từ chối được báo là xung đột (409), không phải lỗi hạ tầng |

K4 là điểm khác với đường phục hồi tiến về phía trước: ở đường cũ, nếu nguồn lỗi sau khi đích đã ghi thì hồ sơ đích phải được giữ ở trạng thái `bao_luu` và phục hồi sau; với 2PC thì hoặc cả hai xong, hoặc như chưa từng có.

## Đánh đổi cần nói thẳng

- 2PC là giao thức **chặn**: nếu điều phối mất kết nối sau pha chuẩn bị, tài nguyên bị khóa tới khi MS DTC phục hồi. Chấp nhận được cho thao tác hiếm, không tranh chấp như chuyển cơ sở; không dùng cho đăng ký lớp.
- Khi đích offline, 2PC **thất bại ngay** (không "chờ và chạy tiếp" như đường cũ); người dùng thử lại khi đích lên.
- Đường 2PC chỉ chạy cho giao dịch chưa bắt đầu; giao dịch đã chạy dở theo đường cũ tiếp tục theo đường cũ.

## Giới hạn

- Hai instance trên **cùng một máy**, không có mạng giữa chúng. Chưa thử MS DTC qua ZeroTier giữa các máy thật, nơi cần mở TCP 135 và dải RPC động, bật Network DTC Access, và `No Authentication Required` trong workgroup. Q7 chạy SQL Server trên Linux trong Docker: MS DTC trên Linux cần cấu hình riêng (xem [runbook](../../../QLTTNN-Chay-Bang-Chung-Site-That.md#2pc)).
- Chưa kiểm tra qua HTTP và giao diện.
