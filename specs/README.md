# Tài liệu đặc tả giao diện và API

Thư mục này lưu yêu cầu thiết kế cho giao diện và các hợp đồng API. Hai file có mục đích riêng nhưng phải mô tả cùng một luồng nghiệp vụ:

| Tài liệu | Dùng để thống nhất |
|---|---|
| [`ui-ux.md`](ui-ux.md) | Vai trò sử dụng, màn hình, trường dữ liệu, trạng thái giao diện và thao tác người dùng |
| [`api.md`](api.md) | Endpoint, quyền, request/response, lỗi và site/bảng được đọc hoặc ghi |

Khi thêm hoặc đổi nghiệp vụ, cập nhật cả hai tài liệu nếu thay đổi ảnh hưởng tới giao diện và API. Mỗi yêu cầu phải khớp với kiến trúc trong [`README.md`](../README.md), cấu trúc dữ liệu trong [`docs/DATABASE_SCHEMA.md`](../docs/DATABASE_SCHEMA.md), và quy trình Git trong [`AGENTS.md`](../AGENTS.md). Các endpoint được ghi là **đề xuất** chỉ trở thành hợp đồng sau khi nhóm thống nhất; không coi tài liệu nháp là API đã triển khai.
