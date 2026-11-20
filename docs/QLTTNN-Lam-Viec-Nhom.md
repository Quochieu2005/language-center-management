# Làm việc nhóm và kế hoạch triển khai

**Tra nhanh:** [Phân công](#2-phân-công-theo-năm-luồng-công-việc) · [Sở hữu tài liệu](#4-quyền-sở-hữu-tài-liệu-và-tránh-xung-đột) · [Quy trình Git/PR](#5-nhịp-làm-việc-và-tích-hợp) · [Kế hoạch triển khai/demo](#ke-hoach-trien-khai). Tổng quan dự án xem [README gốc](../README.md).

Ưu tiên lab/báo cáo theo [đối chiếu giảng viên](QLTTNN-De-Cuong-Bao-Cao.md#tai-lieu-giang-vien): hoàn tất ba instance/máy (Q1 Quốc Hiếu, Q7 Minh Khôi, TD Minh Đức), lưu ánh xạ/cấp phát và bằng chứng TC. TD hiện vẫn cùng Windows Q1; phân công là mục tiêu, không phải kết quả đã chạy. Không đổi toàn bộ cơ chế sang ví dụ QLDSV/hàng không hoặc tự triển khai 2PC khi chưa chốt.

Tài liệu này gom quy trình phối hợp và kế hoạch triển khai, giúp năm thành viên phối hợp làm một hệ thống có nhiều CSDL và nhiều phần code. Nó bổ sung cách làm việc cho [README chính](../README.md); không thay đổi nghiệp vụ hoặc quyết định kỹ thuật trong README và [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md).

## 1. Nguyên tắc cả nhóm cùng nắm

- Đọc README mục 1–4 và schema mục 1–4 trước khi nhận task.
- Đọc [yêu cầu chung và kiểm chứng](QLTTNN-Yeu-Cau-Chung-Va-Kiem-Chung.md): 2–4 site (nhóm dùng 3), tối thiểu một phương pháp phân mảnh, một phương pháp replication, một distributed transaction, một tình huống concurrency, một distributed query và đồng bộ. Các nhóm có thể chọn kiểu phân mảnh khác nhau; các nội dung chứng minh đều bắt buộc.
- Mỗi task phải ghi rõ loại `LOCAL`, `GLOBAL`, `REPLICATED-WRITE` hay `DISTRIBUTED-TX`.
- Mỗi người sở hữu module của mình, nhưng các interface dùng chung được thống nhất trước khi code song song.
- Dùng stack đã chốt trong README mục 9: Next.js frontend, Django API và SQL Server; không tự đổi công nghệ nếu chưa thống nhất cả nhóm.
- Không để nhiều người sửa cùng lúc README hoặc schema mà chưa báo nhau.
- Việc chạy thành công ở một DB không chứng minh hành vi phân tán đã đúng; phải thử các site độc lập và tình huống mất kết nối.

## 2. Phân công theo năm luồng công việc

Nhóm gán tên thật vào các vai trò dưới đây. Đây là đề xuất theo phạm vi, có thể đổi theo năng lực; người điều phối tích hợp không đồng nghĩa tự quyết các điểm đang mở.

| Vai trò | Phạm vi chính | Phối hợp bắt buộc |
|---|---|---|
| A. Database và môi trường | Schema, tạo các CSDL, dữ liệu demo theo site, cấu hình kết nối DB, script triển khai và ảnh cài đặt | Cùng B định nghĩa kết nối; cùng C kiểm tra bảng nhân bản; cùng D/E kiểm tra bảng nghiệp vụ |
| B. Coordinator và tích hợp | Site Router, phát hiện site hoạt động, Global Query, chuẩn hóa lỗi site, build/run tích hợp | Cùng A chốt cấu hình; cùng C làm replicated-write; cùng E thống nhất dữ liệu báo cáo |
| C. Tài khoản và dữ liệu dùng chung | Đăng nhập, quyền, tài khoản, môn/khóa học/cơ sở, đồng bộ replicated-write | Cùng B định nghĩa giao diện đồng bộ; cùng A xác nhận mọi site có bản giống nhau |
| D. Học viên và nghiệp vụ cơ sở | Hồ sơ, lớp, đăng ký/đổi lớp, học phí/phiếu thu, quy tắc cùng site | Cùng A xác nhận FK cục bộ; cùng B dùng đúng router; cùng E đối chiếu điểm danh |
| E. Học tập, báo cáo và demo | Buổi học, điểm danh, điểm, thống kê, nhật ký màn hình và kịch bản demo | Cùng D thống nhất đăng ký/buổi học; cùng B gộp thống kê; cùng cả nhóm kiểm tra quyền |

Chuyển cơ sở là công việc liên chức năng: B làm điều phối; A xác định lưu trạng thái và ràng buộc DB; D bảo đảm trạng thái học viên/lớp; C kiểm tra chỉ Tư vấn tạo đề nghị, Admin Big hoặc Admin Small tại site nhận duyệt/từ chối đúng phạm vi; E kiểm tra hộp thư Global Query, thông báo site nhận, giữ tài khoản, nhật ký, lịch sử và thống kê sau chuyển. Cả nhóm có thể review kịch bản lỗi; Pull Request vẫn phải được trưởng nhóm Quốc Hiếu kiểm tra và merge theo quy trình ở mục 5.

Mỗi vai trò chịu trách nhiệm phần giao diện của domain mình nếu có giao diện. Không dồn toàn bộ frontend vào một người ở cuối dự án.

### Phân công minh chứng yêu cầu chung

| Yêu cầu/kịch bản | Đầu mối | Phối hợp và đầu ra |
|---|---|---|
| YC-01/YC-02 — TC-SITE-01, TC-FRAG-01 | A | B/D xác nhận kết nối, mảnh ngang/dẫn xuất, đối chiếu tập dữ liệu và tái thiết |
| YC-03/YC-07 — TC-REP-01, TC-SYNC-01 | C | A/B triển khai phương pháp replication và phục hồi; lưu dữ liệu/phiên bản từng site |
| YC-04 — TC-DTX-01 | B | A/D xác nhận trạng thái nguồn/đích và recovery; C kiểm tra quyền; E lưu kịch bản lỗi |
| YC-05 — TC-CON-01 | D | A/B chốt cơ chế cạnh tranh; E chạy hai phiên tranh chỗ cuối và đối chiếu dữ liệu |
| YC-06 — TC-DQ-01 | E | B/A đối chiếu kết quả cục bộ, tổng API và trường hợp site lỗi |

Nhóm điền người thực hiện và người review vào task, kèm mã YC/TC và nơi lưu kết quả. Quốc Hiếu kiểm tra trước khi ghi đạt; chưa có bằng chứng thì ghi “Chưa kiểm chứng”. Phân công này không thay đổi quyền review/merge Git ở mục 5.

## 3. Hợp đồng trước khi chia task song song

Trước khi hai người cùng tích hợp một nghiệp vụ, viết một bản hợp đồng ngắn trong task/PR:

```text
Tên chức năng:
Người được phép:
Kiểu nghiệp vụ: LOCAL / GLOBAL / REPLICATED-WRITE / DISTRIBUTED-TX
Site nguồn/đích hoặc tập site:
Bảng đọc/ghi:
Đầu vào và đầu ra:
Các lỗi nghiệp vụ:
Hành vi khi site timeout/lỗi:
Ranh giới commit/rollback:
Nhật ký cần ghi:
Người implement / người review:
```

Nếu chưa trả lời được ranh giới commit/rollback hoặc site tham gia, task chưa sẵn sàng để code. Hỏi cả nhóm và cập nhật README/schema khi đó là quyết định thiết kế mới.

## 4. Quyền sở hữu tài liệu và tránh xung đột

| Tài liệu | Người cập nhật chính | Khi nào cập nhật |
|---|---|---|
| `README.md` | B điều phối thay đổi; người làm nghiệp vụ gửi patch/nội dung | Đổi luồng, quyền, loại thao tác, tiến độ hoặc quyết định đã chốt |
| `docs/DATABASE_SCHEMA.md` | A | Đổi bảng, cột, khóa, trạng thái, quan hệ hoặc phân mảnh |
| `docs/QLTTNN-Huong-Dan-Source.md` | B | Khi module/interface hoặc quy tắc truy cập thay đổi |
| `docs/QLTTNN-Giao-Dich-Phan-Tan.md` | B + A | Khi chốt giao thức commit, trạng thái hoặc recovery |
| `docs/QLTTNN-Yeu-Cau-Chung-Va-Kiem-Chung.md` | B + A/E và người làm kịch bản | Khi tiêu chí, phương pháp kiểm chứng hoặc bằng chứng thay đổi |
| `docs/QLTTNN-Lam-Viec-Nhom.md` | Cả nhóm thống nhất | Khi thay đổi người sở hữu hoặc quy tắc phối hợp |

README và schema là nguồn chuẩn. Tài liệu con không được âm thầm đưa ra chính sách khác. Trong PR đổi schema/nghiệp vụ, sửa file chuẩn và tài liệu con liên quan trong cùng PR.

## 5. Nhịp làm việc và tích hợp

1. **Chọn task:** lấy một luồng từ README mục 10; nêu loại thao tác, site, bảng và quyền.
2. **Chốt hợp đồng:** thống nhất chữ ký service/repository và cấu trúc kết quả/lỗi trước khi hai domain tích hợp.
3. **Cập nhật nhánh gốc:** lấy thay đổi mới nhất từ `Dev`; mỗi thành viên dùng một nhánh cá nhân mang tên mình, ví dụ `qhiu` hoặc `nguyen-van-a`. Không thêm tiền tố `feature/`; không dùng `main` làm nhánh làm việc.
4. **Làm trên nhánh cá nhân:** commit thay đổi vào nhánh mang tên mình. Không commit hoặc push trực tiếp lên `Dev` hay `main`; không merge nhánh cá nhân trực tiếp vào `Dev`.
5. **Kiểm tra trước PR:** chạy các kiểm tra phù hợp, thử luồng trên các CSDL riêng khi cần, kiểm tra log và cập nhật README/schema/tài liệu con liên quan.
6. **Mở Pull Request:** tạo PR từ nhánh cá nhân vào `Dev`, không nhắm vào `main`. Điền đầy đủ `Add a title` và `Add a description` theo mẫu ở mục 5.1. Yêu cầu trưởng nhóm **Quốc Hiếu** review.
7. **Sửa theo review:** tác giả cập nhật nhánh cá nhân và push commit bổ sung lên đúng nhánh đó. Mỗi lần có code mới, cập nhật description của PR để mô tả toàn bộ diff hiện tại, gồm cả thay đổi cũ lẫn mới. Không tự approve hoặc merge PR của mình; không tự merge vào `Dev`.
8. **Merge và đóng task:** chỉ Quốc Hiếu, sau khi kiểm tra PR, mới merge vào `Dev`. Nếu chưa xác định được tài khoản reviewer hoặc không mở được PR, giữ thay đổi trên nhánh cá nhân và báo Quốc Hiếu; không thay `main` cho `Dev`.
9. **Demo định kỳ:** dùng kịch bản ở README mục 6; ghi lại lỗi và người theo dõi thay vì để tới cuối kỳ.

### 5.1. Tiêu chuẩn title và description của Pull Request

Title phải nêu loại thay đổi, phạm vi và kết quả, không dùng các tiêu đề mơ hồ như `update`, `fix`, `changes` hoặc chỉ ghi số PR. Mẫu:

```text
<loại>(<phạm-vi>): <thay đổi và kết quả>
```

Ví dụ:

```text
feat(enrollment): đăng ký học viên vào lớp tại đúng cơ sở
```

Description phải giúp người review hiểu toàn bộ thay đổi mà không phải đoán. Liệt kê theo chức năng/luồng và file hoặc module liên quan; nêu hành vi trước/sau, loại nghiệp vụ phân tán, site và bảng đọc/ghi, quyền/API/UI bị ảnh hưởng, kiểm tra đã chạy và kết quả, tài liệu/schema/migration đã cập nhật, cùng rủi ro hoặc điểm còn mở. Mục không áp dụng phải ghi `Không áp dụng`.

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

Ví dụ: nếu PR #1 đã được mở/push và sau đó tác giả push thêm commit vào cùng PR, phải sửa description của PR #1 để vẫn mô tả tất cả thay đổi trong PR #1, không chỉ phần mới push. Khi mở PR #2, điền title và description mới cho toàn bộ thay đổi của PR #2; không trông chờ người review đọc mô tả PR #1. Nếu phạm vi một PR thay đổi đáng kể, cập nhật cả title. Không yêu cầu Quốc Hiếu merge cho đến khi title và description đầy đủ, khớp với diff hiện tại.

## 6. Checklist khi nhận task

- [ ] Đã đọc luồng tương ứng trong README và bảng liên quan trong schema.
- [ ] Đã xác định vai trò người gọi và site đọc/ghi.
- [ ] Đã phân loại `LOCAL/GLOBAL/REPLICATED-WRITE/DISTRIBUTED-TX`.
- [ ] Đã ghi rõ thành công, rollback, timeout và retry.
- [ ] Đã thống nhất ai sửa file nào để tránh đụng nhau.
- [ ] Đã gắn YC/TC liên quan và xác định dữ liệu ban đầu, cách chạy, điều kiện đạt; không ghi “không áp dụng” cho yêu cầu chung bắt buộc của toàn đồ án.

## 7. Checklist trước khi merge

- [ ] Thay đổi nằm trên nhánh cá nhân mang tên thành viên, tạo từ `Dev`; không có commit/push trực tiếp lên `Dev` hoặc `main`.
- [ ] PR nhắm vào `Dev`, có mô tả và bằng chứng kiểm tra; đã yêu cầu Quốc Hiếu review.
- [ ] `Add a title` nêu rõ loại, phạm vi và kết quả; `Add a description` bao quát toàn bộ diff hiện tại.
- [ ] Mỗi lần push thêm code vào PR, description đã được cập nhật; PR mới có description riêng.
- [ ] Tác giả không tự approve hoặc merge; Quốc Hiếu đã review và là người merge. Review bổ sung không thay bước này.
- [ ] Chỉ ghi đúng các site; không dùng kết nối mặc định.
- [ ] Không join hoặc đặt FK xuyên CSDL; không hard-code danh sách site.
- [ ] Quyền được kiểm tra phía backend; nhật ký ghi đúng, không có bí mật.
- [ ] Với GLOBAL, kết quả thiếu site được đánh dấu chưa đầy đủ.
- [ ] Với dữ liệu dùng chung/chuyển cơ sở, đã thử lỗi giữa chừng và đường phục hồi.
- [ ] README/schema/docs khớp với source đã merge.
- [ ] Với phần phân tán liên quan, FS/API/UI và mã YC/TC khớp nhau; bằng chứng thể hiện thao tác thật trên các site hoặc hai phiên cạnh tranh, không chỉ mock/seed.


---

<a id="ke-hoach-trien-khai"></a>

## 8. Kế hoạch triển khai và tiêu chí hoàn tất

Các giai đoạn dưới đây là kế hoạch, không thay [trạng thái đã kiểm chứng](Trang-Thai-Trien-Khai.md). Chốt các quyết định còn mở tại README mục 9 trước phần code phụ thuộc; tiêu chí hoàn tất task và PR ở mục 6–7 của tài liệu này.

### 8.1. Các giai đoạn và đầu ra

| Giai đoạn | Công việc | Bằng chứng/đầu ra để chuyển bước |
|---|---|---|
| A. Chốt cấu hình triển khai | Ghi phiên bản/cấu hình SQL Server, cách đặt từng site, cấu hình Django và quy trình chạy Next.js/Django | Quyết định được ghi, mọi thành viên có thể dựng cùng môi trường |
| B. CSDL | Tạo các CSDL riêng; chạy cùng schema; tạo dữ liệu demo khác nhau theo site và seed danh mục ban đầu | TC-SITE-01/TC-FRAG-01: kết nối riêng và phân mảnh đúng; seed chưa chứng minh replication runtime |
| C. Django Coordinator API | Site Router, danh sách cơ sở hoạt động, Global Query, logging và nền giao dịch | Không hard-code số site; truy vấn biết nguồn; site mất kết nối được báo rõ |
| D. Quyền và dữ liệu dùng chung | Đăng nhập, phân quyền, tài khoản, quên mật khẩu, danh mục, phương pháp replication và đồng bộ | TC-REP-01/TC-SYNC-01: truyền thay đổi thật, đối soát sau lỗi; không báo hoàn tất khi thiếu site |
| E. Nghiệp vụ cơ sở | Mở lớp, sinh lịch, đăng ký, đổi lớp, học phí, điểm danh, điểm; kiểm soát concurrency | Rollback cùng site; TC-CON-01: hai phiên tranh chỗ cuối chỉ một yêu cầu thắng |
| F. Nghiệp vụ toàn cục | Thống kê, tra cứu học viên, nhật ký nhiều site | Kết quả gộp; cảnh báo site thiếu; không đếm `da_chuyen_di` |
| G. Chuyển cơ sở | Đề nghị Tư vấn, duyệt/từ chối của Admin Big hoặc Admin Small tại cơ sở nhận, Global Query, transaction, retry và phục hồi | Chứng minh chỉ Tư vấn tạo đề nghị, chờ duyệt, từ chối, đúng phạm vi người duyệt; giữ nguyên tài khoản, thông báo tại đích; lỗi trước khi tạo đích và restart sau khi tạo đích |
| H. Hoàn thiện | Giao diện, kiểm thử tích hợp, demo, ảnh cài đặt, báo cáo và slide | Kịch bản demo có thể chạy lại từ đầu; tài liệu khớp source thực tế |

Đây là nhóm giai đoạn để quản lý tích hợp; danh sách chức năng theo thứ tự chi tiết vẫn là README mục 10.

### 8.2. Ma trận kiểm chứng theo loại nghiệp vụ

| Loại | Kịch bản thành công | Kịch bản lỗi bắt buộc | Điều kiện đạt |
|---|---|---|---|
| `LOCAL` | Đăng ký ở Q1 tạo đăng ký, học phí, tăng sĩ số, ghi log | Ép lỗi ở từng bước sau khi bắt đầu giao dịch | Rollback toàn bộ; chỉ Q1 thay đổi khi thành công |
| `GLOBAL` | Đếm học viên tại từng site rồi cộng | Một site timeout | Hiện phần có được, nêu site thiếu và đánh dấu chưa đầy đủ |
| `REPLICATED-WRITE` | Sửa khóa học khi mọi site hoạt động | Một site không kết nối hoặc lỗi giữa chừng | Từ chối trước khi bắt đầu nếu site không sẵn sàng; nếu lỗi giữa chừng có recovery, không để lệch âm thầm |
| `DISTRIBUTED-TX` | Chuyển học viên hết nợ từ Q1 sang Q7 | Q7 không sẵn sàng trước khi tạo hồ sơ đích; tiến trình dừng sau khi đích tạo xong | Nhánh đầu không đổi Q1; nhánh sau resume phần nguồn; chỉ một bản được tính là đang học sau recovery |
| Concurrency (`LOCAL`, YC-05) | Hai học viên khác nhau tranh chỗ cuối của cùng lớp | Hai phiên chạy chồng lấp tại vùng kiểm tra/cập nhật sức chứa | Đúng một yêu cầu thành công; không vượt sĩ số, không có đăng ký/học phí dở dang; ghi cơ chế và bằng chứng cạnh tranh |

### 8.3. Kịch bản demo bảo vệ

Theo bảng README mục 6, chạy đủ các kịch bản nghiệp vụ, gồm 21 kịch bản hiện được liệt kê: phân mảnh; nghiệp vụ cục bộ; quyền; thống kê; nhân bản; đề nghị/duyệt/chuyển và phục hồi; tài khoản; nhật ký; thêm site BT; cạnh tranh chỗ cuối; đồng bộ sau lỗi; tái thiết mảnh và thống kê thiếu site. Đồng thời đối chiếu đủ **TC-SITE-01, TC-FRAG-01, TC-REP-01, TC-DTX-01, TC-CON-01, TC-DQ-01, TC-SYNC-01**. Không thay bài concurrency bằng hai yêu cầu tuần tự hoặc bài replication bằng seed giống nhau. Dùng dữ liệu mẫu của [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md), không sửa cứng dữ liệu demo vào ứng dụng.

### 8.4. Bằng chứng cài đặt

Theo đúng hướng dẫn giảng viên, lưu ảnh/script chứng minh cấu hình mạng hoặc VPN/Remote Desktop, kết nối server, cài SQL Server và quản trị bằng SSMS, kiểm tra Agent nếu áp dụng, Linked Server/Publication nếu được yêu cầu, truy vấn trước/sau đồng bộ và giao dịch thử. Ghi phiên bản Next.js/Django và cách API kết nối từng CSDL. Bảng mã ảnh và nội dung cần chụp theo từng mục 3.1–3.7 nằm trong [đề cương báo cáo](QLTTNN-De-Cuong-Bao-Cao.md). Tài liệu này không khẳng định bước nào đã cài xong; ghi nhận theo trạng thái thực tế.

Ngoài ảnh cấu hình công cụ, **bắt buộc** lưu bằng chứng phương pháp replication đang truyền thay đổi, distributed transaction hai site, concurrency hai phiên, distributed query và phân mảnh. Đồng bộ phải có lỗi/phục hồi. Việc một công cụ cụ thể không được chọn không cho phép bỏ bằng chứng kỹ thuật tương ứng. Dùng mẫu ghi kết quả ở tài liệu YC/TC; chưa chạy thì ghi “Chưa kiểm chứng”.
