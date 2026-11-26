"use client";

import { Avatar, Card, Form, Input, Button, Typography, Space, message, Divider } from "antd";
import { UserOutlined, PhoneOutlined, HomeOutlined, LockOutlined } from "@ant-design/icons";
import { useState } from "react";
import type { ApiRow } from "@/lib/api/academics";
import { academicsApi } from "@/lib/api/academics";
import { authApi } from "@/lib/api/auth";
import { SocialAccountConnections } from "./SocialAccountConnections";
import { SelfAvatarUploader } from "@/components/shared/SelfAvatarUploader";
import portal from "@/components/web/shared/Portal.module.scss";

type Props = {
  profile: ApiRow | null;
  slug: string;
  onRefresh: () => Promise<void>;
};

export function StudentAccountTab({ profile, slug, onRefresh }: Props) {
  const [profileLoading, setProfileLoading] = useState(false);
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [profileForm] = Form.useForm();
  const [passwordForm] = Form.useForm();
  const [uploadedAvatar, setUploadedAvatar] = useState<string | null>(null);
  const avatarUrl = uploadedAvatar ?? (typeof profile?.avatar_secure_url === "string" ? profile.avatar_secure_url : null);

  // Luu thong tin lien he
  const saveProfile = async (values: { phone?: string; address?: string }) => {
    if (!slug) return;
    setProfileLoading(true);
    try {
      await academicsApi.updateStudentProfile(slug, values);
      message.success("Đã cập nhật thông tin liên hệ thành công!");
      await onRefresh();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Không lưu được thông tin.");
    } finally {
      setProfileLoading(false);
    }
  };

  // Doi mat khau
  const changePassword = async (values: {
    current_password: string;
    new_password: string;
    confirm_password: string;
  }) => {
    setPasswordLoading(true);
    try {
      await authApi.changePassword(
        values.current_password,
        values.new_password,
        values.confirm_password
      );
      message.success("Đổi mật khẩu thành công! Mật khẩu mới đã được cập nhật.");
      passwordForm.resetFields();
      await onRefresh();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Đổi mật khẩu không thành công.");
    } finally {
      setPasswordLoading(false);
    }
  };

  return (
    <div style={{ display: "grid", gap: 24 }}>
      {/* 1. Cap nhat thong tin lien he */}
      <Card
        title={
          <Space>
            <UserOutlined className={portal.accent} />
            <span>Thông tin cá nhân & Liên hệ</span>
          </Space>
        }
      >
        <Space align="center" size="large" style={{ marginBottom: 20 }} wrap>
          <Avatar size={88} src={avatarUrl || undefined} icon={<UserOutlined />} style={{ background: "var(--portal-accent)" }} alt="Ảnh đại diện" />
          <Space orientation="vertical" size={4}>
            <Typography.Text strong>Ảnh đại diện</Typography.Text>
            <Typography.Text type="secondary">JPG, PNG hoặc WebP · tối đa 5 MB</Typography.Text>
            <SelfAvatarUploader
              slug={slug}
              hasAvatar={Boolean(avatarUrl)}
              api={{ createIntent: academicsApi.createStudentSelfAvatarIntent, complete: academicsApi.completeStudentSelfAvatar }}
              onUploaded={(url) => { setUploadedAvatar(url); void onRefresh(); }}
            />
          </Space>
        </Space>
        <Form
          form={profileForm}
          layout="vertical"
          onFinish={saveProfile}
          initialValues={{
            phone: profile?.phone ? String(profile.phone) : "",
            address: profile?.address ? String(profile.address) : "",
          }}
        >
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
            <Form.Item label="Họ và tên">
              <Input prefix={<UserOutlined />} value={String(profile?.full_name || "")} disabled />
            </Form.Item>
            <Form.Item label="Mã học viên">
              <Input value={String(profile?.student_id || "")} disabled />
            </Form.Item>
            <Form.Item label="Email">
              <Input value={String(profile?.email || "")} disabled />
            </Form.Item>
            <Form.Item label="Cơ sở đào tạo">
              <Input value={String(profile?.site_code || "TD")} disabled />
            </Form.Item>
            <Form.Item
              name="phone"
              label="Số điện thoại liên hệ"
              rules={[{ max: 20, message: "Tối đa 20 ký tự" }]}
            >
              <Input prefix={<PhoneOutlined />} placeholder="Nhập số điện thoại của bạn" maxLength={20} />
            </Form.Item>
            <Form.Item
              name="address"
              label="Địa chỉ cư trú"
              rules={[{ max: 300, message: "Tối đa 300 ký tự" }]}
            >
              <Input prefix={<HomeOutlined />} placeholder="Nhập địa chỉ cư trú của bạn" maxLength={300} />
            </Form.Item>
          </div>
          <Button type="primary" htmlType="submit" loading={profileLoading}>
            Lưu thay đổi liên hệ
          </Button>
        </Form>
      </Card>

      {/* 2. Doi mat khau tai khoan */}
      <Card
        title={
          <Space>
            <LockOutlined className={portal.accent} />
            <span>Đổi mật khẩu tài khoản</span>
          </Space>
        }
      >
        <Typography.Paragraph type="secondary">
          Bạn có thể thay đổi mật khẩu mặc định được trung tâm cấp để bảo vệ tài khoản cá nhân.
        </Typography.Paragraph>

        <Form
          form={passwordForm}
          layout="vertical"
          onFinish={changePassword}
          style={{ maxWidth: 480 }}
        >
          <Form.Item
            name="current_password"
            label="Mật khẩu hiện tại"
            rules={[{ required: true, message: "Vui lòng nhập mật khẩu hiện tại." }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="Nhập mật khẩu hiện tại" />
          </Form.Item>

          <Form.Item
            name="new_password"
            label="Mật khẩu mới"
            rules={[
              { required: true, message: "Vui lòng nhập mật khẩu mới." },
              { min: 8, message: "Mật khẩu tối thiểu 8 ký tự." },
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="Nhập mật khẩu mới (tối thiểu 8 ký tự)" />
          </Form.Item>

          <Form.Item
            name="confirm_password"
            label="Xác nhận mật khẩu mới"
            dependencies={["new_password"]}
            rules={[
              { required: true, message: "Vui lòng xác nhận mật khẩu mới." },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue("new_password") === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error("Mật khẩu xác nhận không khớp."));
                },
              }),
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="Nhập lại mật khẩu mới" />
          </Form.Item>

          <Button type="primary" htmlType="submit" loading={passwordLoading}>
            Cập nhật mật khẩu mới
          </Button>
        </Form>
      </Card>

      {/* 3. Lien ket tai khoan mang xa hoi */}
      <SocialAccountConnections />
    </div>
  );
}
