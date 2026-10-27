# ĐỌC TRƯỚC KHI LÀM BẤT CỨ ĐIỀU GÌ

## Quy trình Git bắt buộc

Áp dụng cho mọi thành viên và mọi tác nhân AI làm việc trong repository này. Không tự ý bỏ qua các bước sau.

- **Không đẩy code lên `main`**: không commit trực tiếp, push, mở Pull Request (PR) nhắm vào `main`, hoặc dùng `main` làm nhánh làm việc.
- **Không ghi trực tiếp lên `Dev`**: không commit hoặc push thẳng lên `Dev`; thay đổi phải đi từ nhánh cá nhân qua PR.
- Mỗi người làm trên **nhánh cá nhân mang tên thành viên**, tạo từ bản mới nhất của `Dev` (ví dụ: `qhiu`, `nguyen-van-a`). Không thêm tiền tố `feature/` hay tên task vào tên nhánh. Mỗi thành viên push công việc của mình lên đúng nhánh cá nhân đó.
- Khi hoàn tất, push nhánh cá nhân và mở **PR từ nhánh cá nhân vào `Dev`**. PR phải nêu mục đích, thay đổi chính, bảng/site bị ảnh hưởng, loại nghiệp vụ phân tán, kiểm tra đã chạy và tài liệu đã cập nhật. Yêu cầu **Quốc Hiếu, trưởng nhóm**, review PR.
- Tác giả không tự duyệt hoặc merge PR của mình. Các thành viên khác có thể review bổ sung, nhưng không thay thế bước Quốc Hiếu review; chỉ Quốc Hiếu mới merge PR đã kiểm tra vào `Dev`. Nếu cần sửa sau review, tác giả cập nhật nhánh cá nhân và đẩy commit mới lên chính nhánh đó; không tự merge để xử lý nhanh.
- Không đoán tài khoản GitHub của Quốc Hiếu. Nếu không xác định được tài khoản để gán reviewer, để PR ở trạng thái chờ và báo Quốc Hiếu; không tự thay bước review bắt buộc của trưởng nhóm hoặc tự merge.
- Nếu chưa có `Dev`, không xác định được remote/nhánh cá nhân, hoặc repository không cho tạo PR, dừng trước thao tác ghi lên nhánh dùng chung và báo rõ trở ngại. **Không lấy `main` làm phương án thay thế.**

Quy trình chuẩn: cập nhật `Dev` → tạo/chuyển sang nhánh mang tên thành viên → sửa và kiểm tra → push nhánh cá nhân → mở PR vào `Dev` và yêu cầu Quốc Hiếu review → chờ Quốc Hiếu merge. Các quy tắc này cũng áp dụng khi một tác nhân AI được yêu cầu hoàn thành thay đổi code.

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

## Yêu cầu chung của môn học (áp dụng cho tất cả đề tài)

Mỗi đề tài có **2–4 site**. Nhóm phải triển khai tối thiểu **phân mảnh, replication (nhân bản), transaction (giao dịch) và đồng bộ dữ liệu**. Đồ án này chọn **3 site Q1, Q7, TD**, mỗi site có CSDL SQL Server riêng; số site này nằm trong phạm vi yêu cầu của môn học.

Không bắt buộc mọi nhóm dùng cùng một kiểu phân mảnh. Tuy nhiên, mỗi nhóm phải chứng minh được ít nhất: **1 phương pháp phân mảnh + 1 phương pháp replication + 1 distributed transaction (giao dịch phân tán) + 1 tình huống concurrency (truy cập đồng thời) + 1 distributed query (truy vấn phân tán)**. Có mô tả hoặc sơ đồ thiết kế chưa đủ để kết luận đã đáp ứng; phải có kịch bản chạy thực tế và kết quả kiểm chứng.

Mã yêu cầu **YC-01–YC-07**, cách chạy các kịch bản **TC-SITE-01, TC-FRAG-01, TC-REP-01, TC-DTX-01, TC-CON-01, TC-DQ-01, TC-SYNC-01**, phân công và mẫu bằng chứng nằm tại [docs/QLTTNN-Yeu-Cau-Chung-Va-Kiem-Chung.md](docs/QLTTNN-Yeu-Cau-Chung-Va-Kiem-Chung.md). Khi sửa phần liên quan, đối chiếu cùng README, FS, API/UI specs và tài liệu triển khai; không chỉ cập nhật yêu cầu trong riêng `AGENTS.md`.

### Áp dụng và kiểm chứng trong đồ án này

| Nội dung bắt buộc | Kịch bản cần triển khai và chứng minh |
|---|---|
| **Phân mảnh — ít nhất 1 phương pháp** | Dùng phân mảnh ngang theo cơ sở cho dữ liệu nghiệp vụ, ví dụ `LopHoc`; các bảng con phân mảnh dẫn xuất theo bảng cha như `DangKy` theo lớp. Ghi rõ điều kiện phân mảnh, vị trí từng mảnh và truy vấn đối chiếu để chứng minh tính đầy đủ, khả năng tái thiết và tính không giao nhau của các mảnh ngang đã chọn. |
| **Replication — ít nhất 1 phương pháp** | Chọn và ghi rõ phương pháp nhân bản cho bảng dùng chung theo schema, ví dụ `MonHoc`: nơi được phép ghi, các site nhận bản sao, hướng truyền và cơ chế xử lý lỗi/xung đột. Thay đổi dữ liệu ở nơi được phép ghi rồi đọc từng bản sao để chứng minh cơ chế thực sự truyền thay đổi; nạp cùng dữ liệu mẫu thủ công vào ba DB không đủ chứng minh replication. |
| **Distributed transaction — ít nhất 1 giao dịch** | Dùng nghiệp vụ chuyển cơ sở đã được Admin Big duyệt, tác động tới CSDL nguồn và đích. Ghi cơ chế điều phối/commit, trạng thái trước–sau tại hai site, thử lỗi trước và sau khi đích commit, rồi kiểm tra retry/phục hồi không tạo hồ sơ trùng hoặc làm mất lịch sử. Transaction chỉ chạy trong một CSDL không thay thế bằng chứng giao dịch phân tán. |
| **Concurrency — ít nhất 1 tình huống** | Cho hai phiên/yêu cầu chạy đồng thời để đăng ký hai học viên vào cùng lớp chỉ còn một chỗ. Chứng minh đúng một yêu cầu thành công, yêu cầu còn lại được xử lý rõ ràng, sĩ số không vượt sức chứa và yêu cầu thất bại không để lại `DangKy`/`HocPhi` dở dang. Ghi cơ chế khóa, mức cô lập hoặc kiểm soát phiên bản thực tế; chạy tuần tự hai yêu cầu không được tính là kiểm thử đồng thời. |
| **Distributed query — ít nhất 1 truy vấn** | Thống kê học viên theo cơ sở qua Global Query: Site Router đọc từng CSDL site, API tổng hợp kết quả. Đối chiếu số liệu với truy vấn cục bộ tại từng site, áp dụng quy tắc trạng thái học viên/chuyển cơ sở để tránh đếm trùng; thử ngắt một site và xác nhận kết quả báo thiếu site. Không gom dữ liệu vào DB trung tâm hoặc dùng JOIN xuyên site. |
| **Đồng bộ dữ liệu — bắt buộc** | Sau thay đổi bảng nhân bản, kiểm tra dữ liệu và trạng thái đồng bộ ở các site. Thử một site mất kết nối, khôi phục rồi retry/đối soát theo chính sách đã chốt; chứng minh bản sao được cập nhật đúng, không ghi trùng và không báo hoàn tất khi còn thiếu site bắt buộc. Có thể dùng cùng cơ chế replication để chứng minh nội dung này, nhưng phải kiểm tra cả trường hợp lỗi và phục hồi. |

### Bằng chứng và giới hạn khi kết luận hoàn thành

- Mỗi kịch bản ghi rõ mã/tên, người thực hiện, điều kiện ban đầu, site và bảng tham gia, script/lệnh/API hoặc các phiên đồng thời, kết quả mong đợi, kết quả thực tế, dữ liệu trước–sau và ảnh/log kiểm chứng. Bằng chứng không chứa mật khẩu, token hay thông tin kết nối bí mật.
- **Replication và distributed transaction là yêu cầu bắt buộc**, kể cả khi tài liệu hiện còn để mở lựa chọn công cụ triển khai. Phải chốt cơ chế cụ thể và cập nhật FS, README, schema, đặc tả và tài liệu triển khai có liên quan trước khi code phụ thuộc vào lựa chọn đó; không diễn giải việc chưa chọn công cụ thành được phép bỏ yêu cầu.
- Thiết kế chuyển cơ sở hiện dùng Coordinator với transaction cục bộ và phục hồi tiến về phía trước sau khi đích commit. Phải mô tả đúng bảo đảm của cơ chế này; không ghi là ACID nguyên tử xuyên CSDL hoặc đã dùng MSDTC/2PC khi chưa cấu hình và kiểm thử. Nếu tiêu chí giảng viên yêu cầu cơ chế giao dịch phân tán do DBMS quản lý, phải thống nhất và triển khai bổ sung cơ chế đó, không tự coi bằng chứng phục hồi hiện tại là đủ thay thế.
- Chỉ đánh dấu đáp ứng khi có kết quả kiểm chứng cho đủ năm nội dung tối thiểu và đồng bộ dữ liệu. Mục chưa chạy hoặc chưa có bằng chứng phải ghi rõ **chưa kiểm chứng**; không suy ra đã đạt từ việc có ba DB, có màn hình ứng dụng hay có tài liệu thiết kế.

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

## Giới hạn độ dài file mã nguồn

- Mỗi file mã nguồn được tạo hoặc sửa (Python, TypeScript/JavaScript, SQL, SCSS và mã thực thi tương tự) tối đa **1.000 dòng vật lý**, tính cả dòng trống và chú thích. Markdown, dữ liệu cấu hình thuần, file sinh tự động và file khóa phụ thuộc không thuộc giới hạn này.
- Trước khi thêm logic, kiểm tra số dòng của file. Nếu file đã có 1.000 dòng hoặc thay đổi sẽ làm vượt giới hạn, tách phần trách nhiệm liên quan thành file/module riêng rồi import hoặc re-export tại điểm tích hợp phù hợp; không tiếp tục dồn logic vào file quá dài.
- Với file cũ đã vượt giới hạn, không thêm logic mới vào đó; khi cần sửa, tách phần liên quan trước. Không refactor file cũ ngoài phạm vi chỉ để làm đẹp.
- Với SQL migration/script, nếu vượt giới hạn thì tách thành các file migration đánh số theo thứ tự chạy; không giả định SQL hỗ trợ import như Python.
- Khi tách file, giữ nguyên hợp đồng API và hành vi hiện có, tránh import vòng, cập nhật nơi gọi và chạy các kiểm tra liên quan.

## Đặc tả API và giao diện phải đọc trước khi làm

`specs/README.md` là mục lục và quy tắc đồng bộ đặc tả. Trước khi sửa API, đọc `specs/api.md`; trước khi sửa giao diện, đọc `specs/ui-ux.md`. Nếu thay đổi ảnh hưởng cả thao tác người dùng lẫn API, phải đối chiếu và cập nhật **cả hai**. Các file trong `specs/` là tài liệu thiết kế; endpoint hoặc màn hình được ghi là đề xuất/chưa bật không được mô tả như đã triển khai hay tự ý coi là hợp đồng đã chốt.

### Quy tắc dùng Functional Specification

- Trước khi triển khai hoặc sửa một chức năng nghiệp vụ, đọc `fs/README.md` và yêu cầu tương ứng trong `fs/Functional-Specification.md`, đồng thời đối chiếu `README.md`, `docs/DATABASE_SCHEMA.md` và `specs/api.md`/`specs/ui-ux.md` theo phần bị ảnh hưởng.
- `fs/Functional-Specification.md` là nguồn mô tả mục tiêu chức năng, vai trò, điều kiện, luồng chính, trường hợp lỗi và tiêu chí nghiệm thu. Tài liệu này không thay thế schema hay hợp đồng API, và không chứng minh chức năng đã được code hoặc kiểm thử.
- Khi thêm, đổi hoặc bỏ hành vi nghiệp vụ, cập nhật yêu cầu/tiêu chí nghiệm thu trong `fs/Functional-Specification.md` cùng PR. Nếu thay đổi ảnh hưởng API hoặc giao diện, cập nhật tương ứng `specs/api.md` và/hoặc `specs/ui-ux.md`; nếu ảnh hưởng bảng, cột, khóa, phân mảnh hoặc định vị, cập nhật `docs/DATABASE_SCHEMA.md` và script/migration liên quan. Cập nhật `README.md` khi kiến trúc hoặc luồng hướng dẫn thành viên thay đổi.
- Nếu FS, README, schema, API spec, UI spec hoặc source không khớp nhau, không tự đoán rồi triển khai. Nêu rõ chỗ mâu thuẫn, xác định tài liệu nào cần thống nhất với nhóm, rồi cập nhật các tài liệu liên quan trong cùng thay đổi.
- Không triển khai một mục được ghi là ngoài phạm vi, chưa chốt hoặc chưa bật như thể đã được duyệt. Đặc biệt, portal/tài khoản học viên và thanh toán trực tuyến chỉ được đưa vào phạm vi sau khi nhóm chốt và cập nhật đồng bộ FS, schema, API và UI.

### Quy tắc API tổng hợp từ `specs/api.md`

- **Tình trạng đặc tả:** `specs/api.md` là thiết kế; đường dẫn/method/status được ghi là đề xuất chưa phải hợp đồng đã triển khai. Trước khi thêm endpoint, đối chiếu `specs/README.md`, README dự án, schema và API hiện có. Không tự tuyên bố một chức năng hoặc tích hợp đã chạy chỉ vì nó có trong tài liệu.
- **Ranh giới kiến trúc:** trình duyệt chỉ gọi API. Django xác thực danh tính, vai trò, quyền trên bản ghi và phạm vi site trước khi gọi SQL Server qua Site Router. Không để trình duyệt kết nối SQL Server, tự chọn database, hoặc gửi một site tùy ý để vượt quyền. Mỗi site có CSDL SQL Server riêng; không tạo database nghiệp vụ trung tâm, khóa ngoại xuyên site hay JOIN giữa hai CSDL.
- **Khai báo truy cập phân tán:** với mỗi endpoint ghi rõ kiểu nghiệp vụ, site được đọc/ghi, bảng được đọc/ghi, quyền cần thiết, ranh giới transaction và cách xử lý site lỗi. `LOCAL` chỉ dùng CSDL của site được xác thực; `GLOBAL` hỏi từng site hoạt động và gộp kết quả trong API; `REPLICATED-WRITE` dùng một chính sách đồng bộ chung cho các bảng được schema xác định là dùng chung; `DISTRIBUTED-TX` điều phối thao tác nhiều site và lưu tiến trình/phục hồi. Không rải logic chọn site hoặc ghi bản sao ở nhiều view/service.
- **Truy vấn toàn cục và nhân bản:** Global Query không lưu kết quả nghiệp vụ vào database tổng hợp. Nếu một site không phản hồi, trả trạng thái không đầy đủ cùng danh sách site thiếu; không âm thầm bỏ site và không báo thành công toàn phần. Với replicated write, báo kết quả một phần/thất bại nếu thiếu site bắt buộc, lưu trạng thái đồng bộ và cho phép retry/đối soát an toàn. Danh sách site lấy từ cấu hình và dữ liệu cơ sở đang hoạt động, không hard-code Q1/Q7/TD.
- **Phân quyền API:** Admin Big có phạm vi toàn hệ thống; Admin Small chỉ có site được phân công và được tạo đề nghị chuyển học viên, không tự duyệt/chuyển; giáo viên chỉ đọc/ghi lớp, buổi học, điểm danh và điểm được phân công. Quyền được xác định từ tài khoản đã xác thực ở server, không tin vai trò, ma_co_so, teacher_id hoặc student_id do client gửi. Học viên chưa có tài khoản/portal được duyệt trong schema hiện tại; không bật đăng ký, đăng nhập hay API học viên trước khi nhóm duyệt và cập nhật đồng bộ API, UI, README, schema.
- **Các luồng nghiệp vụ phải nhất quán với schema:** đăng ký khóa học kiểm tra học viên/lớp cùng site, trạng thái nhận học viên, sức chứa và đăng ký trùng; ghi DangKy, HocPhi, sức chứa lớp và nhật ký trong một transaction cục bộ. Xếp lớp kiểm tra lớp đích cùng site, sức chứa/lịch học rồi cập nhật đăng ký và số lượng liên quan nguyên tử trong site đó. Quản lý điểm kiểm tra giáo viên được phân công, thang điểm 0–10, loại điểm hợp lệ và quy tắc duy nhất; sửa điểm có lịch sử. Thống kê theo site chỉ tính bản đang học, tránh đếm bản đã chuyển và báo thiếu site khi Global Query chưa đủ dữ liệu. Mỗi thay đổi bảng phải được phản ánh trong docs/DATABASE_SCHEMA.md trước khi code phụ thuộc vào cột/bảng mới.
- **Chuyển cơ sở hai bước:** Admin Small tạo đề nghị tại site nguồn bằng danh tính/phạm vi của chính mình; kiểm tra học viên đang học ở nguồn, site đích hoạt động, không có đề nghị/giao dịch đang mở và điều kiện công nợ theo nghiệp vụ. Ghi đề nghị trạng thái chờ duyệt cùng sự kiện tại nguồn, chưa ghi hồ sơ đích. Admin Big xem hộp thư bằng Global Query và quyết định; quyết định phải được ghi tại nguồn. Chỉ đề nghị đã duyệt mới được Coordinator chạy chuyển dữ liệu phân tán. Lưu trạng thái tiến trình và sự kiện append-only; nếu chưa tạo hồ sơ đích thì giữ nguồn, nếu đích đã commit thì phục hồi tiến về phía trước và đánh dấu bản nguồn đã chuyển, giữ lịch sử. Không xóa bản nguồn và không tuyên bố ACID nguyên tử xuyên CSDL khi chưa cấu hình, kiểm thử.
- **SQL injection và validation:** ưu tiên Django ORM; nếu cần SQL thô phải dùng tham số. Không nối chuỗi từ request vào SQL. Tên cột, hướng sắp xếp, trường lọc động phải chọn từ allowlist; kiểm tra kiểu, độ dài, miền giá trị, quan hệ giữa trường và quyền sở hữu bản ghi ở server. Không dựa vào validation của form frontend. Kiểm thử payload SQL injection, dữ liệu sai kiểu, thiếu quyền, bản ghi thuộc site khác và cập nhật đồng thời.
- **Đăng nhập và thông tin nhạy cảm:** lưu mật khẩu bằng bcrypt qua cấu hình Django phù hợp; không lưu mật khẩu gốc. Bắt buộc HTTPS/TLS ở môi trường triển khai. Không ghi mật khẩu, hash mật khẩu, token, cookie, khóa ký, credential, dữ liệu thẻ hoặc nội dung nhạy cảm vào log, response lỗi, analytics, mã nguồn hay Git. Cookie phiên cần cấu hình HttpOnly, Secure, SameSite và CSRF phù hợp; không lưu token dài hạn hoặc mật khẩu trong localStorage. Mọi phiên đăng nhập phải hết hạn sau 3600 giây không có tương tác thật của người dùng; polling/request nền không làm mới hạn. API phải kiểm tra idle expiry và thu hồi phiên, frontend đồng bộ tab và đưa mọi role về đăng nhập. Trước khi code phải chốt session store có thể thu hồi tương thích CSDL site riêng; không dùng CSDL nghiệp vụ trung tâm hoặc default dummy.
- **Chống dò và spam form:** rate limit riêng cho IP và định danh đã chuẩn hóa; phản hồi đăng nhập/đăng ký/quên mật khẩu không tiết lộ tài khoản/email có tồn tại. Các ngưỡng trong specs là giá trị khởi đầu để cấu hình và kiểm thử, không phải cam kết bảo mật cố định: đăng nhập 10 yêu cầu/IP/phút và 5 lần sai theo cặp tài khoản+IP/15 phút; đăng ký 5 yêu cầu/IP/giờ và 3 yêu cầu/email/giờ; quên mật khẩu 10 yêu cầu/IP/giờ và 3 yêu cầu/email/giờ. Trả 429 kèm Retry-After; có thể tăng CAPTCHA sau ngưỡng. Tránh khóa tài khoản vĩnh viễn do người khác cố tình nhập sai.
- **Ảnh và tệp:** dữ liệu ảnh nhị phân nằm trên Cloudinary, không lưu trong source, thư mục media/upload của Django hoặc Git. Server tạo/kiểm tra quyền upload, chữ ký, site sở hữu, MIME thực tế, kích thước và giới hạn cần thiết; không cho nhập URL tùy ý để server tải xuống (SSRF). Lưu URL/public identifier và metadata tối thiểu tại CSDL site phù hợp; không lưu secret Cloudinary ở frontend. Schema hiện chưa có đủ metadata ảnh thì cập nhật schema trước khi triển khai luồng upload.
- **Ngày giờ:** nghiệp vụ dùng múi giờ `Asia/Ho_Chi_Minh` (UTC+07:00), giao diện giờ 24 tiếng. Ngày truyền theo YYYY-MM-DD; thời điểm có offset ISO/RFC3339. Server kiểm tra ngày kết thúc không trước ngày bắt đầu, khoảng giờ hợp lệ, lớp/buổi không trùng và mọi quy tắc lịch. Không dùng múi giờ mặc định của máy; kiểm thử qua nửa đêm và khi API chạy trên host cấu hình UTC.
- **Thanh toán học phí:** tiền và site do server lấy từ HocPhi tại site sở hữu hồ sơ, không tin số tiền/client site. Tạo lần thanh toán bền vững và khóa idempotency trước khi chuyển sang cổng; cùng key+cùng nội dung trả kết quả cũ, cùng key+nội dung khác trả xung đột. Reload hoặc quay lại chỉ đọc trạng thái đã lưu, không tạo lượt thu mới; redirect/query string không phải bằng chứng đã thanh toán. Webhook phải xác minh chữ ký, thời gian/replay, merchant, số tiền và loại tiền; xử lý trùng lặp an toàn; chỉ sau khi đã commit PhieuThu, cập nhật HocPhi và sự kiện thanh toán trong transaction cục bộ mới xác nhận thành công. Khi kết quả chưa rõ hoặc database lỗi, giữ trạng thái chờ đối soát, retry/đối soát trước khi cho thử lại. Hoàn tiền là bút toán bù trừ có tham chiếu phiếu gốc, không sửa/xóa lịch sử và không vượt số có thể hoàn. Không lưu PAN/CVV. Cổng thanh toán chưa được chốt; không mô tả thanh toán trực tuyến như đã tích hợp. Nếu thiếu bảng lần thanh toán/sự kiện/idempotency trong schema, phải thiết kế và cập nhật schema trước, tại site đang giữ HocPhi, không tạo database trung tâm.
- **Response và lỗi:** thống nhất định dạng thành công/lỗi và mã request để truy vết; response Global cần thể hiện complete và missing_sites. Phân biệt lỗi validation, chưa xác thực, không đủ quyền, không tìm thấy, xung đột/trùng lặp, giới hạn tốc độ và site tạm thời không sẵn sàng. Không trả SQL, stack trace, secret hay thông tin nội bộ. Lỗi phải nói rõ hành động nào có thể thử lại và hành động nào cần đối soát; không biến lỗi site thành danh sách rỗng hợp lệ.
- **Kiểm tra trước khi gọi endpoint hoàn tất:** chạy kiểm tra quyền theo từng role/site; CRUD đọc lại dữ liệu sau ghi; validation và SQL injection; transaction rollback; dữ liệu trùng/idempotency; site mất kết nối và kết quả Global thiếu; đồng bộ replicated-write; chuyển cơ sở trước/sau khi đích commit; múi giờ; ảnh sai loại/kích thước; giới hạn đăng nhập; thanh toán giả redirect, webhook sai chữ ký/phát lại, reload, timeout, callback lặp và lỗi DB. Ghi rõ lệnh/kịch bản, kết quả và điều chưa thử. Đo p50/p95 và thời gian phản hồi bằng ms trong môi trường được ghi lại; không tuyên bố đạt mục tiêu trong specs nếu chưa đo.

### Quy tắc giao diện tổng hợp từ `specs/ui-ux.md`

- **Nguồn yêu cầu và phạm vi:** `specs/ui-ux.md` mô tả cấu trúc và hành vi mong muốn, không có nghĩa mọi trang đã được code. Một frontend dùng chung, một cửa đăng nhập chung; sau khi API xác thực, giao diện hiển thị đúng workspace và route theo quyền. Không cho người dùng tự chọn role để nâng quyền. Portal/tài khoản học viên chưa được duyệt trong schema hiện tại; giữ ngoài phạm vi cho tới khi nhóm chốt và cập nhật API/schema/UI.
- **Sơ đồ theo vai trò:** khu vực công khai gồm trang chủ, danh sách/chi tiết khóa học, cơ sở và xác thực theo phạm vi đã duyệt. Admin Big cần màn hình tổng quan toàn hệ thống, cơ sở/site, tài khoản và Admin Small, giáo viên, hộp thư đề nghị chuyển, báo cáo toàn hệ thống. Admin Small chỉ có dashboard và màn hình học viên, đăng ký, xếp lớp, học phí/phiếu thu, điểm, đề nghị chuyển và báo cáo của cơ sở được giao; không có nút tự duyệt đề nghị. Giáo viên chỉ thấy lớp/buổi được phân công, lịch, điểm danh và nhập/quản lý điểm theo quyền. Trước khi thêm route, kiểm tra danh sách trang trong specs và gắn route với role, dữ liệu API, trạng thái rỗng/lỗi.
- **Tổ chức source:** app/router chỉ khai báo route và gọi page; trang chia component theo khu vực web/admin/shared, từng trang có các section nhỏ; section/page có SCSS Module riêng. Dùng shared components cho nút, input, trạng thái, dialog, bảng và layout khi có cùng hành vi. Giao diện gọi qua API/service layer; không truy vấn SQL, không nhúng dữ liệu nghiệp vụ cố định trong component. Tên/thư mục phải theo cấu trúc đã chốt trong specs, không tạo một trang khổng lồ hoặc copy-paste component cho từng role.
- **Nội dung và hình ảnh:** không tự bịa tên thương hiệu, địa chỉ, học phí, lịch khai giảng, số học viên, kết quả, đánh giá, chứng thực, khuyến mãi hoặc ảnh trung tâm. Chỉ dùng nội dung thật do nhóm cung cấp/duyệt và dữ liệu API; khi chưa có ảnh thật, dùng typography, khoảng trắng, bố cục và thành phần giao diện để tạo visual. Không dùng ảnh AI tạo để giả làm cơ sở/giáo viên/học viên thật, không chèn icon emoji trang trí và không dùng minh họa sai ngữ cảnh.
- **Màu sắc và kiểu chữ:** theo tối đa ba màu gốc trong specs, ưu tiên nền giấy dịu, chữ tối dễ đọc và một màu nhấn tiết chế; không tự thêm màu bão hòa, gradient hoặc hiệu ứng gây chói. Dùng sans-serif gọn như Inter/system sans-serif, phân cấp tiêu đề rõ, khoảng thở rộng và bố cục có nhịp; tránh dàn mọi nội dung thành lưới thẻ đều nhau. Ant Design dùng theo theme/token dự án để không lộ bảng màu mặc định lệch thiết kế. SCSS Modules là cách tạo style chính; Tailwind chỉ dùng utility ngắn khi có trong dự án, không lặp chuỗi class dài hoặc viết trùng CSS.
- **SVG và icon:** trước khi tạo icon/SVG, tìm file trong thư mục assets và kiểm tra barrel export/thư viện icon đang dùng. Nếu đã có thì import dùng lại. Nếu chưa có, ưu tiên icon phù hợp trong Ant Design; chỉ thêm SVG component mới khi cần, dùng currentColor, kích thước/viewBox rõ và nhãn trợ năng khi icon mang ý nghĩa. Lưu đúng thư mục icons đã quy định; không nhân bản icon cùng ý nghĩa hoặc tạo logo/hình ảnh thương hiệu giả.
- **Responsive:** mobile-first; bắt buộc kiểm tra 375 × 812, 768 × 1024, 1024 × 768 và 1440 × 900. Không tràn ngang trang, cắt chữ quan trọng hoặc che nút thao tác. Điều hướng/sidebar chuyển thành menu/drawer phù hợp; form xếp cột trên màn hình hẹp; nút đủ vùng chạm; bảng có vùng cuộn riêng hoặc cách trình bày thay thế và vẫn giữ tiêu đề/ngữ cảnh. Không chỉ đặt media query mà phải kiểm tra trạng thái thực tế ở các kích thước này.
- **Trạng thái tương tác:** nút/field/link có hover, active, focus-visible, disabled và loading phù hợp; loading chống gửi lặp nhưng giữ dữ liệu người dùng. Trang/list có empty state giải thích vì sao rỗng và bước tiếp theo; lỗi có nội dung có thể xử lý/thử lại; form chỉ rõ lỗi cạnh trường và tóm tắt lỗi khi cần. Kết quả GLOBAL phải phân biệt đầy đủ với thiếu site, có site lỗi và đang tải; không trình bày dữ liệu một phần như toàn hệ thống. Thêm transition/animation ngắn, phục vụ phản hồi thao tác, tôn trọng prefers-reduced-motion.
- **Form, ngày giờ và thanh toán:** frontend giúp nhập đúng nhưng API vẫn là nơi xác thực cuối cùng. Khi chọn ngày kết thúc, vô hiệu hóa ngày trước ngày bắt đầu và hiển thị giờ Việt Nam 24 tiếng. Màn hình đóng học phí phải cho thấy khoản nợ, số tiền, site, phương thức và trạng thái rõ ràng; khóa nút trong lúc gửi; giữ trạng thái sau reload; không xem redirect là bằng chứng thanh toán. Trạng thái chưa rõ cần hướng dẫn chờ/đối soát, không khuyến khích bấm thu lại. Không hiển thị trang học viên tự thanh toán cho tới khi tài khoản/portal và cổng thanh toán được duyệt.
- **Trợ năng:** dùng semantic HTML, label gắn với input, điều khiển được bằng bàn phím, focus nhìn thấy, thứ tự focus hợp lý, thông báo lỗi/loading cho screen reader, văn bản thay thế cho ảnh có ý nghĩa và tương phản đủ đọc. Không chỉ dùng màu để biểu thị trạng thái. Dialog/drawer phải quản lý focus và cho đóng bằng bàn phím theo hành vi phù hợp.
- **Tốc độ:** đo thay vì phỏng đoán. Mục tiêu Core Web Vitals trong specs là LCP không quá 2500 ms, INP không quá 200 ms, CLS không quá 0.1 ở p75; ghi thiết bị, viewport, mạng/môi trường và công cụ đo. Tối ưu kích thước ảnh theo viewport, lazy-load ảnh dưới màn hình đầu, không lazy-load nội dung hero nếu nó là LCP, tránh video/asset nặng không cần thiết và tách phần tải theo route khi phù hợp. Không ghi “tải dưới X ms” nếu chưa đo.
- **Chẩn đoán tải trang và dữ liệu:** trước khi sửa, phân biệt route Next.js biên dịch lần đầu trong `npm run dev`, thời gian render HTML/JavaScript, API/Django, truy vấn SQL từng site và truy vấn `GLOBAL`; không quy kết cho SQL Server nếu chưa đo. So sánh lần mở route đầu với lần mở lại và chỉ dùng `npm run build` + `npm run start` khi đánh giá bản production. Trang phải render layout và trạng thái loading/skeleton ngay, không chờ mọi request; request độc lập chạy song song, tránh gọi lặp và N+1; danh sách lớn phải lọc/phân trang tại API/SQL. Truy vấn `GLOBAL` chỉ hỏi site cần thiết qua Site Router; fan-out chỉ chạy song song có giới hạn/timeout khi driver và kết nối an toàn, đồng thời phải báo `complete`/`missing_sites` chính xác. Ghi thời gian bằng ms theo request và site, p50/p95 khi có nhiều lượt đo; không log bí mật hoặc dữ liệu nhạy cảm. Làm theo [README.md mục 12](README.md#12-tốc-độ-tải-trang-và-dữ-liệu).
- **Kiểm tra mỗi trang trước khi hoàn tất:** chạy lint, typecheck và build theo scripts hiện có; mở route trực tiếp và đi qua điều hướng; kiểm tra API/network, console, ảnh/icon/font/404; thử các viewport đã nêu, chuột, bàn phím, touch, reduced motion, trạng thái loading/empty/error/disabled và dữ liệu một phần; xác nhận role không thấy route/thao tác trái quyền. Đo hiệu năng và lưu bằng chứng/kết quả. Không kết luận responsive hoặc không có bug nếu chưa kiểm tra trên giao diện chạy thật.

### Đồng bộ tài liệu

Khi đổi yêu cầu giao diện/API, cập nhật `specs/ui-ux.md` và/hoặc `specs/api.md` cùng `README.md`, `docs/DATABASE_SCHEMA.md` và tài liệu triển khai liên quan trong cùng thay đổi. Nếu đặc tả mâu thuẫn về vai trò, trạng thái, quyền, site hoặc bảng, dừng việc tự suy diễn; chỉ rõ các tài liệu mâu thuẫn và thống nhất với nhóm trước khi triển khai.

## Trước khi viết code, tự trả lời 4 câu

1. Dữ liệu này thuộc loại nào: nhân bản, phân mảnh, dẫn xuất hay cục bộ? (xem `docs/DATABASE_SCHEMA.md` mục 2–3)
2. Nghiệp vụ này là `LOCAL`, `GLOBAL`, `REPLICATED-WRITE` hay `DISTRIBUTED-TX`? (xem `README.md` mục 5)
3. Truy vấn có đi qua Site Router không? Có vô tình đụng 2 cơ sở trong 1 câu lệnh không?
4. Đã kiểm tra quyền và ghi nhật ký chưa?

## Đọc tiếp

- `docs/QLTTNN-Yeu-Cau-Chung-Va-Kiem-Chung.md`: yêu cầu 2–4 site, năm nội dung chứng minh tối thiểu, đồng bộ dữ liệu, mã YC/TC và bằng chứng nghiệm thu
- `fs/README.md` và `fs/Functional-Specification.md`: phạm vi chức năng, vai trò, luồng nghiệp vụ, quy tắc lỗi và tiêu chí nghiệm thu
- `specs/README.md`: mục lục và cách giữ đặc tả API/UI đồng bộ
- `specs/api.md`: bảo mật, validation, phân quyền, các endpoint và nghiệp vụ thanh toán
- `specs/ui-ux.md`: vai trò, sơ đồ trang, cấu trúc component, thiết kế và kiểm tra responsive
- `README.md` mục 12: phân biệt độ trễ Next.js/API/SQL/site, hiện loading ngay, giữ nguyên ranh giới CSDL phân tán và quy trình đo hiệu năng
- `docs/DATABASE_SCHEMA.md`: các bảng, kiểu phân mảnh, ràng buộc phân tán (mục 4), dữ liệu mẫu
- `README.md`: kiến trúc, phân quyền, 14 luồng nghiệp vụ kèm ví dụ (có thêm / đóng cơ sở)
- `docs/QLTTNN-Lam-Viec-Nhom.md`: phân công, quy trình task, nhánh cá nhân và PR
- Đổi bảng hoặc luồng → cập nhật `README.md`, `docs/DATABASE_SCHEMA.md` và tài liệu con liên quan trong cùng PR; nhờ Quốc Hiếu review và merge theo quy trình Git ở trên
- Đổi yêu cầu hoặc hành vi chức năng → cập nhật `fs/Functional-Specification.md`; nếu thay đổi liên quan tới bảng hoặc luồng thì vẫn cập nhật đồng thời các tài liệu theo quy tắc phía trên.
