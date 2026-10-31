"use client";

import { Alert, Button, Card, Form, Input, Space, Typography, message } from "antd";
import { useState } from "react";
import { useRouter } from "next/navigation";
import AdminLayout from "@/components/admin/layout/AdminLayout";
import { authApi } from "@/lib/api/auth";
import { RequireSession, useSession } from "@/lib/auth/session";

const ADMIN_ROLES = ["admin_big", "admin_small", "le_tan", "tu_van", "ke_toan", "xep_lop"];

type PasswordForm = {
  current_password: string;
  new_password: string;
  confirm_password: string;
};

export default function ChangePasswordRoute() {
  return (
    <RequireSession>
      <ChangePasswordRouteContent />
    </RequireSession>
  );
}

function ChangePasswordRouteContent() {
  const { user } = useSession();
  const content = <ChangePasswordForm />;

  if (ADMIN_ROLES.includes(user?.role || "")) {
    return <AdminLayout>{content}</AdminLayout>;
  }

  return <main style={{ minHeight: "100vh", padding: 20 }}>{content}</main>;
}

function ChangePasswordForm() {
  const { user, refreshProfile } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();

  const submit = async (values: PasswordForm) => {
    setBusy(true);
    setError("");
    try {
      const result = await authApi.changePassword(
        values.current_password,
        values.new_password,
        values.confirm_password,
      );
      await refreshProfile();
      message.success(result.detail);
      router.replace("/profile");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không đổi được mật khẩu.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section style={{ width: "min(100%, 600px)", margin: "24px auto" }}>
      <Card>
        <Space orientation="vertical" size="large" style={{ width: "100%" }}>
          <div>
            <Typography.Title level={2}>Đổi mật khẩu</Typography.Title>
            <Typography.Text type="secondary">Tài khoản: {user?.email}</Typography.Text>
          </div>

          {user?.must_change_password && (
            <Alert type="warning" title="Bạn cần đổi mật khẩu tạm thời để tiếp tục." />
          )}
          {error && <Alert type="error" title={error} />}

          <Form layout="vertical" onFinish={submit}>
            <Form.Item
              name="current_password"
              label="Mật khẩu hiện tại"
              rules={[{ required: true }]}
            >
              <Input.Password autoComplete="current-password" />
            </Form.Item>
            <Form.Item
              name="new_password"
              label="Mật khẩu mới (ít nhất 12 ký tự)"
              rules={[{ required: true, min: 12, max: 128 }]}
            >
              <Input.Password autoComplete="new-password" />
            </Form.Item>
            <Form.Item
              name="confirm_password"
              label="Nhập lại mật khẩu mới"
              dependencies={["new_password"]}
              rules={[
                { required: true },
                ({ getFieldValue }) => ({
                  validator(_, value) {
                    return !value || getFieldValue("new_password") === value
                      ? Promise.resolve()
                      : Promise.reject(new Error("Mật khẩu xác nhận không khớp."));
                  },
                }),
              ]}
            >
              <Input.Password autoComplete="new-password" />
            </Form.Item>
            <Button type="primary" htmlType="submit" loading={busy} block>
              Lưu mật khẩu
            </Button>
          </Form>
        </Space>
      </Card>
    </section>
  );
}
