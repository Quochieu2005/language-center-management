# Quy trình làm việc nhóm

Tài liệu này giúp năm thành viên phối hợp làm một hệ thống có nhiều CSDL và nhiều phần code. Nó bổ sung cách làm việc cho [README chính](../README.md); không thay đổi nghiệp vụ hoặc quyết định kỹ thuật trong README và [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md).

## 1. Nguyên tắc cả nhóm cùng nắm

- Đọc README mục 1–4 và schema mục 1–4 trước khi nhận task.
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

Chuyển cơ sở là công việc liên chức năng: B làm điều phối; A xác định lưu trạng thái và ràng buộc DB; D bảo đảm trạng thái học viên/lớp; C kiểm tra Admin Small chỉ tạo đề nghị còn Admin Big mới duyệt/từ chối; E kiểm tra hộp thư Global Query, nhật ký, lịch sử và thống kê sau chuyển. Cả nhóm có thể review kịch bản lỗi; Pull Request vẫn phải được trưởng nhóm Quốc Hiếu kiểm tra và merge theo quy trình ở mục 5.

Mỗi vai trò chịu trách nhiệm phần giao diện của domain mình nếu có giao diện. Không dồn toàn bộ frontend vào một người ở cuối dự án.

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
| `docs/QLTTNN-Kien-Truc.md` | B | Đổi thành phần hoặc định tuyến đã thống nhất |
| `docs/QLTTNN-Du-Lieu.md` | A | Khi thay đổi phân mảnh/quan hệ ở schema |
| `docs/QLTTNN-Huong-Dan-Source.md` | B | Khi module/interface hoặc quy tắc truy cập thay đổi |
| `docs/QLTTNN-Giao-Dich-Phan-Tan.md` | B + A | Khi chốt giao thức commit, trạng thái hoặc recovery |
| `docs/QLTTNN-Ke-Hoach-Trien-Khai.md` | Người tích hợp | Khi thứ tự/gate hoặc demo thay đổi |
| `docs/QLTTNN-Lam-Viec-Nhom.md` | Cả nhóm thống nhất | Khi thay đổi người sở hữu hoặc quy tắc phối hợp |

README và schema là nguồn chuẩn. Tài liệu con không được âm thầm đưa ra chính sách khác. Trong PR đổi schema/nghiệp vụ, sửa file chuẩn và tài liệu con liên quan trong cùng PR.

## 5. Nhịp làm việc và tích hợp

1. **Chọn task:** lấy một luồng từ README mục 10; nêu loại thao tác, site, bảng và quyền.
2. **Chốt hợp đồng:** thống nhất chữ ký service/repository và cấu trúc kết quả/lỗi trước khi hai domain tích hợp.
3. **Cập nhật nhánh gốc:** lấy thay đổi mới nhất từ `dev`; tạo nhánh riêng theo mẫu `feature/<ten-thanh-vien>/<mo-ta-ngan>`. Không dùng `main` làm nhánh làm việc.
4. **Làm trên nhánh cá nhân:** commit thay đổi vào nhánh của mình. Không commit hoặc push trực tiếp lên `dev` hay `main`; không merge nhánh cá nhân vào `dev`.
5. **Kiểm tra trước PR:** chạy các kiểm tra phù hợp, thử luồng trên các CSDL riêng khi cần, kiểm tra log và cập nhật README/schema/tài liệu con liên quan.
6. **Mở Pull Request:** tạo PR từ nhánh cá nhân vào `dev`, không nhắm vào `main`. Điền đầy đủ `Add a title` và `Add a description` theo mẫu ở mục 5.1. Yêu cầu trưởng nhóm **Quốc Hiếu** review.
7. **Sửa theo review:** tác giả cập nhật nhánh cá nhân và push commit bổ sung lên đúng nhánh đó. Mỗi lần có code mới, cập nhật description của PR để mô tả toàn bộ diff hiện tại, gồm cả thay đổi cũ lẫn mới. Không tự approve hoặc merge PR của mình; không tự merge vào `dev`.
8. **Merge và đóng task:** chỉ Quốc Hiếu, sau khi kiểm tra PR, mới merge vào `dev`. Nếu chưa xác định được tài khoản reviewer hoặc không mở được PR, giữ thay đổi trên nhánh cá nhân và báo Quốc Hiếu; không thay `main` cho `dev`.
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

## 7. Checklist trước khi merge

- [ ] Thay đổi nằm trên nhánh cá nhân tạo từ `dev`; không có commit/push trực tiếp lên `dev` hoặc `main`.
- [ ] PR nhắm vào `dev`, có mô tả và bằng chứng kiểm tra; đã yêu cầu Quốc Hiếu review.
- [ ] `Add a title` nêu rõ loại, phạm vi và kết quả; `Add a description` bao quát toàn bộ diff hiện tại.
- [ ] Mỗi lần push thêm code vào PR, description đã được cập nhật; PR mới có description riêng.
- [ ] Tác giả không tự approve hoặc merge; Quốc Hiếu đã review và là người merge. Review bổ sung không thay bước này.
- [ ] Chỉ ghi đúng các site; không dùng kết nối mặc định.
- [ ] Không join hoặc đặt FK xuyên CSDL; không hard-code danh sách site.
- [ ] Quyền được kiểm tra phía backend; nhật ký ghi đúng, không có bí mật.
- [ ] Với GLOBAL, kết quả thiếu site được đánh dấu chưa đầy đủ.
- [ ] Với dữ liệu dùng chung/chuyển cơ sở, đã thử lỗi giữa chừng và đường phục hồi.
- [ ] README/schema/docs khớp với source đã merge.
