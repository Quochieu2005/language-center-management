import { Alert, Card } from "antd";

export default function AuditPage() {
  return <Card title="Nhật ký hệ thống"><Alert type="warning" showIcon title="Web chưa thể tải nhật ký vì backend hiện chưa có API đọc bảng Logs." description="Trang không hiển thị dữ liệu mẫu. Khi API đọc Logs được thêm, cần xác định quyền và phạm vi site trước khi nối giao diện." /></Card>;
}
