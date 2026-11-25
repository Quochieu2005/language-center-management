"use client";

import { useState } from "react";
import { Card, Form, Input, Button, Row, Col, Typography, message, Tag, Descriptions } from "antd";
import { LockOutlined, UserOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { authApi, type SessionUser } from "@/lib/api/auth";

type TeacherAccountTabProps = {
  user: SessionUser | null;
};

export function TeacherAccountTab({ user }: TeacherAccountTabProps) {
  const [form] = Form.useForm();
  const [changing, setChanging] = useState(false);

  const handleChangePassword = async (values: { current: string; next: string; confirm: string }) => {
    if (values.next !== values.confirm) {
      message.error("Mật khẩu mới và xác nhận mật khẩu không khớp.");
      return;
    }
    setChanging(true);
    try {
      await authApi.changePassword(values.current, values.next, values.confirm);
      message.success("Đổi mật khẩu thành công! Vui lòng ghi nhớ mật khẩu mới của bạn.");
      form.resetFields();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Đổi mật khẩu thất bại.");
    } finally {
      setChanging(false);
    }
  };

  return (
    <div>
      <Row gutter={[24, 24]}>
        {/* Profile Card */}
        <Col xs={24} lg={12}>
          <Card
            title={
              <span>
                <UserOutlined style={{ marginRight: 8, color: "#3b82f6" }} />
                Thông tin tài khoản giáo viên
              </span>
            }
          >
            <Descriptions bordered layout="vertical" size="middle" column={{ xs: 1, sm: 2 }}>
              <Descriptions.Item label="Mã giáo viên">
                <Tag color="blue" style={{ fontSize: 13, fontWeight: 600 }}>
                  {user?.profile_id || "Chưa xác định"}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Tên đăng nhập">
                <strong>{user?.username || "Giáo viên"}</strong>
              </Descriptions.Item>
              <Descriptions.Item label="Email tài khoản">
                <span>{user?.email || "Chưa cập nhật"}</span>
              </Descriptions.Item>
              <Descriptions.Item label="Cơ sở công tác">
                <Tag color="cyan">{user?.site_code || "Chưa xác định"}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Vai trò hệ thống">
                <Tag color="purple">Giáo viên (LOCAL)</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Trạng thái giảng dạy">
                <Tag color="green">Đang giảng dạy</Tag>
              </Descriptions.Item>
            </Descriptions>

            <div style={{ marginTop: 20, padding: 14, background: "#f8fafc", borderRadius: 8, border: "1px solid #e2e8f0" }}>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                Lưu ý: Dữ liệu giảng dạy và điểm danh của bạn được phân mảnh cục bộ tại cơ sở {user?.site_code || "chưa xác định"}. Mọi điều chỉnh điểm được ghi nhận vào nhật ký kiểm toán.
              </Typography.Text>
            </div>
          </Card>
        </Col>

        {/* Change Password Card */}
        <Col xs={24} lg={12}>
          <Card
            title={
              <span>
                <SafetyCertificateOutlined style={{ marginRight: 8, color: "#10b981" }} />
                Đổi mật khẩu bảo mật
              </span>
            }
          >
            <Form form={form} layout="vertical" onFinish={handleChangePassword}>
              <Form.Item
                name="current"
                label="Mật khẩu hiện tại"
                rules={[{ required: true, message: "Vui lòng nhập mật khẩu hiện tại" }]}
              >
                <Input.Password prefix={<LockOutlined />} placeholder="Nhập mật khẩu hiện tại" />
              </Form.Item>

              <Form.Item
                name="next"
                label="Mật khẩu mới"
                rules={[
                  { required: true, message: "Vui lòng nhập mật khẩu mới" },
                  { min: 8, message: "Mật khẩu mới cần tối thiểu 8 ký tự" },
                ]}
              >
                <Input.Password prefix={<LockOutlined />} placeholder="Tối thiểu 8 ký tự" />
              </Form.Item>

              <Form.Item
                name="confirm"
                label="Xác nhận mật khẩu mới"
                dependencies={["next"]}
                rules={[
                  { required: true, message: "Vui lòng xác nhận mật khẩu mới" },
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      if (!value || getFieldValue("next") === value) {
                        return Promise.resolve();
                      }
                      return Promise.reject(new Error("Mật khẩu xác nhận không khớp!"));
                    },
                  }),
                ]}
              >
                <Input.Password prefix={<LockOutlined />} placeholder="Nhập lại mật khẩu mới" />
              </Form.Item>

              <Form.Item style={{ marginTop: 24, marginBottom: 0 }}>
                <Button type="primary" htmlType="submit" loading={changing} style={{ width: "100%" }}>
                  Cập nhật mật khẩu
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
