
# Đặc tả API

> Trạng thái: Bản thiết kế đề xuất — các method/path trong file phải được nhóm thống nhất trước khi xem là hợp đồng cuối cùng.

File này mô tả giao diện gọi API thế nào và API phải xử lý quyền, site, dữ liệu cùng lỗi ra sao. Yêu cầu màn hình nằm ở [`ui-ux.md`](ui-ux.md); luồng nghiệp vụ chuẩn nằm trong [`README.md`](../README.md); định nghĩa bảng nằm trong [`docs/DATABASE_SCHEMA.md`](../docs/DATABASE_SCHEMA.md).

## Quy tắc bắt buộc

1. Giao diện chỉ gọi API. API xác thực tài khoản, kiểm tra vai trò/phạm vi, kiểm tra dữ liệu nghiệp vụ rồi mới truy cập CSDL qua Site Router.
2. Mỗi cơ sở dùng một CSDL SQL Server riêng và một kết nối riêng. Không dùng CSDL nghiệp vụ trung tâm; không JOIN hoặc tạo khóa ngoại xuyên site.
3. Mỗi endpoint phải được gắn một kiểu: `LOCAL`, `GLOBAL`, `REPLICATED-WRITE` hoặc `DISTRIBUTED-TX`. Nếu endpoint có nhiều chặng, ghi kiểu cho từng chặng.
4. API tự xác định site từ danh tính đã xác thực, bản ghi hiện hành hoặc danh sách site đang `hoat_dong`. Không tin `ma_co_so_nguon` do trình duyệt gửi lên nếu nguồn phải lấy từ tài khoản.
5. `GLOBAL` truy vấn riêng các CSDL site trong phạm vi quyền và tổng hợp ở tầng API. Response phải chỉ rõ dữ liệu có đầy đủ không; site lỗi không được âm thầm bỏ qua.
6. `REPLICATED-WRITE` ghi theo một chính sách thống nhất tới mọi site hoạt động cần tham gia. Không trả thành công toàn phần nếu có site bắt buộc chưa được cập nhật.
7. Hai CSDL riêng không tạo thành một transaction ACID nguyên tử xuyên site. Với `DISTRIBUTED-TX`, API lưu tiến trình, có thể retry/phục hồi và trả trạng thái giao dịch rõ ràng.
8. Mọi ghi cần bảo vệ khỏi dữ liệu sai, quyền không hợp lệ, gửi trùng và cập nhật đồng thời. Không ghi mật khẩu, token hoặc thông tin kết nối vào log hay response.

## Quy ước response và lỗi — đề xuất

Nhóm nên thống nhất một cấu trúc response dùng chung. Mẫu dưới đây là đề xuất, chưa phải định dạng đã triển khai:

```json
{
  "data": {},
  "meta": {
    "request_id": "...",
    "complete": true,
    "missing_sites": []
  }
}
```

Với lỗi:

```json
{
  "error": {
    "code": "BUSINESS_RULE_VIOLATION",
    "message": "Yêu cầu không thể thực hiện.",
    "details": {},
    "request_id": "..."
  }
}
```

Các response `GLOBAL` cần có dấu hiệu đầy đủ/không đầy đủ. Nếu một site lỗi, ví dụ `complete: false` và `missing_sites: ["Q7"]`; giao diện phải cảnh báo người dùng. Không biến lỗi site thành danh sách rỗng không phân biệt với “không có dữ liệu”.

| HTTP status đề xuất | Dùng cho |
|---|---|
| `200` | Đọc hoặc cập nhật thành công và có kết quả |
| `201` | Tạo bản ghi nghiệp vụ thành công |
| `202` | Chấp nhận yêu cầu bất đồng bộ; giao dịch còn đang xử lý |
| `400` / `422` | Request sai định dạng hoặc không qua kiểm tra nghiệp vụ |
| `401` | Chưa xác thực hoặc thông tin xác thực không hợp lệ |
| `403` | Đã xác thực nhưng không có quyền/phạm vi phù hợp |
| `404` | Không tìm thấy tài nguyên trong phạm vi được phép |
| `409` | Xung đột trạng thái, gửi trùng hoặc dữ liệu đã thay đổi |
| `503` | Site bắt buộc không khả dụng nên nghiệp vụ không thể hoàn tất |

Mã lỗi chính xác và cách biểu diễn response khi `GLOBAL` chỉ lấy được một phần phải được chốt cùng nhóm; nội dung trên là quy ước đề nghị để bắt đầu thiết kế.

## Danh mục endpoint đề xuất cho sáu nghiệp vụ

Các path dưới đây là **bản nháp để thảo luận**, chưa khẳng định đã có trong source. Cần giữ nhất quán giữa API, giao diện và kiểm thử sau khi nhóm chốt.

| Nghiệp vụ | Endpoint đề xuất | Vai trò | Kiểu phân tán | Site và bảng chính |
|---|---|---|---|---|
| Đăng ký khóa học | `POST /api/v1/enrollments` | Admin Small, lễ tân | `LOCAL` | Site học viên/lớp; đọc `HocVien`, `LopHoc`; ghi `DangKy`, `HocPhi`, cập nhật sĩ số `LopHoc` |
| Xếp/đổi lớp | `PATCH /api/v1/enrollments/{ma_dang_ky}/class` | Admin Small, lễ tân | `LOCAL` | Site của đăng ký; đọc lớp và sĩ số; cập nhật `DangKy`, sĩ số hai lớp |
| Thu/hoàn học phí | `POST /api/v1/tuition-receipts` | Kế toán; Admin Small theo quyền | `LOCAL` | Site chứa `HocPhi`; ghi `PhieuThu`, cập nhật số đã thu/trạng thái `HocPhi` |
| Quản lý điểm | `PUT /api/v1/enrollments/{ma_dang_ky}/grades/{loai_diem}` | Giáo viên được phân công; quản lý theo quyền | `LOCAL` | Site của lớp/đăng ký; đọc phân công và đăng ký; ghi `Diem`, nhật ký chỉnh sửa |
| Tạo đề nghị chuyển | `POST /api/v1/transfers` | Admin Small | `LOCAL` | Nguồn lấy từ tài khoản; ghi `GiaoDichChuyenCoSo`, thêm `LichSuChuyenCoSo`; chưa ghi site đích |
| Hộp thư đề nghị | `GET /api/v1/transfers/inbox` | Admin Big | `GLOBAL` | Đọc riêng các site đang hoạt động; gộp kết quả trong API; trả trạng thái đầy đủ/thiếu site |
| Duyệt đề nghị | `POST /api/v1/transfers/{ma_chuyen}/approve` | Admin Big | `LOCAL` ghi quyết định, rồi `DISTRIBUTED-TX` | Quyết định ghi tại nguồn; Coordinator mới phối hợp nguồn/đích sau khi duyệt |
| Từ chối đề nghị | `POST /api/v1/transfers/{ma_chuyen}/reject` | Admin Big | `LOCAL` | Ghi `tu_choi`, người duyệt, thời điểm, lý do và sự kiện tại nguồn; hồ sơ học viên không đổi |
| Xem trạng thái chuyển | `GET /api/v1/transfers/{ma_chuyen}` | Admin Big; Admin Small trong phạm vi được phép | Admin Big: `GLOBAL` để định vị nguồn; Admin Small: `LOCAL` tại site được gán | Đọc trạng thái tại nguồn; không suy ra site từ tiền tố mã học viên |
| Thống kê học viên theo cơ sở | `GET /api/v1/reports/students-by-site` | Admin Big toàn hệ thống; Admin Small site mình | `LOCAL` hoặc `GLOBAL` tùy phạm vi | Đọc `HocVien` và trạng thái chuyển liên quan; gộp tại API khi nhiều site |

## Request và quy tắc kiểm tra chính

Các trường dưới đây là phần nghiệp vụ tối thiểu để đặc tả. Kiểu SQL chính xác, khóa ngoại và giá trị enum phải đối chiếu schema trước khi triển khai.

### Đăng ký khóa học

```json
{
  "ma_hoc_vien": "Q1-HV-000001",
  "ma_lop": "Q1-LH-000001"
}
```

API phải xác nhận học viên và lớp thuộc cùng site, lớp đang nhận đăng ký và còn chỗ, học viên chưa có đăng ký trùng còn hiệu lực. Tạo `DangKy`, `HocPhi`, cập nhật sĩ số và ghi nhật ký trong một transaction cục bộ; lỗi ở một bước thì rollback cả transaction.

### Xếp hoặc đổi lớp

Request tối thiểu gồm `ma_lop_moi`. API lấy site từ đăng ký hiện tại; không nhận site để chuyển đăng ký sang cơ sở khác. Kiểm tra lớp đích cùng site, còn chỗ và phù hợp lịch; cập nhật đăng ký/sĩ số lớp cũ và mới trong một transaction cục bộ.

### Thu hoặc hoàn học phí

```json
{
  "ma_hoc_phi": "Q1-HP-000001",
  "loai": "thu",
  "so_tien": 1500000,
  "hinh_thuc": "chuyen_khoan",
  "ghi_chu": "..."
}
```

API tự lấy site từ khoản học phí. Kiểm tra số tiền dương, số dư khi thu/hoàn, quyền của người thao tác và trạng thái khoản phí. Tạo `PhieuThu`, cập nhật `HocPhi` và ghi log trong cùng transaction cục bộ. Không xóa phiếu đã phát sinh; hoàn tiền tạo một dòng `PhieuThu` loại `hoan`.

### Nhập hoặc sửa điểm

Request tối thiểu gồm `diem_so` trong khoảng 0–10. API xác định site từ đăng ký/lớp, kiểm tra giáo viên được phân công và loại điểm hợp lệ. Mỗi đăng ký chỉ có một dòng cho mỗi `loai_diem`; endpoint phải quy định rõ tạo mới khi chưa có điểm hay cập nhật điểm đã có, và mọi lần sửa phải ghi nhận lịch sử theo quy tắc audit của dự án.

### Chuyển cơ sở

Tạo đề nghị nhận tối thiểu `ma_hoc_vien`, `ma_co_so_dich`, `ly_do_de_nghi`. Không nhận `ma_co_so_nguon` như một giá trị đáng tin từ client; API lấy nguồn từ tài khoản Admin Small. Kiểm tra học viên hiện hành, nợ học phí, đích đang hoạt động, đích khác nguồn và không có giao dịch mở. Lưu trạng thái `cho_duyet` cùng sự kiện `de_nghi` tại nguồn; khi tạo đề nghị chưa được ghi hồ sơ đích.

Hộp thư Admin Big là `GLOBAL`: hỏi các site độc lập và gộp tại API. Duyệt/từ chối định tuyến về CSDL nguồn và ghi quyết định/sự kiện tại nguồn. Khi từ chối, cần `ly_do_tu_choi`; khi duyệt, kiểm tra lại điều kiện rồi mới giao Coordinator chạy `DISTRIBUTED-TX`. Giao dịch phải hỗ trợ trạng thái và phục hồi theo [README mục 5.5](../README.md#55-chuyển-học-viên-sang-cơ-sở-khác); không tuyên bố ACID nguyên tử xuyên hai CSDL.

### Thống kê học viên theo cơ sở

Site cụ thể chỉ được nhận từ request sau khi API kiểm tra phạm vi của người gọi. Admin Small không được yêu cầu site khác; Admin Big có thể truy vấn toàn hệ thống. Với `GLOBAL`, gộp kết quả ở API, loại bản `da_chuyen_di`, không đếm trùng trạng thái chuyển tạm thời và nêu rõ site không phản hồi.

## Mẫu hợp đồng endpoint

Sao chép mẫu này cho từng endpoint sau khi nhóm thống nhất:

```markdown
### [Tên thao tác]
- Trạng thái: Đề xuất / Đã thống nhất / Đã triển khai
- Method/path:
- Người gọi và vai trò:
- Quyền/phạm vi site:
- Kiểu phân tán:
- Site Router chọn site theo:
- Bảng đọc:
- Bảng ghi:
- Transaction cục bộ / giao dịch phân tán:
- Quy tắc request và validation:
- Ví dụ request:
- Ví dụ response thành công:
- HTTP status và mã lỗi:
- Xử lý retry/gửi trùng/cập nhật đồng thời:
- Kiểm tra đã chạy:
- Thay đổi giao diện/schema/tài liệu liên quan:
```
