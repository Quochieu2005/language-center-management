# Tài liệu đặc tả giao diện và API

Thư mục này lưu yêu cầu thiết kế cho giao diện và các hợp đồng API. Hai file có mục đích riêng nhưng phải mô tả cùng một luồng nghiệp vụ:

| Tài liệu | Dùng để thống nhất |
|---|---|
| [`ui-ux.md`](ui-ux.md) | Vai trò sử dụng, màn hình, trường dữ liệu, trạng thái giao diện và thao tác người dùng |
| [`api.md`](api.md) | Endpoint, quyền, request/response, lỗi và site/bảng được đọc hoặc ghi |

## Yêu cầu chung phải thể hiện trong cả API và UI

Đồ án dùng 3 site Q1/Q7/TD trong giới hạn **2–4 site**. Phải triển khai phân mảnh, replication, transaction và đồng bộ; chứng minh ít nhất **1 phương pháp phân mảnh, 1 phương pháp replication, 1 distributed transaction, 1 tình huống concurrency, 1 distributed query**. Các nhóm được chọn kiểu phân mảnh phù hợp.

Đối chiếu [yêu cầu chung](../README.md#yêu-cầu-chung-áp-dụng-cho-mọi-đề-tài), [kịch bản demo](../README.md#6-kịch-bản-demo) và [FS](../fs/Functional-Specification.md). API phải thực thi ranh giới site/transaction, kiểm soát cạnh tranh và trạng thái đồng bộ; UI hiển thị đúng kết quả, xung đột, đang xử lý hoặc thiếu site. Kiểm thử giao diện không thay thế bằng chứng từ API/DB. Cơ chế replication/distributed transaction còn mở vẫn là việc bắt buộc phải chốt và triển khai. Trước khi mô tả retry replication trong API, đối chiếu OPEN-14: `NhatKyDongBo` là log, chưa mặc định đủ làm tiến trình bền vững.

Khi thêm hoặc đổi nghiệp vụ, cập nhật cả hai tài liệu nếu thay đổi ảnh hưởng tới giao diện và API. Mỗi yêu cầu phải khớp với kiến trúc trong [`README.md`](../README.md), cấu trúc dữ liệu trong [`docs/DATABASE_SCHEMA.md`](../docs/DATABASE_SCHEMA.md), và quy trình Git trong [`AGENTS.md`](../AGENTS.md). Các endpoint được ghi là **đề xuất** chỉ trở thành hợp đồng sau khi nhóm thống nhất; không coi tài liệu nháp là API đã triển khai.
