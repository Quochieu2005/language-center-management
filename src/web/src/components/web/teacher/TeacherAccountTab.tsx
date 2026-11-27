"use client";

import { useEffect, useState } from "react";
import { Alert, Avatar, Button, Card, Col, Descriptions, Form, Input, Row, Skeleton, Space, Tag, Typography } from "antd";
import { message } from "@/lib/ui/message";
import { EditOutlined, LockOutlined, SafetyCertificateOutlined, UserOutlined } from "@ant-design/icons";
import { adminApi, type Teacher } from "@/lib/api/admin";
import { authApi } from "@/lib/api/auth";
import { useSession } from "@/lib/auth/session";
import { SelfAvatarUploader } from "@/components/shared/SelfAvatarUploader";
import portal from "@/components/web/shared/Portal.module.scss";

const TEACHING_STATUS: Record<string, { label: string; color: string }> = {
  dang_day: { label: "Đang giảng dạy", color: "green" },
  tam_nghi: { label: "Tạm nghỉ", color: "orange" },
  nghi_viec: { label: "Đã nghỉ việc", color: "default" },
};

export function TeacherAccountTab() {
  const { user, refreshProfile } = useSession();
  const [profile, setProfile] = useState<Teacher | null>(null);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [saving, setSaving] = useState(false);
  const [changing, setChanging] = useState(false);
  const [profileForm] = Form.useForm<{ full_name: string; phone?: string }>();
  const [passwordForm] = Form.useForm();

  useEffect(() => {
    if (!user?.slug) return;
    let cancelled = false;
    void (async () => {
      setLoading(true);
      setLoadError("");
      try {
        const [teacher, account] = await Promise.all([adminApi.teacherProfile(user.slug), authApi.profile(user.slug)]);
        if (cancelled) return;
        setProfile(teacher);
        setAvatarUrl(account.user.avatar_secure_url ?? teacher.avatar_secure_url ?? null);
        profileForm.setFieldsValue({ full_name: teacher.full_name, phone: teacher.phone ?? "" });
      } catch (reason) {
        if (!cancelled) setLoadError(reason instanceof Error ? reason.message : "Không tải được hồ sơ giáo viên.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [profileForm, user?.slug]);

  const saveProfile = async (values: { full_name: string; phone?: string }) => {
    if (!user?.slug) return;
    setSaving(true);
    try {
      const updated = await adminApi.updateTeacherProfile(user.slug, {
        full_name: values.full_name.trim(),
        phone: values.phone?.trim() || null,
      });
      setProfile(updated);
      profileForm.setFieldsValue({ full_name: updated.full_name, phone: updated.phone ?? "" });
      await refreshProfile();
      message.success("Đã cập nhật hồ sơ.");
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "Không cập nhật được hồ sơ.");
    } finally {
      setSaving(false);
    }
  };

  const changePassword = async (values: { current: string; next: string; confirm: string }) => {
    setChanging(true);
    try {
      await authApi.changePassword(values.current, values.next, values.confirm);
      message.success("Đổi mật khẩu thành công! Vui lòng ghi nhớ mật khẩu mới của bạn.");
      passwordForm.resetFields();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "Đổi mật khẩu thất bại.");
    } finally {
      setChanging(false);
    }
  };

  const status = TEACHING_STATUS[profile?.status ?? ""] ?? { label: "Chưa xác định", color: "default" };

  return (
    <Row gutter={[24, 24]}>
      <Col xs={24} lg={14}>
        <Card title={<span><UserOutlined className={portal.accent} style={{ marginRight: 8 }}/>Hồ sơ giáo viên</span>}>
          {loadError && <Alert type="error" showIcon title={loadError} style={{ marginBottom: 16 }} />}
          {loading ? <Skeleton active avatar paragraph={{ rows: 6 }} /> : (
            <>
              <Space align="center" size="large" style={{ marginBottom: 20 }}>
                <Avatar size={88} src={avatarUrl || undefined} icon={<UserOutlined />} style={{ background: "#2a7a67" }} alt="Ảnh đại diện" />
                <Space orientation="vertical" size={4}>
                  <Typography.Title level={4} style={{ margin: 0 }}>{profile?.full_name || user?.username}</Typography.Title>
                  <Typography.Text type="secondary">JPG, PNG hoặc WebP · tối đa 5 MB</Typography.Text>
                  <SelfAvatarUploader
                    slug={user?.slug}
                    hasAvatar={Boolean(avatarUrl)}
                    onUploaded={(url) => {
                      setAvatarUrl(url);
                      void refreshProfile();
                    }}
                  />
                </Space>
              </Space>

              <Form form={profileForm} layout="vertical" onFinish={saveProfile} disabled={!profile}>
                <Row gutter={16}>
                  <Col xs={24} md={12}>
                    <Form.Item
                      name="full_name"
                      label="Họ và tên"
                      rules={[{ required: true, whitespace: true, message: "Vui lòng nhập họ tên" }, { max: 150 }]}
                    >
                      <Input maxLength={150} placeholder="Họ và tên giáo viên" />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item
                      name="phone"
                      label="Số điện thoại"
                      rules={[{ pattern: /^[0-9+\s.-]{8,20}$/, message: "Số điện thoại không hợp lệ" }]}
                    >
                      <Input maxLength={20} placeholder="Ví dụ 0901234567" />
                    </Form.Item>
                  </Col>
                </Row>
                <Button type="primary" htmlType="submit" icon={<EditOutlined />} loading={saving}>Lưu thay đổi</Button>
              </Form>

              <Descriptions bordered size="small" column={{ xs: 1, sm: 2 }} style={{ marginTop: 24 }}>
                <Descriptions.Item label="Mã giáo viên"><Tag color="green">{profile?.teacher_id || user?.profile_id}</Tag></Descriptions.Item>
                <Descriptions.Item label="Cơ sở công tác"><Tag color="cyan">{profile?.site_code || user?.site_code}</Tag></Descriptions.Item>
                <Descriptions.Item label="Tên đăng nhập">{profile?.username || user?.username}</Descriptions.Item>
                <Descriptions.Item label="Email">{profile?.email || user?.email || "Chưa cập nhật"}</Descriptions.Item>
                <Descriptions.Item label="Chuyên môn">{profile?.specialty || "Chưa cập nhật"}</Descriptions.Item>
                <Descriptions.Item label="Trạng thái"><Tag color={status.color}>{status.label}</Tag></Descriptions.Item>
              </Descriptions>
              <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0, fontSize: 12 }}>
                Email, tên đăng nhập và cơ sở do trung tâm quản lý; liên hệ quản trị viên nếu cần thay đổi.
              </Typography.Paragraph>
            </>
          )}
        </Card>
      </Col>

      <Col xs={24} lg={10}>
        <Card title={<span><SafetyCertificateOutlined className={portal.accent} style={{ marginRight: 8 }}/>Đổi mật khẩu</span>}>
          <Form form={passwordForm} layout="vertical" onFinish={changePassword}>
            <Form.Item name="current" label="Mật khẩu hiện tại" rules={[{ required: true, message: "Vui lòng nhập mật khẩu hiện tại" }]}>
              <Input.Password prefix={<LockOutlined />} autoComplete="current-password" placeholder="Nhập mật khẩu hiện tại" />
            </Form.Item>
            <Form.Item
              name="next"
              label="Mật khẩu mới"
              rules={[{ required: true, message: "Vui lòng nhập mật khẩu mới" }, { min: 8, message: "Mật khẩu mới cần tối thiểu 8 ký tự" }]}
            >
              <Input.Password prefix={<LockOutlined />} autoComplete="new-password" placeholder="Tối thiểu 8 ký tự" />
            </Form.Item>
            <Form.Item
              name="confirm"
              label="Xác nhận mật khẩu mới"
              dependencies={["next"]}
              rules={[
                { required: true, message: "Vui lòng xác nhận mật khẩu mới" },
                ({ getFieldValue }) => ({
                  validator(_, value) {
                    return !value || getFieldValue("next") === value
                      ? Promise.resolve()
                      : Promise.reject(new Error("Mật khẩu xác nhận không khớp!"));
                  },
                }),
              ]}
            >
              <Input.Password prefix={<LockOutlined />} autoComplete="new-password" placeholder="Nhập lại mật khẩu mới" />
            </Form.Item>
            <Button type="primary" htmlType="submit" loading={changing} block>Cập nhật mật khẩu</Button>
          </Form>
        </Card>
      </Col>
    </Row>
  );
}
