# ĐỌC TRƯỚC KHI LÀM BẤT CỨ ĐIỀU GÌ

## Quy trình Git bắt buộc

Áp dụng cho mọi thành viên và mọi tác nhân AI làm việc trong repository này. Không tự ý bỏ qua các bước sau.

- **Không đẩy code lên `main`**: không commit trực tiếp, push, mở Pull Request (PR) nhắm vào `main`, hoặc dùng `main` làm nhánh làm việc.
- **Không ghi trực tiếp lên `dev`**: không commit hoặc push lên `dev`; không tự merge nhánh cá nhân vào `dev` bằng Git, GitHub hay công cụ khác.
- Mỗi người làm trên **nhánh cá nhân** tạo từ bản mới nhất của `dev`, theo tên `feature/<ten-thanh-vien>/<mo-ta-ngan>` (ví dụ: `feature/quoc-hieu/site-router`). Chỉ push nhánh cá nhân của task đó.
- Khi hoàn tất, push nhánh cá nhân và mở **PR từ nhánh cá nhân vào `dev`**. PR phải nêu mục đích, thay đổi chính, bảng/site bị ảnh hưởng, loại nghiệp vụ phân tán, kiểm tra đã chạy và tài liệu đã cập nhật. Yêu cầu **Quốc Hiếu, trưởng nhóm**, review PR.
- Tác giả không tự duyệt hoặc merge PR của mình. Các thành viên khác có thể review bổ sung, nhưng không thay thế bước Quốc Hiếu review; chỉ Quốc Hiếu mới merge PR đã kiểm tra vào `dev`. Nếu cần sửa sau review, tác giả cập nhật nhánh cá nhân và đẩy commit mới lên chính nhánh đó; không tự merge để xử lý nhanh.
- Không đoán tài khoản GitHub của Quốc Hiếu. Nếu không xác định được tài khoản để gán reviewer, để PR ở trạng thái chờ và báo Quốc Hiếu; không tự thay bước review bắt buộc của trưởng nhóm hoặc tự merge.
- Nếu chưa có `dev`, không xác định được remote/nhánh cá nhân, hoặc repository không cho tạo PR, dừng trước thao tác ghi lên nhánh dùng chung và báo rõ trở ngại. **Không lấy `main` làm phương án thay thế.**

Quy trình chuẩn: cập nhật `dev` → tạo nhánh cá nhân → sửa và kiểm tra → push nhánh cá nhân → mở PR vào `dev` và yêu cầu Quốc Hiếu review → chờ Quốc Hiếu merge. Các quy tắc này cũng áp dụng khi một tác nhân AI được yêu cầu hoàn thành thay đổi code.

### Nội dung bắt buộc trong `Add a title` và `Add a description`

- **`Add a title`** phải nêu loại thay đổi, phạm vi và kết quả cụ thể; không dùng tiêu đề chung chung như `update code`, `fix`, `changes` hoặc chỉ ghi số PR. Mẫu: `<loại>(<phạm-vi>): <thay đổi và kết quả>`. Ví dụ: `feat(enrollment): đăng ký học viên vào lớp tại đúng cơ sở`.
- **`Add a description`** phải giải thích đầy đủ mọi thay đổi code thuộc PR để Quốc Hiếu có thể review mà không phải đoán. Ghi theo chức năng/luồng và nêu file hoặc module liên quan; không chỉ ghi “đã sửa lỗi” hay “xem code”.
- Mỗi lần push thêm commit/code vào cùng một PR, cập nhật `Add a description` để nó phản ánh **toàn bộ diff hiện tại của PR**: giữ mô tả các thay đổi trước đó và bổ sung mọi thay đổi mới. Không để phần mô tả chỉ nói về commit mới nhất. Nếu phạm vi PR đổi đáng kể, cập nhật cả title.
- Trước khi mở PR tiếp theo, PR mới phải có title và description riêng, mô tả đầy đủ tất cả thay đổi của PR mới. Không dựa vào mô tả của PR trước. Lịch sử commit không thay thế description.
- Chưa được yêu cầu review/merge nếu title hoặc description thiếu, lỗi thời, hoặc không bao quát hết code đang có trong PR.

Description tối thiểu phải có: mục tiêu; các thay đổi và hành vi trước/sau; chức năng/file/module bị ảnh hưởng; loại nghiệp vụ (`LOCAL`, `GLOBAL`, `REPLICATED-WRITE`, `DISTRIBUTED-TX`), site và bảng đọc/ghi; quyền/API/UI liên quan; cách kiểm tra và kết quả; tài liệu/schema/migration đã cập nhật; rủi ro hoặc điểm còn mở. Nếu một mục không áp dụng, ghi rõ `Không áp dụng` thay vì bỏ trống.

Mẫu description:

```markdown
## Mục tiêu
Vấn đề cần giải quyết và kết quả mong muốn.

## Thay đổi
- Chức năng/luồng, module hoặc file được sửa; hành vi trước và sau.
- Các thay đổi code khác nằm trong PR này.

## Ảnh hưởng dữ liệu phân tán
- Loại nghiệp vụ:
- Site được đọc/ghi:
- Bảng được đọc/ghi:
- Quyền cần kiểm tra:

## Kiểm tra
- Lệnh/kịch bản đã chạy:
- Kết quả:

## Tài liệu và rủi ro
- Tài liệu/schema/migration đã cập nhật:
- Điểm còn mở hoặc rủi ro:
```

## Dự án này là gì

Đây là bài tập môn **Cơ sở dữ liệu PHÂN TÁN** (distributed database): hệ thống quản lý trung tâm ngoại ngữ hiện có **3 cơ sở** (Q1, Q7, TD); thiết kế cần lấy danh sách site đang hoạt động từ dữ liệu để có thể bổ sung cơ sở.

**Đây KHÔNG phải ứng dụng CRUD thông thường với 1 database.** Mục tiêu của đồ án là thể hiện các kỹ thuật phân tán: phân mảnh dữ liệu, nhân bản, truy vấn toàn cục, giao dịch phân tán.

## Phạm vi bắt buộc theo đề tài được giao

Đề tài là **Đề tài 10: Quản lý trung tâm đào tạo ngoại ngữ**. Ba cơ sở ban đầu là **Quận 1 (`Q1`)**, **Quận 7 (`Q7`)** và **Thủ Đức (`TD`)**. Đây là ba site của hệ thống CSDL phân tán, không phải ba giá trị giả lập trong một CSDL duy nhất.

Các thực thể/bảng nghiệp vụ cốt lõi phải được thể hiện trong thiết kế và triển khai: `HocVien`, `LopHoc`, `GiaoVien`, `MonHoc`, `DangKy`, `HocPhi`, `Diem`. Có thể có thêm bảng hỗ trợ như `CoSo`, `KhoaHoc`, `TaiKhoan`, `BuoiHoc`, `PhieuThu`, `DiemDanh` và nhật ký, nhưng bảng hỗ trợ không thay thế các bảng cốt lõi hoặc làm lệch đề tài.

Sáu nghiệp vụ bắt buộc phải có trong thiết kế, API và kịch bản kiểm chứng: **đăng ký khóa học**, **xếp lớp**, **chuyển cơ sở**, **đóng học phí**, **quản lý điểm**, **thống kê học viên theo cơ sở**. Khi sửa một nghiệp vụ, phải xác định bảng được đọc/ghi, site tham gia và kiểu truy cập phân tán tương ứng; cập nhật README, schema hoặc tài liệu triển khai liên quan để thành viên khác có thể lần theo từ yêu cầu đến source.

Mỗi cơ sở giữ **một CSDL SQL Server riêng**, cùng cấu trúc logic nhưng lưu các mảnh dữ liệu tương ứng. Có thể nhân bản những bảng được xác định là dùng chung; thao tác Global Query chỉ đọc các CSDL site riêng rồi tổng hợp kết quả ở tầng ứng dụng, không tạo CSDL trung tâm để gộp dữ liệu nghiệp vụ. Chi tiết phân loại và vị trí từng bảng phải thống nhất với `docs/DATABASE_SCHEMA.md`.

## Mô hình trong 5 dòng

1. Hiện có **3 CSDL độc lập** (Q1, Q7, TD), cùng cấu trúc bảng nhưng **chứa dữ liệu khác nhau**. Dù chạy trên 1 máy, vẫn phải là một CSDL / một kết nối riêng cho mỗi cơ sở, **không** gộp vào một CSDL có cột `chi_nhanh`.
2. Có 1 tầng **Coordinator trong Django API** đứng giữa: Next.js gọi API; Django chọn đúng cơ sở, gộp kết quả và điều phối giao dịch. SQL Server lưu dữ liệu; SSMS là công cụ quản trị, không phải frontend.
3. Dữ liệu chia 4 loại: **nhân bản** (giống hệt ở tất cả cơ sở hoạt động) · **phân mảnh** (mỗi cơ sở chỉ giữ phần của mình) · **dẫn xuất** (đi theo bảng cha) · **cục bộ** (nhật ký, mã tạm).
4. Mọi thao tác thuộc 1 trong 4 kiểu: `LOCAL` (1 cơ sở) · `GLOBAL` (đọc nhiều cơ sở rồi gộp) · `REPLICATED-WRITE` (ghi theo chính sách tới tất cả cơ sở hoạt động) · `DISTRIBUTED-TX` (giao dịch nhiều cơ sở: chuyển cơ sở).
   Riêng chuyển cơ sở có ba chặng: Admin Small tạo đề nghị `LOCAL` tại nguồn; Admin Big xem hộp thư/ra quyết định `GLOBAL` và quyết định được ghi tại nguồn; chỉ đề nghị đã duyệt mới chạy `DISTRIBUTED-TX`.
5. Chi tiết nằm ở `docs/DATABASE_SCHEMA.md` (bảng, phân mảnh) và `README.md` (luồng nghiệp vụ).

## Những lỗi AI hay mắc: KHÔNG ĐƯỢC LÀM

**Nguyên tắc bắt buộc:** đây là hệ CSDL phân tán với CSDL SQL Server riêng cho từng site. Dữ liệu nghiệp vụ được phân mảnh theo cơ sở; chỉ các bảng dùng chung đã xác định trong schema mới được nhân bản theo chính sách. Global Query chỉ tổng hợp kết quả đọc tại tầng ứng dụng để trả lời/thống kê, không nhập các CSDL hoặc chuyển toàn bộ dữ liệu về một DB trung tâm.

| ❌ Sai | ✔ Đúng |
|--------|---------|
| Gộp tất cả vào 1 CSDL, thêm cột `branch_id` | Giữ CSDL riêng cho từng cơ sở; phân mảnh dữ liệu nghiệp vụ và chỉ nhân bản các bảng dùng chung theo schema |
| Tạo khóa ngoại hoặc `JOIN` giữa bảng của 2 cơ sở | Không có khóa ngoại/JOIN xuyên cơ sở. Global Query hỏi từng CSDL riêng qua Site Router rồi **chỉ tổng hợp kết quả trả về ở tầng ứng dụng**; không gộp dữ liệu lưu trữ vào DB chung |
| Dùng 1 kết nối mặc định cho mọi truy vấn | Luôn qua **Site Router** để chọn đúng kết nối theo cơ sở |
| ID tự tăng 1, 2, 3... | Mã có tiền tố cơ sở: `Q1-HV-000001` |
| Ghi bảng dùng chung (môn, khóa, tài khoản) vào 1 cơ sở | Ghi tới mọi cơ sở `hoat_dong` theo chính sách đồng bộ; thiếu site thì **không báo thành công** |
| Đoán cơ sở của học viên từ tiền tố mã | Học viên có thể chuyển cơ sở → tìm bằng Global Query, lấy bản `dang_hoc` |
| `DELETE` học viên khi chuyển cơ sở | Bản cũ đánh dấu `da_chuyen_di`, **giữ lại** lịch sử |
| Cho Admin Small tự chuyển hoặc bỏ qua bước duyệt; ghi hai site bằng lệnh rời nhau | Admin Small tạo đề nghị `cho_duyet` tại CSDL nguồn; Admin Big xem hộp thư bằng Global Query và duyệt/từ chối. Chỉ sau khi duyệt, Coordinator mới chạy giao dịch phân tán. `GiaoDichChuyenCoSo` lưu trạng thái ở nguồn; `LichSuChuyenCoSo` append-only tại site phát sinh. Nếu đích chưa commit thì giữ nguồn; sau khi đích commit thì phục hồi tiến về phía trước, không xóa đích. Không tuyên bố ACID nguyên tử xuyên CSDL nếu chưa cấu hình và kiểm thử |
| Cộng cả bản `da_chuyen_di` vào thống kê | Chỉ cộng bản `dang_hoc` |
| Ghi mật khẩu / token vào nhật ký, hoặc lưu bản gốc | Chỉ lưu bản băm; không bao giờ ghi vào nhật ký |
| Viết cứng dữ liệu mẫu trong code | Mọi dữ liệu lấy từ CSDL |
| Viết cứng danh sách `['Q1','Q7','TD']` hoặc vòng lặp "3 lần" | Lấy các cơ sở có `trang_thai = hoat_dong` trong bảng Cơ sở (đã nhân bản nên cơ sở nào cũng tự hỏi được), đối chiếu với cấu hình kết nối. Số cơ sở có thể tăng (vd Bình Thạnh `BT`), xem `README.md` mục 2 và 5.14 |
| Rải logic "ghi đủ các cơ sở hoạt động" ra nhiều luồng | Mọi logic ghi dữ liệu dùng chung chỉ nằm ở **một chỗ** (Đồng bộ dữ liệu dùng chung), để sau này đổi chế độ khi có nhiều cơ sở không phải sửa nhiều nơi (xem `README.md` mục 5.14) |
| Tự ý đổi framework / DBMS | Stack đã chốt: **Next.js frontend, Django API, SQL Server**; dùng **SSMS** để quản trị. Không tự thay stack nếu chưa được nhóm thống nhất. Các quyết định triển khai còn mở ở `README.md` mục 9 |

## Trước khi viết code, tự trả lời 4 câu

1. Dữ liệu này thuộc loại nào: nhân bản, phân mảnh, dẫn xuất hay cục bộ? (xem `docs/DATABASE_SCHEMA.md` mục 2–3)
2. Nghiệp vụ này là `LOCAL`, `GLOBAL`, `REPLICATED-WRITE` hay `DISTRIBUTED-TX`? (xem `README.md` mục 5)
3. Truy vấn có đi qua Site Router không? Có vô tình đụng 2 cơ sở trong 1 câu lệnh không?
4. Đã kiểm tra quyền và ghi nhật ký chưa?

## Đọc tiếp

- `docs/DATABASE_SCHEMA.md`: các bảng, kiểu phân mảnh, ràng buộc phân tán (mục 4), dữ liệu mẫu
- `README.md`: kiến trúc, phân quyền, 14 luồng nghiệp vụ kèm ví dụ (có thêm / đóng cơ sở)
- `docs/QLTTNN-Lam-Viec-Nhom.md`: phân công, quy trình task, nhánh cá nhân và PR
- Đổi bảng hoặc luồng → cập nhật `README.md`, `docs/DATABASE_SCHEMA.md` và tài liệu con liên quan trong cùng PR; nhờ Quốc Hiếu review và merge theo quy trình Git ở trên
