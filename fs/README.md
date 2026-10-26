# Functional Specification (FS)

Thư mục này chứa đặc tả chức năng của hệ thống Quản lý trung tâm đào tạo ngoại ngữ. Tài liệu mô tả người dùng được làm gì, điều kiện để thao tác hợp lệ, luồng xử lý, dữ liệu/site liên quan và cách nghiệm thu. Đây là yêu cầu thiết kế; nội dung trong FS không tự khẳng định chức năng đã có trong source.

## Tài liệu

- [Đặc tả chức năng hệ thống](Functional-Specification.md): phạm vi, vai trò, quy tắc chung, yêu cầu chức năng, luồng lỗi, phân tán và tiêu chí nghiệm thu.
- [README chính](../README.md#yêu-cầu-chung-áp-dụng-cho-mọi-đề-tài): yêu cầu 2–4 site, các kỹ thuật phân tán tối thiểu và kịch bản demo của đồ án 3 site Q1/Q7/TD.

## Cách dùng

1. Đọc README ở thư mục gốc để hiểu kiến trúc tổng thể và sáu nghiệp vụ bắt buộc của đề tài.
2. Dùng FS để xác định hành vi cần xây dựng và điều kiện nghiệm thu.
3. Tra [docs/DATABASE_SCHEMA.md](../docs/DATABASE_SCHEMA.md) để biết cấu trúc bảng, khóa, phân mảnh và định vị dữ liệu.
4. Tra [specs/api.md](../specs/api.md) và [specs/ui-ux.md](../specs/ui-ux.md) để biết hợp đồng API dự kiến và cách tổ chức giao diện.
5. Khi FS mâu thuẫn với schema hoặc README, không tự chọn một cách hiểu. Ghi lại mâu thuẫn, thống nhất với nhóm rồi cập nhật tài liệu liên quan cùng thay đổi.
6. Đối chiếu FS mục 10 với mã YC/TC của môn học; ghi bằng chứng chạy thật trước khi đánh dấu đạt. Seed ba DB hoặc hoàn tất giao diện không thay thế kiểm chứng phân tán.

## Trạng thái

FS là tài liệu yêu cầu. Theo trạng thái được ghi trong [src/api/README.md](../src/api/README.md), API hiện mới có liveness check; các nghiệp vụ trong tài liệu chưa được xem là đã triển khai chỉ vì đã được mô tả ở đây.
